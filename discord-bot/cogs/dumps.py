# discord-bot/cogs/dumps.py
import discord
from discord import app_commands, Embed
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

class Dumps(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="dip", description="GOD-TIER DUMP SNIPER — BUY THE PANIC")
    async def dip(self, interaction: discord.Interaction):
        data = requests.get(f"{CONFIG['backend_url']}/api/dumps", timeout=30).json()
        if not data:
            await interaction.response.send_message("Market stable. No panic. Yet.", ephemeral=True)
            return

        # Sort by pure destruction power
        sorted_dumps = sorted(data, key=lambda x: x.get('volume', 0) * x.get('drop_pct', 0), reverse=True)

        embed = Embed(
            title="DUMP DETECTED — WHALES ARE BLEEDING",
            description="**INSTANT BUY SIGNALS** — Sorted by *Volume × Crash Intensity*",
            color=0x8B0000  # Blood red
        )

        for item in sorted_dumps[:8]:
            name = item['name']
            drop = item['drop_pct']
            price = item['buy']
            vol = item['volume']
            insta_buy = item.get('insta_buy', 0)
            insta_sell = item.get('insta_sell', 0)
            quality = item.get('quality', '')
            label = item.get('quality_label', '')

            # NUCLEAR TITLE
            title = f"{quality} **{name}** — {drop:.1f}% CRASH"

            # REAL PROFIT CALC
            realistic_profit = price * 0.99 - item.get('cost_per_limit', price)
            max_profit = price * 4 * 0.99  # 4h limit flip

            value = (
                f"**BUY NOW @{price:,} GP** | Vol: **{vol:,}**\n"
                f"**Max Profit:** {max_profit/1e6:.1f}M gp | **Realistic:** {realistic_profit/1e6:.1f}M gp\n"
                f"**Insta Buy:** {insta_buy:,} | **Insta Sell:** {insta_sell:,} (Live)\n"
                f"**Limit:** {item.get('limit', 0):,} | **Tax:** 1%\n"
                f"`{label}`"
            )

            embed.add_field(name=title, value=value, inline=False)
        
        # Set thumbnail for the first (top) dump item
        if sorted_dumps:
            top_item = sorted_dumps[0]
            thumbnail_url = get_item_thumbnail_url(top_item.get('name', ''), top_item.get('id', 0))
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)

        embed.set_footer(text=
            "QUALITY GUIDE:\n"
            "⭐ = Good • ⭐⭐⭐ = Premium • ⭐⭐⭐⭐⭐ = GOD-TIER\n"
            "NUCLEAR DUMP = 1.5M+ items dumped — WHALE PANIC SELLING\n"
            "Built by the ImPanicking — Nov 10 2025"
        )
        embed.timestamp = interaction.created_at

        await interaction.response.send_message(embed=embed)

async def setup(bot):
    await bot.add_cog(Dumps(bot))