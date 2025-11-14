# discord-bot/cogs/debug.py
"""
Debug commands for bot diagnostics and configuration inspection
"""
import discord
from discord import app_commands, Embed
from discord.ext import commands
import json
import os
import time
from datetime import datetime

# Load config with fallback paths for Docker and local development
CONFIG_PATH = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(__file__), '..', '..', 'config.json'))
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')

CONFIG = {}
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, 'r') as f:
        CONFIG = json.load(f)

class Debug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def is_admin(self, user: discord.Member):
        """Check if user has admin permissions"""
        if not user:
            return False
        return user.guild_permissions.manage_guild or user.guild_permissions.administrator

    @app_commands.command(name="sniper_debug", description="Show bot configuration and status for this server (Admin only)")
    async def sniper_debug(self, interaction: discord.Interaction):
        """Slash command to show debug information"""
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
            return
        
        if not self.is_admin(interaction.user):
            await interaction.response.send_message("❌ This command requires Manage Server permission.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            guild_id = str(interaction.guild.id)
            
            # Get unified config from bot's cache (access via bot instance)
            guild_config_cache = getattr(self.bot, 'guild_config_cache', {})
            tier_configs = getattr(self.bot, 'tier_configs', {})
            last_dump_fetch_time = getattr(self.bot, 'last_dump_fetch_time', None)
            last_dump_fetch_success = getattr(self.bot, 'last_dump_fetch_success', False)
            
            guild_config = guild_config_cache.get(guild_id, {}) if isinstance(guild_config_cache, dict) else {}
            tier_config_data = tier_configs.get(guild_id, {}) if isinstance(tier_configs, dict) else {}
            
            # Build debug embed
            embed = Embed(
                title="🔧 Bot Debug Information",
                description=f"Configuration and status for **{interaction.guild.name}**",
                color=0x3498db
            )
            
            # Alert Channel
            alert_channel_id = guild_config.get("alert_channel_id")
            if alert_channel_id:
                try:
                    channel = self.bot.get_channel(int(alert_channel_id))
                    if channel:
                        channel_info = f"{channel.mention} (#{channel.name})"
                    else:
                        channel_info = f"ID: {alert_channel_id} (channel not found)"
                except (ValueError, TypeError):
                    channel_info = f"ID: {alert_channel_id} (invalid)"
            else:
                channel_info = "❌ Not configured"
            embed.add_field(name="📢 Alert Channel", value=channel_info, inline=False)
            
            # Alert Settings
            min_margin_gp = guild_config.get("min_margin_gp", 0)
            min_score = guild_config.get("min_score", 0)
            max_alerts = guild_config.get("max_alerts_per_interval", 1)
            enabled_tiers = guild_config.get("enabled_tiers", [])
            
            settings_text = []
            settings_text.append(f"**Min Margin GP:** {min_margin_gp:,}")
            settings_text.append(f"**Min Score:** {min_score}")
            settings_text.append(f"**Max Alerts/Interval:** {max_alerts}")
            if enabled_tiers:
                settings_text.append(f"**Enabled Tiers:** {', '.join([t.capitalize() for t in enabled_tiers])}")
            else:
                settings_text.append(f"**Enabled Tiers:** All tiers")
            
            embed.add_field(name="⚙️ Alert Settings", value="\n".join(settings_text), inline=False)
            
            # Tier Configuration
            tier_info = []
            if tier_config_data and "tiers" in tier_config_data:
                tiers = tier_config_data.get("tiers", [])
                min_tier_name = tier_config_data.get("min_tier_name")
                
                for tier in sorted(tiers, key=lambda x: x.get('min_score', 0)):
                    tier_name = tier.get('name', '').capitalize()
                    emoji = tier.get('emoji', '')
                    enabled = tier.get('enabled', True)
                    role_id = tier.get('role_id')
                    
                    role_info = ""
                    if role_id:
                        try:
                            role = interaction.guild.get_role(int(role_id))
                            if role:
                                role_info = f" → {role.mention}"
                            else:
                                role_info = f" → Role ID: {role_id} (not found)"
                        except (ValueError, TypeError):
                            role_info = f" → Role ID: {role_id} (invalid)"
                    
                    status = "✅" if enabled else "❌"
                    tier_info.append(f"{status} {emoji} **{tier_name}**{role_info}")
                
                if min_tier_name:
                    tier_info.append(f"\n**Min Tier:** {min_tier_name.capitalize()}")
            else:
                tier_info.append("No tier configuration loaded")
            
            embed.add_field(name="🎯 Tier Configuration", value="\n".join(tier_info) if tier_info else "None", inline=False)
            
            # Role Mappings
            role_ids_per_tier = guild_config.get("role_ids_per_tier", {})
            if role_ids_per_tier:
                role_mappings = []
                for tier_name, role_id in role_ids_per_tier.items():
                    try:
                        role = interaction.guild.get_role(int(role_id))
                        if role:
                            role_mappings.append(f"**{tier_name.capitalize()}:** {role.mention}")
                        else:
                            role_mappings.append(f"**{tier_name.capitalize()}:** Role ID {role_id} (not found)")
                    except (ValueError, TypeError):
                        role_mappings.append(f"**{tier_name.capitalize()}:** Invalid role ID")
                embed.add_field(name="👥 Role Mappings", value="\n".join(role_mappings), inline=False)
            
            # Cache Status
            last_updated = guild_config.get("last_updated", 0)
            if last_updated:
                cache_time = datetime.fromtimestamp(last_updated).strftime("%Y-%m-%d %H:%M:%S")
                cache_age = int(time.time() - last_updated)
                cache_status = f"Last updated: {cache_time} ({cache_age}s ago)"
            else:
                cache_status = "Never updated"
            
            embed.add_field(name="💾 Config Cache", value=cache_status, inline=False)
            
            # Backend Status
            backend_status = []
            backend_status.append(f"**Backend URL:** {CONFIG.get('backend_url', 'NOT SET')}")
            
            if last_dump_fetch_time:
                fetch_time = datetime.fromtimestamp(last_dump_fetch_time).strftime("%Y-%m-%d %H:%M:%S")
                fetch_age = int(time.time() - last_dump_fetch_time)
                backend_status.append(f"**Last Dump Fetch:** {fetch_time} ({fetch_age}s ago)")
                backend_status.append(f"**Last Fetch Success:** {'✅' if last_dump_fetch_success else '❌'}")
            else:
                backend_status.append("**Last Dump Fetch:** Never")
            
            embed.add_field(name="🔌 Backend Status", value="\n".join(backend_status), inline=False)
            
            # Bot Info
            bot_info = []
            bot_info.append(f"**Latency:** {round(self.bot.latency * 1000)}ms")
            bot_info.append(f"**Guilds:** {len(self.bot.guilds)}")
            bot_info.append(f"**Uptime:** {self.get_uptime()}")
            
            embed.add_field(name="🤖 Bot Info", value="\n".join(bot_info), inline=False)
            
            embed.set_footer(text=f"Guild ID: {guild_id}")
            embed.timestamp = datetime.now()
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"[ERROR] /sniper_debug command failed: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"❌ Error fetching debug information: {str(e)}", ephemeral=True)

    @commands.command(name="sniper_debug", aliases=["debug", "status"])
    async def sniper_debug_text(self, ctx):
        """Text command to show debug information"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.")
            return
        
        if not self.is_admin(ctx.author):
            await ctx.send("❌ This command requires Manage Server permission.")
            return
        
        try:
            guild_id = str(ctx.guild.id)
            
            # Get unified config from bot's cache (access via bot instance)
            guild_config_cache = getattr(self.bot, 'guild_config_cache', {})
            tier_configs = getattr(self.bot, 'tier_configs', {})
            last_dump_fetch_time = getattr(self.bot, 'last_dump_fetch_time', None)
            last_dump_fetch_success = getattr(self.bot, 'last_dump_fetch_success', False)
            
            guild_config = guild_config_cache.get(guild_id, {}) if isinstance(guild_config_cache, dict) else {}
            tier_config_data = tier_configs.get(guild_id, {}) if isinstance(tier_configs, dict) else {}
            
            # Build debug embed
            embed = Embed(
                title="🔧 Bot Debug Information",
                description=f"Configuration and status for **{ctx.guild.name}**",
                color=0x3498db
            )
            
            # Alert Channel
            alert_channel_id = guild_config.get("alert_channel_id")
            if alert_channel_id:
                try:
                    channel = self.bot.get_channel(int(alert_channel_id))
                    if channel:
                        channel_info = f"{channel.mention} (#{channel.name})"
                    else:
                        channel_info = f"ID: {alert_channel_id} (channel not found)"
                except (ValueError, TypeError):
                    channel_info = f"ID: {alert_channel_id} (invalid)"
            else:
                channel_info = "❌ Not configured"
            embed.add_field(name="📢 Alert Channel", value=channel_info, inline=False)
            
            # Alert Settings
            min_margin_gp = guild_config.get("min_margin_gp", 0)
            min_score = guild_config.get("min_score", 0)
            max_alerts = guild_config.get("max_alerts_per_interval", 1)
            enabled_tiers = guild_config.get("enabled_tiers", [])
            
            settings_text = []
            settings_text.append(f"**Min Margin GP:** {min_margin_gp:,}")
            settings_text.append(f"**Min Score:** {min_score}")
            settings_text.append(f"**Max Alerts/Interval:** {max_alerts}")
            if enabled_tiers:
                settings_text.append(f"**Enabled Tiers:** {', '.join([t.capitalize() for t in enabled_tiers])}")
            else:
                settings_text.append(f"**Enabled Tiers:** All tiers")
            
            embed.add_field(name="⚙️ Alert Settings", value="\n".join(settings_text), inline=False)
            
            # Tier Configuration
            tier_info = []
            if tier_config_data and "tiers" in tier_config_data:
                tiers = tier_config_data.get("tiers", [])
                min_tier_name = tier_config_data.get("min_tier_name")
                
                for tier in sorted(tiers, key=lambda x: x.get('min_score', 0)):
                    tier_name = tier.get('name', '').capitalize()
                    emoji = tier.get('emoji', '')
                    enabled = tier.get('enabled', True)
                    role_id = tier.get('role_id')
                    
                    role_info = ""
                    if role_id:
                        try:
                            role = ctx.guild.get_role(int(role_id))
                            if role:
                                role_info = f" → {role.mention}"
                            else:
                                role_info = f" → Role ID: {role_id} (not found)"
                        except (ValueError, TypeError):
                            role_info = f" → Role ID: {role_id} (invalid)"
                    
                    status = "✅" if enabled else "❌"
                    tier_info.append(f"{status} {emoji} **{tier_name}**{role_info}")
                
                if min_tier_name:
                    tier_info.append(f"\n**Min Tier:** {min_tier_name.capitalize()}")
            else:
                tier_info.append("No tier configuration loaded")
            
            embed.add_field(name="🎯 Tier Configuration", value="\n".join(tier_info) if tier_info else "None", inline=False)
            
            # Role Mappings
            role_ids_per_tier = guild_config.get("role_ids_per_tier", {})
            if role_ids_per_tier:
                role_mappings = []
                for tier_name, role_id in role_ids_per_tier.items():
                    try:
                        role = ctx.guild.get_role(int(role_id))
                        if role:
                            role_mappings.append(f"**{tier_name.capitalize()}:** {role.mention}")
                        else:
                            role_mappings.append(f"**{tier_name.capitalize()}:** Role ID {role_id} (not found)")
                    except (ValueError, TypeError):
                        role_mappings.append(f"**{tier_name.capitalize()}:** Invalid role ID")
                embed.add_field(name="👥 Role Mappings", value="\n".join(role_mappings), inline=False)
            
            # Cache Status
            last_updated = guild_config.get("last_updated", 0)
            if last_updated:
                cache_time = datetime.fromtimestamp(last_updated).strftime("%Y-%m-%d %H:%M:%S")
                cache_age = int(time.time() - last_updated)
                cache_status = f"Last updated: {cache_time} ({cache_age}s ago)"
            else:
                cache_status = "Never updated"
            
            embed.add_field(name="💾 Config Cache", value=cache_status, inline=False)
            
            # Backend Status
            backend_status = []
            backend_status.append(f"**Backend URL:** {CONFIG.get('backend_url', 'NOT SET')}")
            
            if last_dump_fetch_time:
                fetch_time = datetime.fromtimestamp(last_dump_fetch_time).strftime("%Y-%m-%d %H:%M:%S")
                fetch_age = int(time.time() - last_dump_fetch_time)
                backend_status.append(f"**Last Dump Fetch:** {fetch_time} ({fetch_age}s ago)")
                backend_status.append(f"**Last Fetch Success:** {'✅' if last_dump_fetch_success else '❌'}")
            else:
                backend_status.append("**Last Dump Fetch:** Never")
            
            embed.add_field(name="🔌 Backend Status", value="\n".join(backend_status), inline=False)
            
            # Bot Info
            bot_info = []
            bot_info.append(f"**Latency:** {round(self.bot.latency * 1000)}ms")
            bot_info.append(f"**Guilds:** {len(self.bot.guilds)}")
            bot_info.append(f"**Uptime:** {self.get_uptime()}")
            
            embed.add_field(name="🤖 Bot Info", value="\n".join(bot_info), inline=False)
            
            embed.set_footer(text=f"Guild ID: {guild_id}")
            embed.timestamp = datetime.now()
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            print(f"[ERROR] !sniper_debug command failed: {e}")
            import traceback
            traceback.print_exc()
            await ctx.send(f"❌ Error fetching debug information: {str(e)}")

    def get_uptime(self):
        """Calculate bot uptime"""
        if not hasattr(self.bot, 'start_time'):
            return "Unknown"
        uptime_seconds = int(time.time() - self.bot.start_time)
        days = uptime_seconds // 86400
        hours = (uptime_seconds % 86400) // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
        
        return " ".join(parts)

async def setup(bot):
    # Set start time for uptime calculation
    import time
    bot.start_time = time.time()
    await bot.add_cog(Debug(bot))

