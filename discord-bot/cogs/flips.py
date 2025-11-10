# discord-bot/cogs/flips.py
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

class Flips(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="flips", description="Top flips right now")
    async def flips(self, interaction: discord.Interaction, min_gp: int = 2_000_000):
        data = requests.get(f"{CONFIG['backend_url']}/api/top", timeout=30).json()
        data = [d for d in data if d['profit'] >= min_gp]
        embed = discord.Embed(title=f"Top Flips >{min_gp/1e6:.0f}M", color=0x00ff00)
        
        for item in data[:10]:
            embed.add_field(name=item['name'],
                value=f"Buy {item['buy']:,} → Sell {item['sell']:,}\nProfit **{item['profit']/1e6:.1f}M**",
                inline=False)
        
        # Set thumbnail for the first (top) flip item
        if data:
            top_item = data[0]
            thumbnail_url = get_item_thumbnail_url(top_item.get('name', ''), top_item.get('id', 0))
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            embed.url = get_item_wiki_url(top_item.get('id', 0))
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

async def setup(bot):
    await bot.add_cog(Flips(bot))