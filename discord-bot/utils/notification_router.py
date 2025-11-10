# discord-bot/utils/notification_router.py
"""
Per-server notification routing system
Routes alerts to configured channels based on item type, price, and category
"""
import discord
import requests
import json
import os

# Load config with fallback paths for Docker and local development
# From discord-bot/utils/notification_router.py -> discord-bot/ -> root/config.json
CONFIG_PATH = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', 'config.json'))
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '..', '..', 'config.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
CONFIG = json.load(open(CONFIG_PATH))

def get_server_config(guild_id: str):
    """Fetch server config from backend"""
    try:
        backend_url = os.getenv('BACKEND_URL', CONFIG.get('backend_url', 'http://localhost:5000'))
        response = requests.get(f"{backend_url}/api/server_config/{guild_id}", timeout=2)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None

def determine_roles_to_ping(item, item_type: str, server_config):
    """
    Determine which roles to ping based on risk level and quality
    
    Returns list of role IDs/names to ping
    """
    if not server_config:
        return []
    
    roles = server_config.get("roles", {})
    roles_to_ping = []
    
    # Risk-based role pings
    risk_score = item.get("risk_score", 0)
    risk_level = item.get("risk_level", "").upper()
    
    if risk_level == "LOW" and roles.get("risk_low"):
        roles_to_ping.append(roles["risk_low"])
    elif risk_level == "MEDIUM" and roles.get("risk_medium"):
        roles_to_ping.append(roles["risk_medium"])
    elif risk_level == "HIGH" and roles.get("risk_high"):
        roles_to_ping.append(roles["risk_high"])
    elif risk_level == "VERY HIGH" and roles.get("risk_very_high"):
        roles_to_ping.append(roles["risk_very_high"])
    
    # Quality-based role pings (for dumps)
    if item_type == "dump":
        quality = item.get("quality", "")
        quality_label = item.get("quality_label", "")
        volume = item.get("volume", 0)
        
        # Nuclear dumps (1.5M+ volume)
        if volume > 1_500_000 and roles.get("quality_nuclear"):
            roles_to_ping.append(roles["quality_nuclear"])
        
        # Quality-based pings
        if "⭐⭐⭐⭐⭐" in quality or "GOD-TIER" in quality_label:
            if roles.get("quality_god_tier"):
                roles_to_ping.append(roles["quality_god_tier"])
        elif "⭐⭐⭐⭐" in quality or "ELITE" in quality_label:
            if roles.get("quality_elite"):
                roles_to_ping.append(roles["quality_elite"])
        elif "⭐⭐⭐" in quality or "PREMIUM" in quality_label:
            if roles.get("quality_premium"):
                roles_to_ping.append(roles["quality_premium"])
        elif "⭐⭐" in quality or "GOOD" in quality_label:
            if roles.get("quality_good"):
                roles_to_ping.append(roles["quality_good"])
        elif "⭐" in quality or "DEAL" in quality_label:
            if roles.get("quality_deal"):
                roles_to_ping.append(roles["quality_deal"])
        
        # General dump role
        if roles.get("dumps"):
            roles_to_ping.append(roles["dumps"])
    
    elif item_type == "spike":
        # General spike role
        if roles.get("spikes"):
            roles_to_ping.append(roles["spikes"])
    
    elif item_type == "flip":
        # General flip role
        if roles.get("flips"):
            roles_to_ping.append(roles["flips"])
    
    # Remove duplicates
    return list(set(roles_to_ping))

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
    
    # Determine roles to ping
    roles_to_ping = determine_roles_to_ping(item, item_type, server_config)
    
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
                # Build role mentions
                role_mentions = []
                for role_identifier in roles_to_ping:
                    role = None
                    # Try as role ID first
                    if str(role_identifier).isdigit():
                        role = guild.get_role(int(role_identifier))
                    else:
                        # Try to find by name
                        role = discord.utils.get(guild.roles, name=str(role_identifier))
                    
                    if role:
                        role_mentions.append(role.mention)
                
                # Send message with role mentions if any
                content = " ".join(role_mentions) if role_mentions else None
                await channel.send(content=content, embed=embed)
                return True
        
        # Try to find by name (remove # if present)
        channel_name_clean = channel_name.replace("#", "").strip()
        channel = discord.utils.get(guild.text_channels, name=channel_name_clean)
        
        if channel:
            # Build role mentions
            role_mentions = []
            for role_identifier in roles_to_ping:
                role = None
                # Try as role ID first
                if str(role_identifier).isdigit():
                    role = guild.get_role(int(role_identifier))
                else:
                    # Try to find by name
                    role = discord.utils.get(guild.roles, name=str(role_identifier))
                
                if role:
                    role_mentions.append(role.mention)
            
            # Send message with role mentions if any
            content = " ".join(role_mentions) if role_mentions else None
            await channel.send(content=content, embed=embed)
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
            backend_url = os.getenv('BACKEND_URL', CONFIG.get('backend_url', 'http://localhost:5000'))
            response = requests.get(f"{backend_url}/api/server_banned/{guild_id}", timeout=1)
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

