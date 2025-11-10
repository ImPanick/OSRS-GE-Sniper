# discord-bot/cogs/nightly.py
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

class Nightly(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="nightly", description="Best overnight flip opportunities (8-16 hour predictions)")
    async def nightly(self, interaction: discord.Interaction, min_profit: int = 1_000_000):
        """Get recommendations for overnight flips with high profit potential"""
        await interaction.response.defer()
        
        try:
            # Get overnight recommendations from backend
            response = requests.get(
                f"{CONFIG['backend_url']}/api/nightly",
                params={"min_profit": min_profit},
                timeout=30
            )
            
            if response.status_code != 200:
                await interaction.followup.send(
                    "❌ Failed to fetch overnight recommendations. Please try again later.",
                    ephemeral=True
                )
                return
            
            data = response.json()
            
            if not data or len(data) == 0:
                await interaction.followup.send(
                    f"🔍 No overnight flip opportunities found with minimum profit of {min_profit:,} GP.\n"
                    f"Try lowering the minimum profit or check back later.",
                    ephemeral=False
                )
                return
            
            # Create embed with top recommendations
            embed = discord.Embed(
                title="🌙 Overnight Flip Recommendations",
                description=f"**Best opportunities for 8-16 hour holds**\n"
                          f"Minimum profit: {min_profit:,} GP\n"
                          f"*These items show strong potential for overnight price recovery or growth*",
                color=0x4B0082  # Indigo color for night theme
            )
            
            # Add top 5 recommendations
            for i, item in enumerate(data[:5], 1):
                item_name = item.get('name', 'Unknown')
                item_id = item.get('id', 0)
                
                buy_price = item.get('buy', 0)
                sell_price = item.get('sell', buy_price)
                insta_buy = item.get('insta_buy', buy_price)
                insta_sell = item.get('insta_sell', sell_price)
                
                # Overnight profit prediction
                overnight_profit = item.get('overnight_profit', 0)
                overnight_roi = item.get('overnight_roi', 0)
                confidence = item.get('overnight_confidence', 0)
                
                # Price historicals
                avg_24h = item.get('avg_24h')
                avg_12h = item.get('avg_12h')
                avg_6h = item.get('avg_6h')
                
                # Risk metrics
                risk_score = item.get('risk_score', 0)
                risk_level = item.get('risk_level', 'UNKNOWN')
                liquidity_score = item.get('liquidity_score', 0)
                
                # Build field value
                field_value = f"**Buy:** {buy_price:,} GP → **Sell:** {sell_price:,} GP\n"
                
                if insta_buy != buy_price or insta_sell != sell_price:
                    field_value += f"⚡ Insta: {insta_buy:,} / {insta_sell:,} GP\n"
                
                field_value += f"\n💰 **Overnight Profit:** {overnight_profit:,} GP ({overnight_roi:.1f}% ROI)\n"
                field_value += f"📊 **Confidence:** {confidence:.1f}%\n"
                field_value += f"⚠️ **Risk:** {risk_level} ({risk_score:.1f}/100)\n"
                field_value += f"💧 **Liquidity:** {liquidity_score:.1f}%\n"
                
                # Add historicals if available
                if avg_24h or avg_12h or avg_6h:
                    field_value += f"\n📈 **Historicals:** "
                    if avg_24h:
                        field_value += f"24h: {avg_24h:,} | "
                    if avg_12h:
                        field_value += f"12h: {avg_12h:,} | "
                    if avg_6h:
                        field_value += f"6h: {avg_6h:,}"
                
                # Add volume and limit info
                volume = item.get('volume', 0)
                limit = item.get('limit', 0)
                if limit > 0:
                    field_value += f"\n📦 **Volume:** {volume:,} | **Limit:** {limit:,}"
                
                # Add reasoning
                reasoning = item.get('reasoning', '')
                if reasoning:
                    field_value += f"\n\n💡 **Why:** {reasoning}"
                
                embed.add_field(
                    name=f"{i}. {item_name}",
                    value=field_value,
                    inline=False
                )
            
            # Set thumbnail for the top recommendation
            if data:
                top_item = data[0]
                thumbnail_url = get_item_thumbnail_url(top_item.get('name', ''), top_item.get('id', 0))
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                embed.url = get_item_wiki_url(top_item.get('id', 0))
            
            # Add footer with disclaimer
            embed.set_footer(
                text="⚠️ Overnight predictions are estimates based on historical patterns. "
                     "Always do your own research before investing."
            )
            
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except requests.exceptions.Timeout:
            await interaction.followup.send(
                "⏱️ Request timed out. Please try again later.",
                ephemeral=True
            )
        except Exception as e:
            print(f"[ERROR] nightly command: {e}")
            await interaction.followup.send(
                "❌ An error occurred while fetching overnight recommendations.",
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(Nightly(bot))

