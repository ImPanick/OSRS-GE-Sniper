# discord-bot/cogs/config.py
import discord
from discord import app_commands, Embed
from discord.ext import commands
import requests
import json
import os

# Load config with fallback paths for Docker and local development
CONFIG_PATH = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(__file__), '..', '..', 'config.json'))
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')
with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

class Config(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="sniper_config", description="Open web dashboard for this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        backend_url = CONFIG.get('backend_url', 'http://localhost:5000')
        url = f"{backend_url}/config/{interaction.guild_id}"
        embed = Embed(title="SNIPER CONFIG DASHBOARD", description=f"[CLICK HERE TO CONFIGURE]({url})", color=0x00ff00)
        embed.set_footer(text="Per-server channels • High-alch • Recipe items • Billionaire flips")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="tiers", description="Show tier definitions and role mappings for this server")
    async def tiers(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild.id) if interaction.guild else None
        if not guild_id:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        try:
            # Fetch tier configuration from backend
            response = requests.get(
                f"{CONFIG['backend_url']}/api/tiers?guild_id={guild_id}",
                timeout=10
            )
            
            if response.status_code == 200:
                tier_data = response.json()
                tiers = tier_data.get('tiers', [])
                min_tier_name = tier_data.get('min_tier_name')
                
                if not tiers:
                    await interaction.followup.send("No tier configuration found.", ephemeral=True)
                    return
                
                # Build embed
                embed = Embed(
                    title="⚔️ Tier System",
                    description="Dump quality tiers mapped to score ranges. Alerts are sent based on tier configuration.",
                    color=0x9b59b6
                )
                
                # Group tiers by group (metals vs gems)
                metals = [t for t in tiers if t.get('group', '').lower() == 'metals']
                gems = [t for t in tiers if t.get('group', '').lower() == 'gems']
                
                # Add metals section
                if metals:
                    metals_text = []
                    for tier in sorted(metals, key=lambda x: x.get('min_score', 0)):
                        name = tier.get('name', '').capitalize()
                        emoji = tier.get('emoji', '')
                        min_score = tier.get('min_score', 0)
                        max_score = tier.get('max_score', 100)
                        role_id = tier.get('role_id')
                        enabled = tier.get('enabled', True)
                        
                        role_mention = ""
                        if role_id:
                            try:
                                role = interaction.guild.get_role(int(role_id))
                                if role:
                                    role_mention = f" → {role.mention}"
                            except (ValueError, TypeError):
                                role_mention = f" → Role ID: {role_id}"
                        
                        status = "✅" if enabled else "❌"
                        metals_text.append(
                            f"{status} {emoji} **{name}** ({min_score}-{max_score}){role_mention}"
                        )
                    
                    embed.add_field(
                        name="🔩 Metals",
                        value="\n".join(metals_text) if metals_text else "None",
                        inline=False
                    )
                
                # Add gems section
                if gems:
                    gems_text = []
                    for tier in sorted(gems, key=lambda x: x.get('min_score', 0)):
                        name = tier.get('name', '').capitalize()
                        emoji = tier.get('emoji', '')
                        min_score = tier.get('min_score', 0)
                        max_score = tier.get('max_score', 100)
                        role_id = tier.get('role_id')
                        enabled = tier.get('enabled', True)
                        
                        role_mention = ""
                        if role_id:
                            try:
                                role = interaction.guild.get_role(int(role_id))
                                if role:
                                    role_mention = f" → {role.mention}"
                            except (ValueError, TypeError):
                                role_mention = f" → Role ID: {role_id}"
                        
                        status = "✅" if enabled else "❌"
                        gems_text.append(
                            f"{status} {emoji} **{name}** ({min_score}-{max_score}){role_mention}"
                        )
                    
                    embed.add_field(
                        name="💎 Gems",
                        value="\n".join(gems_text) if gems_text else "None",
                        inline=False
                    )
                
                # Add minimum tier restriction if configured
                if min_tier_name:
                    embed.add_field(
                        name="⚙️ Minimum Tier",
                        value=f"Only alerts for **{min_tier_name.capitalize()}** and above are sent.",
                        inline=False
                    )
                
                embed.set_footer(text="Configure tiers and roles in the web dashboard: /sniper_config")
                embed.timestamp = interaction.created_at
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                error_data = response.json() if response.content else {}
                await interaction.followup.send(f"Error: {error_data.get('error', f'HTTP {response.status_code}')}", ephemeral=True)
        except Exception as e:
            print(f"[ERROR] /tiers command failed: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"Error fetching tier information: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Config(bot))