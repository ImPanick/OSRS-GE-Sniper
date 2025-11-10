# discord-bot/cogs/stats.py
import discord
from discord import app_commands
from discord.ext import commands
import json
import os

STATS_FILE = "data/profit_tracker.json"
if not os.path.exists("data"):
    os.makedirs("data")
if not os.path.exists(STATS_FILE):
    with open(STATS_FILE, "w") as f:
        json.dump({}, f)

class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profit", description="Log your flip profit")
    async def profit(self, interaction: discord.Interaction, gp: int):
        with open(STATS_FILE, 'r') as f:
            data = json.load(f)
        user = str(interaction.user.id)
        data[user] = data.get(user, 0) + gp
        with open(STATS_FILE, "w") as f:
            json.dump(data, f)
        await interaction.response.send_message(f"Logged +{gp/1e6:.1f}M GP! Total: {data[user]/1e6:.1f}M", ephemeral=True)

    @app_commands.command(name="leaderboard", description="Top flippers this week")
    async def leaderboard(self, interaction: discord.Interaction):
        with open(STATS_FILE, 'r') as f:
            data = json.load(f)
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)[:10]
        msg = "**CLAN FLIP LEADERBOARD**\n"
        for uid, gp in sorted_data:
            user = await self.bot.fetch_user(int(uid))
            msg += f"{user.name}: **{gp/1e6:.1f}M**\n"
        await interaction.response.send_message(msg)

async def setup(bot):
    await bot.add_cog(Stats(bot))