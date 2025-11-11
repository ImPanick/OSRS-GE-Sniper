import discord
from discord.ext import commands, tasks
import requests
import json
import os
import asyncio
from datetime import datetime

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

async def collect_server_info(guild):
    """Collect server information (roles, members, channels, etc.)"""
    try:
        guild_id = str(guild.id)
        
        # Collect roles
        roles = []
        for role in guild.roles:
            if not role.is_bot_managed and role.name != "@everyone":
                roles.append({
                    "id": str(role.id),
                    "name": role.name,
                    "color": role.color.value if role.color.value else 0,
                    "position": role.position,
                    "mentionable": role.mentionable,
                    "managed": role.managed
                })
        
        # Collect text channels
        text_channels = []
        for channel in guild.text_channels:
            text_channels.append({
                "id": str(channel.id),
                "name": channel.name,
                "position": channel.position,
                "nsfw": channel.nsfw
            })
        
        # Collect members (with their roles)
        members = []
        online_count = 0
        for member in guild.members:
            if not member.bot:
                member_roles = [str(role.id) for role in member.roles if not role.is_bot_managed and role.name != "@everyone"]
                try:
                    if hasattr(member, 'status') and member.status != discord.Status.offline:
                        online_count += 1
                except Exception:
                    pass  # Status might not be available
                members.append({
                    "id": str(member.id),
                    "username": member.name,
                    "display_name": member.display_name,
                    "roles": member_roles,
                    "status": str(member.status) if hasattr(member, 'status') else "unknown"
                })
        
        # Collect bot permissions
        bot_member = guild.get_member(bot.user.id)
        bot_permissions = {}
        if bot_member:
            perms = bot_member.guild_permissions
            bot_permissions = {
                "mention_everyone": perms.mention_everyone,
                "manage_roles": perms.manage_roles,
                "send_messages": perms.send_messages,
                "embed_links": perms.embed_links,
                "attach_files": perms.attach_files,
                "read_message_history": perms.read_message_history,
                "use_external_emojis": perms.use_external_emojis
            }
        
        server_info = {
            "guild_id": guild_id,
            "guild_name": guild.name,
            "guild_icon": str(guild.icon.url) if guild.icon else None,
            "member_count": guild.member_count,
            "online_count": online_count,
            "roles": roles,
            "text_channels": text_channels,
            "members": members[:500],  # Limit to first 500 members to avoid huge payloads
            "bot_permissions": bot_permissions,
            "timestamp": int(datetime.now().timestamp())
        }
        
        # Send to backend
        try:
            response = requests.post(
                f"{CONFIG['backend_url']}/api/server_info/{guild_id}",
                json=server_info,
                timeout=10
            )
            if response.status_code == 200:
                print(f"[BOT] ✓ Updated server info: {guild.name} ({guild_id})")
            else:
                print(f"[BOT] ⚠ Failed to update server info: {guild.name} ({guild_id}) - HTTP {response.status_code}")
        except Exception as e:
            print(f"[BOT] ⚠ Error updating server info {guild.name} ({guild_id}): {e}")
    except Exception as e:
        print(f"[BOT] ⚠ Error collecting server info for {guild.name}: {e}")

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
        
        # Collect and send server info
        await collect_server_info(guild)
    
    poll_alerts.start()
    update_server_info.start()
    process_role_assignments.start()

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
    
    # Collect and send server info
    await collect_server_info(guild)

@tasks.loop(seconds=300)  # Update server info every 5 minutes
async def update_server_info():
    """Periodically update server information"""
    try:
        for guild in bot.guilds:
            await collect_server_info(guild)
            # Small delay between servers to avoid rate limits
            await asyncio.sleep(1)
    except Exception as e:
        print(f"[ERROR] update_server_info: {e}")

@tasks.loop(seconds=10)  # Check for role assignments every 10 seconds
async def process_role_assignments():
    """Process pending role assignments from admin panel"""
    try:
        for guild in bot.guilds:
            guild_id = str(guild.id)
            assignment_path = os.path.join("server_configs", f"{guild_id}_assignments.json")
            
            # Try to find assignment file (it's in backend, but we'll check via API)
            try:
                response = requests.get(f"{CONFIG['backend_url']}/api/server_info/{guild_id}/assignments", timeout=2)
                if response.status_code == 200:
                    assignments = response.json()
                    for assignment in assignments:
                        user_id = int(assignment.get('user_id'))
                        role_id = int(assignment.get('role_id'))
                        action = assignment.get('action', 'add')
                        
                        try:
                            member = guild.get_member(user_id)
                            role = guild.get_role(role_id)
                            
                            if member and role:
                                if action == 'add':
                                    await member.add_roles(role, reason="Assigned via admin panel")
                                    print(f"[BOT] ✓ Assigned role {role.name} to {member.name} in {guild.name}")
                                elif action == 'remove':
                                    await member.remove_roles(role, reason="Removed via admin panel")
                                    print(f"[BOT] ✓ Removed role {role.name} from {member.name} in {guild.name}")
                        except discord.Forbidden:
                            print(f"[BOT] ⚠ No permission to manage roles in {guild.name}")
                        except Exception as e:
                            print(f"[BOT] ⚠ Error processing role assignment: {e}")
            except Exception:
                pass  # Assignment file doesn't exist or API call failed
    except Exception as e:
        print(f"[ERROR] process_role_assignments: {e}")

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