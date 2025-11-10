# discord-bot/cogs/config.py
import discord
from discord import app_commands, Embed
from discord.ext import commands
import json
import os

# Load config with fallback paths for Docker and local development
CONFIG_PATH = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(__file__), '..', '..', 'config.json'))
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')
CONFIG = json.load(open(CONFIG_PATH))

class Config(commands.Cog):
    @app_commands.command(name="sniper_config", description="Open web dashboard for this server")
    @app_commands.checks.has_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        backend_url = CONFIG.get('backend_url', 'http://localhost:5000')
        url = f"{backend_url}/config/{interaction.guild_id}"
        embed = Embed(title="SNIPER CONFIG DASHBOARD", description=f"[CLICK HERE TO CONFIGURE]({url})", color=0x00ff00)
        embed.set_footer(text="Per-server channels • High-alch • Recipe items • Billionaire flips")
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Config(bot))