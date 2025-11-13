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
        await interaction.response.defer()
        
        try:
            data = requests.get(f"{CONFIG['backend_url']}/api/dumps", timeout=30).json() or []
            if not data:
                await interaction.followup.send("Market stable. No panic. Yet.", ephemeral=True)
                return

            # Sort by score (highest first) - new tier system
            sorted_dumps = sorted(data, key=lambda x: x.get('score', 0), reverse=True)

            embed = Embed(
                title="💎 TIERED DUMP OPPORTUNITIES",
                description="**INSTANT BUY SIGNALS** — Sorted by *Quality Score*",
                color=0x8B0000  # Blood red
            )

            for item in sorted_dumps[:8]:
                name = item.get('name', 'Unknown')
                tier = item.get('tier', '').capitalize()
                emoji = item.get('emoji', '')
                score = item.get('score', 0)
                drop = item.get('drop_pct', 0)
                vol_spike = item.get('vol_spike_pct', 0)
                oversupply = item.get('oversupply_pct', 0)
                price = item.get('low', 0) or item.get('buy', 0)
                high = item.get('high', 0) or item.get('sell', 0)
                vol = item.get('volume', 0)
                max_buy_4h = item.get('max_buy_4h', 0) or item.get('limit', 0)
                flags = item.get('flags', [])

                # Build title with tier
                title = f"{emoji} **{tier}** {name} — {drop:.1f}% DROP"

                # Build value with all metrics
                value_parts = [
                    f"**Score:** {score:.1f} | **Tier:** {tier}",
                    f"**Drop %:** {drop:.1f}% | **Vol Spike %:** {vol_spike:.1f}% | **Oversupply %:** {oversupply:.1f}%",
                    f"**Buy / Sell:** {price:,} / {high:,} GP",
                    f"**Volume:** {vol:,} | **Max Buy / 4h:** {max_buy_4h:,}",
                ]
                
                # Add flags
                if flags:
                    flag_labels = []
                    if 'slow_buy' in flags:
                        flag_labels.append("Slow Buy")
                    if 'one_gp_dump' in flags:
                        flag_labels.append("1GP")
                    if 'super' in flags:
                        flag_labels.append("Super")
                    if flag_labels:
                        value_parts.append(f"**Flags:** {', '.join(flag_labels)}")

                value = "\n".join(value_parts)
                embed.add_field(name=title, value=value, inline=False)
            
            # Set thumbnail for the first (top) dump item
            if sorted_dumps:
                top_item = sorted_dumps[0]
                thumbnail_url = get_item_thumbnail_url(top_item.get('name', ''), top_item.get('id', 0) or top_item.get('item_id', 0))
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)

            embed.set_footer(text=
                "TIER GUIDE:\n"
                "🔩 Iron (0-10) • 🪙 Copper (11-20) • 🏅 Bronze (21-30) • 🥈 Silver (31-40) • 🥇 Gold (41-50)\n"
                "⚪ Platinum (51-60) • 💎🔴 Ruby (61-70) • 💎🔵 Sapphire (71-80) • 💎🟢 Emerald (81-90) • 💎 Diamond (91-100)"
            )
            embed.timestamp = interaction.created_at

            await interaction.followup.send(embed=embed)
        except Exception as e:
            print(f"[ERROR] /dip command failed: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"Error fetching dumps: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Dumps(bot))