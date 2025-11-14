import discord
from discord.ext import commands, tasks
import requests
import json
import os
import asyncio
import base64
from datetime import datetime

# Try to import cryptography for token decryption
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    print("[BOT] WARNING: cryptography not available, tokens must be stored in plaintext")

# Load config with fallback paths for Docker and local development
# Priority: 1) CONFIG_PATH env var, 2) /repo/config.json (Docker), 3) relative paths (local dev)
CONFIG_PATH = os.getenv('CONFIG_PATH')
if not CONFIG_PATH:
    # Try Docker path first (/repo is mounted repo root)
    docker_path = '/repo/config.json'
    if os.path.exists(docker_path):
        CONFIG_PATH = docker_path
    else:
        # Fall back to relative paths for local development
        CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')
        if not os.path.exists(CONFIG_PATH):
            CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
        if not os.path.exists(CONFIG_PATH):
            CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')

print(f"[BOT] Loading config from: {CONFIG_PATH}")
print(f"[BOT] Config file exists: {os.path.exists(CONFIG_PATH)}")

with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypt Discord bot token if encrypted, otherwise return as-is.
    Uses the same encryption key derivation as backend.
    """
    if not encrypted_token:
        return None
    
    if not CRYPTOGRAPHY_AVAILABLE:
        # Fallback: return as-is (assume plain token)
        return encrypted_token
    
    # Check if token appears to be encrypted (base64-encoded Fernet token)
    try:
        # Try to decode as base64 first
        decoded = base64.urlsafe_b64decode(encrypted_token.encode())
        
        # If it's a valid Fernet token (starts with Fernet header), decrypt it
        if decoded.startswith(b'gAAAAA'):  # Fernet tokens start with this
            # Get encryption key from config or derive from admin_key
            admin_key = CONFIG.get('admin_key', '')
            if not admin_key:
                print("[BOT] WARNING: No admin_key found, cannot decrypt token")
                return encrypted_token
            
            # Derive key using same method as backend
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'osrs_ge_sniper_salt',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(admin_key.encode()))
            
            fernet = Fernet(key)
            decrypted = fernet.decrypt(decoded)
            return decrypted.decode()
    except Exception as e:
        # Not encrypted or decryption failed, return as-is (plain token)
        pass
    
    # Return as-is if it doesn't appear to be encrypted
    return encrypted_token

# Decrypt token if encrypted
encrypted_token = CONFIG.get('discord_token', '').strip()
token = decrypt_token(encrypted_token) if encrypted_token else ''
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
bot.synced = False  # Track if slash commands have been synced

# Tier configuration cache: guild_id -> {tier_name -> {role_id, enabled, group, min_score, max_score, emoji}}
tier_configs = {}

# Deduplication cache: (guild_id, item_id, tier, timestamp_bucket) -> sent
# timestamp_bucket is rounded to nearest 5 minutes to prevent spam
alert_dedupe_cache = set()

# Alert settings cache: guild_id -> {min_margin_gp, min_score, enabled_tiers, max_alerts_per_interval, last_updated}
alert_settings_cache = {}
ALERT_SETTINGS_CACHE_TTL = 60  # Refresh cache every 60 seconds

async def fetch_alert_settings(guild_id, force_refresh=False):
    """Fetch alert settings for a guild from backend with caching"""
    import time
    
    # Check cache first (unless force refresh)
    if not force_refresh and guild_id in alert_settings_cache:
        cached = alert_settings_cache[guild_id]
        last_updated = cached.get('last_updated', 0)
        if time.time() - last_updated < ALERT_SETTINGS_CACHE_TTL:
            return cached
    
    try:
        response = requests.get(
            f"{CONFIG['backend_url']}/api/config/{guild_id}/alerts",
            timeout=5
        )
        if response.status_code == 200:
            settings = response.json()
            settings['last_updated'] = time.time()
            alert_settings_cache[guild_id] = settings
            return settings
        else:
            # Return defaults if fetch fails
            defaults = {
                "min_margin_gp": 0,
                "min_score": 0,
                "enabled_tiers": [],
                "max_alerts_per_interval": 1,
                "last_updated": time.time()
            }
            alert_settings_cache[guild_id] = defaults
            return defaults
    except Exception as e:
        print(f"[BOT] ⚠ Error fetching alert settings for {guild_id}: {e}")
        # Return defaults on error
        defaults = {
            "min_margin_gp": 0,
            "min_score": 0,
            "enabled_tiers": [],
            "max_alerts_per_interval": 1,
            "last_updated": time.time()
        }
        alert_settings_cache[guild_id] = defaults
        return defaults

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
    print(f"[BOT] ========================================")
    print(f"[BOT] {bot.user} ONLINE (ID: {bot.user.id})")
    print(f"[BOT] ========================================")
    
    # Load all cogs
    print(f"[BOT] Loading cogs...")
    loaded_cogs = []
    failed_cogs = []
    for filename in ["flips", "dumps", "spikes", "watchlist", "stats", "config", "nightly", "item_lookup", "text_commands"]:
        try:
            await bot.load_extension(f"cogs.{filename}")
            loaded_cogs.append(filename)
            print(f"[BOT] ✓ Loaded cog: {filename}")
        except Exception as e:
            failed_cogs.append((filename, str(e)))
            print(f"[BOT] ✗ Failed to load cog {filename}: {e}")
            import traceback
            traceback.print_exc()
    
    print(f"[BOT] Loaded {len(loaded_cogs)}/{len(loaded_cogs) + len(failed_cogs)} cogs")
    
    # Sync slash commands - try global sync first, then per-guild if needed
    if not bot.synced:
        try:
            # Global sync (works for all guilds, but can take up to 1 hour to propagate)
            synced = await bot.tree.sync()
            print(f"[BOT] ✓ Synced {len(synced)} slash command(s) globally")
            
            # Log command names for verification
            if synced:
                cmd_names = [cmd.name for cmd in synced]
                print(f"[BOT] Commands synced: {', '.join(cmd_names)}")
            
            bot.synced = True
        except Exception as e:
            print(f"[BOT] ⚠ Failed to sync slash commands globally: {e}")
            import traceback
            traceback.print_exc()
            
            # Try per-guild sync as fallback
            print(f"[BOT] Attempting per-guild sync...")
            for guild in bot.guilds:
                try:
                    bot.tree.copy_global_to(guild=guild)
                    synced = await bot.tree.sync(guild=guild)
                    print(f"[BOT] ✓ Synced {len(synced)} command(s) for {guild.name}")
                except Exception as guild_error:
                    print(f"[BOT] ⚠ Failed to sync commands for {guild.name}: {guild_error}")
    
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
    
    # Start background tasks
    print(f"[BOT] Starting background tasks...")
    try:
        poll_alerts.start()
        print(f"[BOT] ✓ Started poll_alerts task")
    except Exception as e:
        print(f"[BOT] ✗ Failed to start poll_alerts: {e}")
    
    try:
        update_server_info.start()
        print(f"[BOT] ✓ Started update_server_info task")
    except Exception as e:
        print(f"[BOT] ✗ Failed to start update_server_info: {e}")
    
    try:
        process_role_assignments.start()
        print(f"[BOT] ✓ Started process_role_assignments task")
    except Exception as e:
        print(f"[BOT] ✗ Failed to start process_role_assignments: {e}")
    
    try:
        refresh_guild_configs.start()
        print(f"[BOT] ✓ Started refresh_guild_configs task")
    except Exception as e:
        print(f"[BOT] ✗ Failed to start refresh_guild_configs: {e}")
    
    try:
        load_tier_configs.start()
        print(f"[BOT] ✓ Started load_tier_configs task")
    except Exception as e:
        print(f"[BOT] ✗ Failed to start load_tier_configs: {e}")
    
    try:
        tiered_alerts.start()
        print(f"[BOT] ✓ Started tiered_alerts task")
    except Exception as e:
        print(f"[BOT] ✗ Failed to start tiered_alerts: {e}")
    
    print(f"[BOT] ========================================")
    print(f"[BOT] Bot is ready and operational!")
    print(f"[BOT] Connected to {len(bot.guilds)} server(s)")
    print(f"[BOT] ========================================")

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

@tasks.loop(seconds=60)  # Refresh guild configs every 60 seconds
async def refresh_guild_configs():
    """Refresh unified guild configurations for all guilds"""
    try:
        for guild in bot.guilds:
            guild_id = str(guild.id)
            try:
                config = await fetch_guild_config(guild_id)
                print(f"[BOT] ✓ Refreshed config for {guild.name} ({guild_id})")
            except Exception as e:
                print(f"[BOT] ⚠ Error refreshing config for {guild.name}: {e}")
    except Exception as e:
        print(f"[ERROR] refresh_guild_configs: {e}")

@refresh_guild_configs.before_loop
async def before_refresh_guild_configs():
    """Load guild configs immediately on startup"""
    await bot.wait_until_ready()
    # Run once immediately
    for guild in bot.guilds:
        guild_id = str(guild.id)
        try:
            config = await fetch_guild_config(guild_id)
            print(f"[BOT] ✓ Loaded config for {guild.name} ({guild_id})")
        except Exception as e:
            print(f"[BOT] ⚠ Error loading config for {guild.name}: {e}")

@tasks.loop(seconds=300)  # Update tier configs every 5 minutes (for tier display info)
async def load_tier_configs():
    """Load tier configurations for all guilds (for tier display/emoji info)"""
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
    """Tiered alert loop using new dump engine with watchlist filtering"""
    try:
        # Get latest dump opportunities from new engine
        try:
            response = requests.get(f"{CONFIG['backend_url']}/api/dumps", timeout=30)
            if response.status_code != 200:
                print(f"[BOT] ⚠ Failed to fetch dumps: HTTP {response.status_code}")
                return
            dumps = response.json() or []
        except requests.exceptions.RequestException as e:
            print(f"[BOT] ⚠ Error fetching dumps from backend: {e}")
            return
        
        if not dumps:
            return
        
        from utils.item_utils import get_item_thumbnail_url, get_item_wiki_url
        
        # Process each guild
        total_alerts_sent = 0
        for guild in bot.guilds:
            guild_id = str(guild.id)
            
            try:
                # Get tier config for this guild (structure: {"tiers": [...], "min_tier_name": ...})
                tier_config_data = tier_configs.get(guild_id, {})
                if not tier_config_data:
                    continue  # Skip if no tier config loaded
                
                # Extract tier settings dict and min_tier_name
                tier_settings = {}
                if isinstance(tier_config_data, dict):
                    if "tiers" in tier_config_data:
                        # New format: {"tiers": [{"name": "iron", "role_id": ..., "enabled": ...}, ...], "min_tier_name": "ruby"}
                        for tier_info in tier_config_data.get("tiers", []):
                            tier_name = tier_info.get("name", "").lower()
                            tier_settings[tier_name] = {
                                "role_id": tier_info.get("role_id"),
                                "enabled": tier_info.get("enabled", True),
                                "group": tier_info.get("group", "metals"),
                                "min_score": tier_info.get("min_score", 0),
                                "max_score": tier_info.get("max_score", 100),
                                "emoji": tier_info.get("emoji", "")
                            }
                        min_tier_name = tier_config_data.get("min_tier_name")
                    else:
                        # Old format: direct dict mapping
                        tier_settings = tier_config_data
                        min_tier_name = None
                else:
                    continue
                
                # Get watchlist for this guild
                watchlist_items = []
                try:
                    watchlist_response = requests.get(
                        f"{CONFIG['backend_url']}/api/watchlist?guild_id={guild_id}",
                        timeout=5
                    )
                    if watchlist_response.status_code == 200:
                        watchlist_data = watchlist_response.json()
                        watchlist_items = [item.get("item_id") for item in watchlist_data if item.get("item_id")]
                except Exception as e:
                    print(f"[BOT] ⚠ Error fetching watchlist for {guild.name}: {e}")
                
                # Get unified guild config
                guild_config = guild_config_cache.get(guild_id)
                if not guild_config:
                    guild_config = await fetch_guild_config(guild_id)
                
                # Extract settings from unified config
                alert_channel_id = guild_config.get("alert_channel_id")
                min_margin_gp = guild_config.get("min_margin_gp", 0)
                min_score = guild_config.get("min_score", 0)
                enabled_tiers_list = guild_config.get("enabled_tiers", [])
                max_alerts_per_cycle = guild_config.get("max_alerts_per_interval", 1)
                role_ids_per_tier = guild_config.get("role_ids_per_tier", {})
                min_tier_name = guild_config.get("min_tier_name")
                
                # Get server config for fallback channel routing
                from utils.notification_router import get_server_config, determine_channel
                server_config = get_server_config(guild_id)
                
                if not server_config or not server_config.get("enabled", True):
                    continue  # Skip if server not enabled
                
                # Filter opportunities for this guild
                alerts_sent = 0
                
                for opp in dumps:
                    if alerts_sent >= max_alerts_per_cycle:
                        break
                    
                    tier_name = opp.get('tier', '').lower()
                    tier_setting = tier_settings.get(tier_name)
                    
                    # Skip if tier not enabled or not configured
                    if not tier_setting or not tier_setting.get('enabled', True):
                        continue
                    
                    # Check enabled_tiers filter (if configured)
                    if enabled_tiers_list and len(enabled_tiers_list) > 0:
                        if tier_name not in enabled_tiers_list:
                            continue  # Skip if tier not in enabled list
                    
                    # Check min_score filter
                    score = opp.get('score', 0)
                    if score < min_score:
                        continue  # Skip if score below threshold
                    
                    # Check min_margin_gp filter (for dumps, check realistic_profit or max_profit_4h)
                    realistic_profit = opp.get('realistic_profit', 0) or opp.get('max_profit_4h', 0)
                    if realistic_profit < min_margin_gp:
                        continue  # Skip if profit margin below threshold
                    
                    # Check min-tier restriction (from unified config)
                    if min_tier_name:
                        tier_order = ['iron', 'copper', 'bronze', 'silver', 'gold', 'platinum', 'ruby', 'sapphire', 'emerald', 'diamond']
                        try:
                            min_idx = tier_order.index(min_tier_name.lower())
                            opp_idx = tier_order.index(tier_name)
                            if opp_idx < min_idx:
                                continue
                        except ValueError:
                            pass
                    
                    # Watchlist filtering: send if item is in watchlist OR watchlist is empty (send all above min tier)
                    item_id = opp.get('id') or opp.get('item_id')
                    if watchlist_items:  # If watchlist has items, only send alerts for watched items
                        if item_id not in watchlist_items:
                            continue  # Skip if not in watchlist
                    # If watchlist is empty, send all items that pass tier checks (already handled above)
                    
                    # Deduplication check
                    timestamp_bucket = int(datetime.now().timestamp() // 300) * 300  # Round to 5 minutes
                    dedupe_key = (guild_id, item_id, tier_name, timestamp_bucket)
                    
                    if dedupe_key in alert_dedupe_cache:
                        continue  # Already sent this alert
                    
                    # Mark as sent
                    alert_dedupe_cache.add(dedupe_key)
                    
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
                    group = opp.get('group', 'metals')
                    
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
                    
                    # Add footer with tier group
                    group_display = "Gems" if group == "gems" else "Metals"
                    embed.set_footer(text=f"ID: {item_id} | {group_display} | Tax: 1%")
                    embed.timestamp = datetime.now()
                    
                    # Get role to mention (from unified config role_ids_per_tier, fallback to tier_setting)
                    role_id = role_ids_per_tier.get(tier_name) or tier_setting.get('role_id')
                    content = None
                    if role_id:
                        try:
                            role = guild.get_role(int(role_id))
                            if role:
                                content = role.mention
                        except (ValueError, TypeError):
                            pass  # Invalid role ID, skip mention
                    
                    # Get channel to send to (use alert_channel_id from unified config, or fallback to server config)
                    channel = None
                    if alert_channel_id:
                        try:
                            channel = bot.get_channel(int(alert_channel_id))
                            # Verify it's in the correct guild
                            if channel and channel.guild.id != guild.id:
                                channel = None
                        except (ValueError, TypeError):
                            pass
                    
                    # Fallback to server config channel routing if alert_channel_id not set
                    if not channel:
                        channel_name = determine_channel(opp, "dump", server_config)
                        if channel_name:
                            if channel_name.isdigit():
                                channel = bot.get_channel(int(channel_name))
                                # Verify it's in the correct guild
                                if channel and channel.guild.id != guild.id:
                                    channel = None
                            else:
                                channel_name_clean = channel_name.replace("#", "").strip()
                                channel = discord.utils.get(guild.text_channels, name=channel_name_clean)
                    
                    if channel:
                        try:
                            await channel.send(content=content, embed=embed)
                            alerts_sent += 1
                            total_alerts_sent += 1
                            print(f"[BOT] ✓ Sent {tier_display} alert for {item_name} to {guild.name} (#{channel.name})")
                        except discord.Forbidden:
                            print(f"[BOT] ⚠ No permission to send message in {guild.name} (channel: {channel.name})")
                        except discord.HTTPException as e:
                            print(f"[BOT] ⚠ HTTP error sending alert to {guild.name}: {e}")
                        except Exception as e:
                            print(f"[BOT] ⚠ Error sending alert to {guild.name}: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        print(f"[BOT] ⚠ No channel configured for {guild.name} (item: {item_name}, tier: {tier_display})")
                
                if alerts_sent > 0:
                    print(f"[BOT] Sent {alerts_sent} alert(s) to {guild.name}")
            except Exception as e:
                print(f"[BOT] ⚠ Error processing alerts for {guild.name}: {e}")
                import traceback
                traceback.print_exc()
        
        if total_alerts_sent > 0:
            print(f"[BOT] Total alerts sent this cycle: {total_alerts_sent}")
        
        # Clean up old dedupe cache entries periodically
        if len(alert_dedupe_cache) > 10000:
            # Keep only recent entries (last hour)
            current_time = int(datetime.now().timestamp())
            old_keys = [k for k in alert_dedupe_cache if k[3] < current_time - 3600]
            for k in old_keys:
                alert_dedupe_cache.discard(k)
            print(f"[BOT] Cleaned up {len(old_keys)} old dedupe cache entries")
        
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
        
        # Filter spikes by alert settings for each guild
        filtered_spikes = []
        for spike in spikes:
            # Check if any guild would accept this spike
            spike_profit = spike.get('profit', 0) or (spike.get('sell', 0) - spike.get('buy', 0))
            
            # Check each guild's settings
            for guild in bot.guilds:
                guild_id = str(guild.id)
                alert_settings = await fetch_alert_settings(guild_id)
                min_margin_gp = alert_settings.get("min_margin_gp", 0)
                
                # If this spike meets at least one guild's threshold, include it
                if spike_profit >= min_margin_gp:
                    filtered_spikes.append(spike)
                    break  # Only need to match one guild
        
        # Broadcast filtered spikes
        if filtered_spikes:
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
            await broadcast_to_all_servers(bot, filtered_spikes, "spike", spike_embed)
        
    except Exception as e:
        print(f"[ERROR] poll_alerts: {e}")

# Ensure token is stripped of any whitespace (already decrypted above)
token = token.strip() if token else ""
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