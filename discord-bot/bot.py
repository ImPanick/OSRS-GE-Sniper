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

# Tier configuration cache: guild_id -> {tier_name -> {role_id, enabled, group, min_score, max_score, emoji}}
tier_configs = {}

# Deduplication cache: (guild_id, item_id, tier, timestamp_bucket) -> sent
# timestamp_bucket is rounded to nearest 5 minutes to prevent spam
alert_dedupe_cache = set()

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
    for filename in ["flips", "dumps", "spikes", "watchlist", "stats", "config", "nightly", "item_lookup"]:
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
    load_tier_configs.start()
    tiered_alerts.start()

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
            except (requests.RequestException, ValueError, KeyError) as e:
                # Assignment file doesn't exist or API call failed
                pass
    except Exception as e:
        print(f"[ERROR] process_role_assignments: {e}")

@tasks.loop(seconds=300)  # Update tier configs every 5 minutes
async def load_tier_configs():
    """Load tier configurations for all guilds"""
    try:
        for guild in bot.guilds:
            guild_id = str(guild.id)
            try:
                response = requests.get(
                    f"{CONFIG['backend_url']}/api/tiers?guild_id={guild_id}",
                    timeout=5
                )
                if response.status_code == 200:
                    tier_configs[guild_id] = response.json()
                    print(f"[BOT] ✓ Loaded tier config for {guild.name} ({guild_id})")
                else:
                    print(f"[BOT] ⚠ Failed to load tier config for {guild.name}: HTTP {response.status_code}")
            except Exception as e:
                print(f"[BOT] ⚠ Error loading tier config for {guild.name}: {e}")
    except Exception as e:
        print(f"[ERROR] load_tier_configs: {e}")

@load_tier_configs.before_loop
async def before_load_tier_configs():
    """Load tier configs immediately on startup"""
    await bot.wait_until_ready()
    # Run once immediately
    for guild in bot.guilds:
        guild_id = str(guild.id)
        try:
            response = requests.get(
                f"{CONFIG['backend_url']}/api/tiers?guild_id={guild_id}",
                timeout=5
            )
            if response.status_code == 200:
                tier_configs[guild_id] = response.json()
                print(f"[BOT] ✓ Loaded tier config for {guild.name} ({guild_id})")
        except Exception as e:
            print(f"[BOT] ⚠ Error loading tier config for {guild.name}: {e}")

