import discord
from discord.ext import commands, tasks
import requests
import json
import os

# Load config with fallback paths for Docker and local development
CONFIG_PATH = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(__file__), '..', 'config.json'))
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')

print(f"[BOT] Loading config from: {CONFIG_PATH}")
print(f"[BOT] Config file exists: {os.path.exists(CONFIG_PATH)}")

with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

# Validate token exists and show first/last few chars for debugging (don't log full token)
token = CONFIG.get('discord_token', '').strip()
if token:
    token_preview = f"{token[:10]}...{token[-10:]}" if len(token) > 20 else "***"
    print(f"[BOT] Token found: {token_preview} (length: {len(token)})")
    print(f"[BOT] Token has whitespace: {token != token.strip()}")
else:
    print("[BOT] ERROR: No discord_token found in config!")
    print(f"[BOT] Config keys: {list(CONFIG.keys())}")
intents = discord.Intents.default()
intents.message_content = True
intents.members = True  # Required for role mentions and member access
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"{bot.user} ONLINE")
    for filename in ["flips", "dumps", "spikes", "watchlist", "stats", "config", "nightly"]:
        await bot.load_extension(f"cogs.{filename}")
    
    # Auto-register all existing servers
    print(f"[BOT] Registering {len(bot.guilds)} servers with backend...")
    for guild in bot.guilds:
        guild_id = str(guild.id)
        try:
            # Call backend to auto-create config file
            response = requests.get(f"{CONFIG['backend_url']}/api/server_config/{guild_id}", timeout=5)
            if response.status_code == 200:
                print(f"[BOT] ✓ Registered server: {guild.name} ({guild_id})")
            else:
                print(f"[BOT] ⚠ Failed to register server: {guild.name} ({guild_id}) - HTTP {response.status_code}")
        except Exception as e:
            print(f"[BOT] ⚠ Error registering server {guild.name} ({guild_id}): {e}")
    
    poll_alerts.start()

@bot.event
async def on_guild_join(guild):
    """Auto-register server when bot joins"""
    guild_id = str(guild.id)
    print(f"[BOT] Joined new server: {guild.name} ({guild_id})")
    try:
        # Call backend to auto-create config file
        response = requests.get(f"{CONFIG['backend_url']}/api/server_config/{guild_id}", timeout=5)
        if response.status_code == 200:
            print(f"[BOT] ✓ Auto-registered server: {guild.name} ({guild_id})")
        else:
            print(f"[BOT] ⚠ Failed to auto-register server: {guild.name} ({guild_id}) - HTTP {response.status_code}")
    except Exception as e:
        print(f"[BOT] ⚠ Error auto-registering server {guild.name} ({guild_id}): {e}")

