# discord-bot/utils/notification_router.py
"""
Per-server notification routing system
Routes alerts to configured channels based on item type, price, and category
"""
import discord
import requests
import json
import os

# Load config - path relative to discord-bot directory
# From discord-bot/utils/notification_router.py -> discord-bot/ -> root/config.json
# Same as bot.py which uses '../config.json' from discord-bot/
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'config.json')
CONFIG = json.load(open(CONFIG_PATH))

def get_server_config(guild_id: str):
    """Fetch server config from backend"""
    try:
        response = requests.get(f"{CONFIG['backend_url']}/api/server_config/{guild_id}", timeout=2)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def determine_channel(item, item_type: str, server_config):
    """
    Determine which channel to route an item to based on server config
    
    item_type: 'flip', 'dump', 'spike'
    """
    if not server_config or not server_config.get("enabled", True):
        return None
    
    channels = server_config.get("channels", {})
    thresholds = server_config.get("thresholds", {})
    
    if item_type == "dump":
        # Nuclear dumps go to nuclear channel if configured, otherwise to appropriate price tier
        if item.get("volume", 0) > 1_500_000:
            # Check for nuclear dumps channel (if added later)
            pass
        
        # Route by price tier
        price = item.get("buy", 0)
        if price < thresholds.get("cheap_max", 10000):
            return channels.get("cheap_flips")
        elif price < thresholds.get("medium_max", 500000):
            return channels.get("medium_flips")
        elif price < thresholds.get("expensive_max", 50000000):
            return channels.get("expensive_flips")
        else:
            return channels.get("billionaire_flips")
    
    elif item_type == "flip":
        # Route flips by price tier
        price = item.get("buy", 0)
        if price < thresholds.get("cheap_max", 10000):
            return channels.get("cheap_flips")
        elif price < thresholds.get("medium_max", 500000):
            return channels.get("medium_flips")
        elif price < thresholds.get("expensive_max", 50000000):
            return channels.get("expensive_flips")
        else:
            return channels.get("billionaire_flips")
    
    elif item_type == "spike":
        # Spikes typically go to expensive/billionaire channels
        price = item.get("sell", 0)
        if price >= thresholds.get("expensive_max", 50000000):
            return channels.get("billionaire_flips")
        elif price >= thresholds.get("medium_max", 500000):
            return channels.get("expensive_flips")
        else:
            return channels.get("medium_flips")
    
    return None

async def route_notification(bot, guild_id: str, item, item_type: str, embed: discord.Embed):
    """
    Route a notification to the appropriate channel for a server
    Returns True if routed, False otherwise
    """
    server_config = get_server_config(guild_id)
    if not server_config:
        return False
    
    channel_name = determine_channel(item, item_type, server_config)
    if not channel_name:
        return False
    
    # Try to find the channel
    try:
        # Channel name can be a channel ID (numeric string) or channel name
        channel = None
        guild = bot.get_guild(int(guild_id))
        if not guild:
            return False
        
        # Try as channel ID first
        if channel_name.isdigit():
            channel = bot.get_channel(int(channel_name))
            # Verify it's in the correct guild
            if channel and channel.guild.id == guild.id:
                await channel.send(embed=embed)
                return True
        
        # Try to find by name (remove # if present)
        channel_name_clean = channel_name.replace("#", "").strip()
        channel = discord.utils.get(guild.text_channels, name=channel_name_clean)
        
        if channel:
            await channel.send(embed=embed)
            return True
    except Exception as e:
        print(f"[ERROR] Failed to route notification to {guild_id}: {e}")
    
    return False

async def broadcast_to_all_servers(bot, items, item_type: str, embed_template_func):
    """
    Broadcast notifications to all servers the bot is in
    embed_template_func: function(item) -> discord.Embed
    """
    routed_count = 0
    for guild in bot.guilds:
        guild_id = str(guild.id)
        
        # Check if server is banned
        try:
            response = requests.get(f"{CONFIG['backend_url']}/api/server_banned/{guild_id}", timeout=1)
            if response.status_code == 200 and response.json().get("banned"):
                continue
        except:
            pass
        
        # Route each item to appropriate channel
        for item in items[:3]:  # Limit to top 3 per server
            embed = embed_template_func(item)
            if await route_notification(bot, guild_id, item, item_type, embed):
                routed_count += 1
                break  # Only send one notification per server per cycle
    
    return routed_count

