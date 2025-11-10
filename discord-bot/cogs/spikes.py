# discord-bot/cogs/spikes.py
import discord
from discord import app_commands
from discord.ext import commands
import requests
import json
import sys
import os

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.item_utils import get_item_thumbnail_url, get_item_wiki_url

# Load config with fallback paths for Docker and local development
CONFIG_PATH = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(__file__), '..', '..', 'config.json'))
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')
with open(CONFIG_PATH, 'r') as f:
    CONFIG = json.load(f)

class Spikes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="pump", description="Price spikes — SELL!")
    async def pump(self, interaction: discord.Interaction):
        data = requests.get(f"{CONFIG['backend_url']}/api/spikes", timeout=30).json()
        embed = discord.Embed(title="SPIKE ALERTS — SELL NOW", color=0x00ff00)
        
        for item in data[:8]:
            item_name = item.get('name', 'Unknown')
            embed.add_field(name=f"{item_name} +{item.get('rise_pct', 0):.1f}%",
                value=f"Now: {item.get('sell', 0):,} GP | Vol: {item.get('volume', 0):,}", inline=False)
        
        # Set thumbnail for the first (top) spike item
        if data:
            top_item = data[0]
            thumbnail_url = get_item_thumbnail_url(top_item.get('name', ''), top_item.get('id', 0))
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            embed.url = get_item_wiki_url(top_item.get('id', 0))
        
        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Spikes(bot))