@tasks.loop(seconds=20)
async def poll_alerts():
    """Poll backend and route notifications to per-server channels"""
    try:
        # Get latest data
        dumps = requests.get(f"{CONFIG['backend_url']}/api/dumps", timeout=30).json() or []
        spikes = requests.get(f"{CONFIG['backend_url']}/api/spikes", timeout=30).json() or []
        flips = requests.get(f"{CONFIG['backend_url']}/api/top", timeout=30).json() or []
        
        # Import router
        from utils.notification_router import broadcast_to_all_servers
        
        # Broadcast dumps
        if dumps:
            from utils.item_utils import get_item_thumbnail_url, get_item_wiki_url
            
            def dump_embed(item):
                item_name = item.get('name', 'Unknown')
                item_id = item.get('id', 0)
                thumbnail_url = get_item_thumbnail_url(item_name, item_id)
                
                buy_price = item.get('buy', 0)
                sell_price = item.get('sell', buy_price)
                insta_buy = item.get('insta_buy', buy_price)
                insta_sell = item.get('insta_sell', sell_price)
                
                # Build price description
                price_desc = f"Buy: {buy_price:,} GP → Sell: {sell_price:,} GP"
                if insta_buy != buy_price or insta_sell != sell_price:
                    price_desc += f"\n⚡ Insta Buy: {insta_buy:,} GP | Insta Sell: {insta_sell:,} GP"
                
                # Add risk metrics
                risk_score = item.get('risk_score', 0)
                risk_level = item.get('risk_level', 'UNKNOWN')
                profitability_confidence = item.get('profitability_confidence', 0)
                
                risk_info = f"\n⚠️ **Risk:** {risk_level} ({risk_score:.1f}/100) | **Confidence:** {profitability_confidence:.1f}%"
                
                # Build price historicals
                historicals_text = ""
                avg_7d = item.get('avg_7d')
                avg_24h = item.get('avg_24h')
                avg_12h = item.get('avg_12h')
                avg_6h = item.get('avg_6h')
                avg_1h = item.get('avg_1h')
                prev_price = item.get('prev_price')
                prev_timestamp = item.get('prev_timestamp')
                
                if avg_7d or avg_24h or avg_12h or avg_6h or avg_1h or prev_price:
                    historicals_text = "\n\n📊 **Price Historicals:**\n"
                    if avg_7d:
                        historicals_text += f"7d: {avg_7d:,} GP | "
                    if avg_24h:
                        historicals_text += f"24h: {avg_24h:,} GP | "
                    if avg_12h:
                        historicals_text += f"12h: {avg_12h:,} GP | "
                    if avg_6h:
                        historicals_text += f"6h: {avg_6h:,} GP | "
                    if avg_1h:
                        historicals_text += f"1h: {avg_1h:,} GP"
                    if prev_price:
                        from datetime import datetime
                        if prev_timestamp:
                            hours_ago = (datetime.now().timestamp() - prev_timestamp) / 3600
                            historicals_text += f"\nPrev: {prev_price:,} GP ({hours_ago:.1f} hours ago)"
                
                embed = discord.Embed(
                    title=f"🔥 DUMP: {item_name}",
                    description=f"**{item.get('drop_pct', 0):.1f}% DROP**\n"
                              f"{price_desc}\n"
                              f"Vol: {item.get('volume', 0):,}\n"
                              f"{item.get('quality_label', '')}"
                              f"{risk_info}"
                              f"{historicals_text}",
                    color=0x8B0000,
                    url=get_item_wiki_url(item_id)
                )
                
                # Add thumbnail if available
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                
                return embed
            await broadcast_to_all_servers(bot, dumps, "dump", dump_embed)
        
        # Broadcast spikes
        if spikes:
            from utils.item_utils import get_item_thumbnail_url, get_item_wiki_url
            
            def spike_embed(item):
                item_name = item.get('name', 'Unknown')
                item_id = item.get('id', 0)
                thumbnail_url = get_item_thumbnail_url(item_name, item_id)
                
                buy_price = item.get('buy', 0)
                sell_price = item.get('sell', 0)
                insta_buy = item.get('insta_buy', buy_price)
                insta_sell = item.get('insta_sell', sell_price)
                
                # Build price description
                price_desc = f"Buy: {buy_price:,} GP → Sell: {sell_price:,} GP"
                if insta_buy != buy_price or insta_sell != sell_price:
                    price_desc += f"\n⚡ Insta Buy: {insta_buy:,} GP | Insta Sell: {insta_sell:,} GP"
                
                # Add risk metrics
                risk_score = item.get('risk_score', 0)
                risk_level = item.get('risk_level', 'UNKNOWN')
                profitability_confidence = item.get('profitability_confidence', 0)
                
                risk_info = f"\n⚠️ **Risk:** {risk_level} ({risk_score:.1f}/100) | **Confidence:** {profitability_confidence:.1f}%"
                
                # Build price historicals
                historicals_text = ""
                avg_7d = item.get('avg_7d')
                avg_24h = item.get('avg_24h')
                avg_12h = item.get('avg_12h')
                avg_6h = item.get('avg_6h')
                avg_1h = item.get('avg_1h')
                prev_price = item.get('prev_price')
                prev_timestamp = item.get('prev_timestamp')
                
                if avg_7d or avg_24h or avg_12h or avg_6h or avg_1h or prev_price:
                    historicals_text = "\n\n📊 **Price Historicals:**\n"
                    if avg_7d:
                        historicals_text += f"7d: {avg_7d:,} GP | "
                    if avg_24h:
                        historicals_text += f"24h: {avg_24h:,} GP | "
                    if avg_12h:
                        historicals_text += f"12h: {avg_12h:,} GP | "
                    if avg_6h:
                        historicals_text += f"6h: {avg_6h:,} GP | "
                    if avg_1h:
                        historicals_text += f"1h: {avg_1h:,} GP"
                    if prev_price:
                        from datetime import datetime
                        if prev_timestamp:
                            hours_ago = (datetime.now().timestamp() - prev_timestamp) / 3600
                            historicals_text += f"\nPrev: {prev_price:,} GP ({hours_ago:.1f} hours ago)"
                
                embed = discord.Embed(
                    title=f"📈 SPIKE: {item_name}",
                    description=f"**+{item.get('rise_pct', 0):.1f}% RISE**\n"
                              f"{price_desc}\n"
                              f"Vol: {item.get('volume', 0):,}"
                              f"{risk_info}"
                              f"{historicals_text}",
                    color=0x00FF00,
                    url=get_item_wiki_url(item_id)
                )
                
                # Add thumbnail if available
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                
                return embed
            await broadcast_to_all_servers(bot, spikes, "spike", spike_embed)
        
    except Exception as e:
        print(f"[ERROR] poll_alerts: {e}")

# Ensure token is stripped of any whitespace
token = CONFIG.get("discord_token", "").strip()
if not token:
    print("[BOT] ERROR: discord_token is missing or empty in config.json")
    print("[BOT] Please check your config.json file and ensure discord_token is set")
    exit(1)

# Validate token format (basic check)
if token == "YOUR_BOT_TOKEN_HERE" or "YOUR_BOT_TOKEN" in token.upper():
    print("[BOT] ERROR: discord_token is still set to placeholder value!")
    print("[BOT] Please update config.json with your actual bot token from Discord Developer Portal")
    print("[BOT] Get it from: https://discord.com/developers/applications → Your App → Bot → Token")
    exit(1)

print(f"[BOT] Attempting to connect with token: {token[:10]}...{token[-10:]}")
print("[BOT] If you see 401 errors, the token is invalid. Get a new one from Discord Developer Portal.")
try:
    bot.run(token)
except Exception as e:
    print(f"[BOT] FATAL ERROR: {e}")
    print("[BOT] The bot token is invalid or expired.")
    print("[BOT] Steps to fix:")
    print("[BOT] 1. Go to https://discord.com/developers/applications")
    print("[BOT] 2. Select your application → Bot section")
    print("[BOT] 3. Click 'Reset Token' and copy the new token")
    print("[BOT] 4. Update config.json with the new token")
    print("[BOT] 5. Restart: docker compose restart bot")
    raise