@tasks.loop(seconds=30)  # Check for tiered alerts every 30 seconds
async def tiered_alerts():
    """Tiered alert loop using new dump engine"""
    try:
        # Get latest dump opportunities from new engine
        dumps = requests.get(f"{CONFIG['backend_url']}/api/dumps", timeout=30).json() or []
        
        if not dumps:
            return
        
        from utils.item_utils import get_item_thumbnail_url, get_item_wiki_url
        
        # Process each guild
        for guild in bot.guilds:
            guild_id = str(guild.id)
            
            # Get tier config for this guild
            guild_tiers = tier_configs.get(guild_id, {})
            if not guild_tiers:
                continue  # Skip if no tier config loaded
            
            # Filter opportunities for this guild
            for opp in dumps:
                tier_name = opp.get('tier', '').lower()
                tier_config = guild_tiers.get(tier_name)
                
                # Skip if tier not enabled or not configured
                if not tier_config or not tier_config.get('enabled', True):
                    continue
                
                # Check min-tier restriction (if configured)
                min_tier = guild_tiers.get('min_tier')
                if min_tier:
                    tier_order = ['iron', 'copper', 'bronze', 'silver', 'gold', 'platinum', 'ruby', 'sapphire', 'emerald', 'diamond']
                    try:
                        min_idx = tier_order.index(min_tier.lower())
                        opp_idx = tier_order.index(tier_name)
                        if opp_idx < min_idx:
                            continue
                    except ValueError:
                        pass
                
                # Deduplication check
                item_id = opp.get('id') or opp.get('item_id')
                timestamp_bucket = int(datetime.now().timestamp() // 300) * 300  # Round to 5 minutes
                dedupe_key = (guild_id, item_id, tier_name, timestamp_bucket)
                
                if dedupe_key in alert_dedupe_cache:
                    continue  # Already sent this alert
                
                # Mark as sent
                alert_dedupe_cache.add(dedupe_key)
                
                # Note: Old dedupe entries are cleaned up periodically below
                
                # Build embed
                item_name = opp.get('name', 'Unknown')
                item_id = item_id or opp.get('item_id', 0)
                tier_emoji = opp.get('emoji', '')
                tier_display = tier_name.capitalize()
                score = opp.get('score', 0)
                drop_pct = opp.get('drop_pct', 0)
                vol_spike_pct = opp.get('vol_spike_pct', 0)
                oversupply_pct = opp.get('oversupply_pct', 0)
                volume = opp.get('volume', 0)
                high = opp.get('high', 0)
                low = opp.get('low', 0)
                max_buy_4h = opp.get('max_buy_4h', 0)
                flags = opp.get('flags', [])
                
                # Build title
                title = f"{tier_emoji} {tier_display} Dump: {item_name}"
                
                # Build description
                description_parts = []
                description_parts.append(f"**Tier:** {tier_display} (Score: {score:.1f})")
                description_parts.append(f"**Drop %:** {drop_pct:.1f}%")
                description_parts.append(f"**Volume Spike %:** {vol_spike_pct:.1f}%")
                description_parts.append(f"**Oversupply %:** {oversupply_pct:.1f}%")
                description_parts.append(f"**Volume:** {volume:,}")
                description_parts.append(f"**High / Low:** {high:,} / {low:,}")
                description_parts.append(f"**Max Buy / 4h:** {max_buy_4h:,}")
                
                # Add flags
                flag_labels = []
                if 'slow_buy' in flags:
                    flag_labels.append("Slow Buy")
                if 'one_gp_dump' in flags:
                    flag_labels.append("1GP")
                if 'super' in flags:
                    flag_labels.append("Super")
                
                if flag_labels:
                    description_parts.append(f"**Flags:** {', '.join(flag_labels)}")
                
                # Create embed
                embed = discord.Embed(
                    title=title,
                    description="\n".join(description_parts),
                    color=0x8B0000,
                    url=get_item_wiki_url(item_id)
                )
                
                # Add thumbnail
                thumbnail_url = get_item_thumbnail_url(item_name, item_id)
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                
                # Add footer
                embed.set_footer(text=f"ID: {item_id} | Tax: 1%")
                embed.timestamp = datetime.now()
                
                # Get role to mention
                role_id = tier_config.get('role_id')
                content = None
                if role_id:
                    role = guild.get_role(int(role_id))
                    if role:
                        content = role.mention
                
                # Get channel to send to (use notification router logic)
                from utils.notification_router import get_server_config, determine_channel
                server_config = get_server_config(guild_id)
                channel_name = determine_channel(opp, "dump", server_config)
                
                if channel_name:
                    try:
                        channel = None
                        if channel_name.isdigit():
                            channel = bot.get_channel(int(channel_name))
                        else:
                            channel_name_clean = channel_name.replace("#", "").strip()
                            channel = discord.utils.get(guild.text_channels, name=channel_name_clean)
                        
                        if channel:
                            await channel.send(content=content, embed=embed)
                            print(f"[BOT] ✓ Sent {tier_display} alert for {item_name} to {guild.name}")
                    except Exception as e:
                        print(f"[BOT] ⚠ Error sending alert to {guild.name}: {e}")
                
                # Rate limit: only send one alert per guild per cycle
                break
        
        # Clean up old dedupe cache entries periodically
        if len(alert_dedupe_cache) > 10000:
            # Keep only recent entries (last hour)
            current_time = int(datetime.now().timestamp())
            old_keys = [k for k in alert_dedupe_cache if k[3] < current_time - 3600]
            for k in old_keys:
                alert_dedupe_cache.discard(k)
        
    except Exception as e:
        print(f"[ERROR] tiered_alerts: {e}")
        import traceback
        traceback.print_exc()

@tasks.loop(seconds=20)
async def poll_alerts():
    """Legacy poll alerts for spikes and flips (kept for compatibility)"""
    try:
        spikes = requests.get(f"{CONFIG['backend_url']}/api/spikes", timeout=30).json() or []
        
        # Import router
        from utils.notification_router import broadcast_to_all_servers
        
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
                volume = item.get('volume', 0)
                limit = item.get('limit', 0)
                rise_pct = item.get('rise_pct', 0)
                profit_per_item = sell_price - buy_price
                profit_pct = (profit_per_item / buy_price * 100) if buy_price > 0 else 0
                
                # Risk metrics
                risk_score = item.get('risk_score', 0)
                risk_level = item.get('risk_level', 'UNKNOWN')
                profitability_confidence = item.get('profitability_confidence', 0)
                liquidity_score = item.get('liquidity_score', 0)
                
                # Price historicals
                avg_7d = item.get('avg_7d')
                avg_24h = item.get('avg_24h')
                avg_12h = item.get('avg_12h')
                avg_6h = item.get('avg_6h')
                avg_1h = item.get('avg_1h')
                prev_price = item.get('prev_price')
                prev_timestamp = item.get('prev_timestamp')
                
                # Build title
                title = f"📈 SPIKE DETECTED — SELL NOW: {item_name}"
                
                # Build description with all details
                description_parts = []
                
                # Price change
                description_parts.append(f"**+{rise_pct:.1f}% RISE**")
                description_parts.append(f"**Price:** {buy_price:,} GP → {sell_price:,} GP")
                
                # Volume and limit info
                if volume and limit:
                    description_parts.append(f"**IB/IS Volume:** {volume:,}/{volume:,} | **Limit:** {limit:,}")
                
                # Instant buy/sell prices
                insta_info = []
                if insta_buy and insta_buy != buy_price:
                    insta_info.append(f"**Insta Buy:** {insta_buy:,} GP")
                if insta_sell and insta_sell != sell_price:
                    insta_info.append(f"**Insta Sell:** {insta_sell:,} GP")
                
                if insta_info:
                    description_parts.append("⚡ " + " | ".join(insta_info))
                
                # Price historicals section
                historicals_list = []
                if avg_7d:
                    historicals_list.append(f"**7d:** {avg_7d:,} GP")
                if avg_24h:
                    historicals_list.append(f"**24h:** {avg_24h:,} GP")
                if avg_12h:
                    historicals_list.append(f"**12h:** {avg_12h:,} GP")
                if avg_6h:
                    historicals_list.append(f"**6h:** {avg_6h:,} GP")
                if avg_1h:
                    historicals_list.append(f"**1h:** {avg_1h:,} GP")
                if prev_price and prev_timestamp:
                    hours_ago = (datetime.now().timestamp() - prev_timestamp) / 3600
                    historicals_list.append(f"**Prev:** {prev_price:,} GP ({hours_ago:.1f} hours ago)")
                
                if historicals_list:
                    description_parts.append("📊 **Price History:**\n" + "\n".join(historicals_list))
                
                # Profit per item
                if profit_per_item > 0:
                    description_parts.append(f"✔ **Profit per item:** +{profit_per_item:,} GP ({profit_pct:.2f}%)")
                
                # Risk and confidence
                description_parts.append(f"⚠️ **Risk:** {risk_level} ({risk_score:.1f}/100) | **Confidence:** {profitability_confidence:.1f}% | **Liquidity:** {liquidity_score:.1f}%")
                
                # Create embed
                embed = discord.Embed(
                    title=title,
                    description="\n".join(description_parts),
                    color=0x00FF00,
                    url=get_item_wiki_url(item_id)
                )
                
                # Add thumbnail (top-right in Discord)
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                
                # Add footer with metadata
                footer_text = f"ID: {item_id}"
                if item.get('version'):
                    footer_text += f" | v{item.get('version')}"
                footer_text += " | Tax: 1%"
                embed.set_footer(text=footer_text)
                
                # Add timestamp
                embed.timestamp = datetime.now()
                
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