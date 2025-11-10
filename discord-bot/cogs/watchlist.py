# discord-bot/cogs/watchlist.py
import discord
from discord import app_commands
from discord.ext import commands
import json, os

WATCH_FILE = "data/watchlist.json"

# Load config with fallback paths for Docker and local development
CONFIG_PATH = os.getenv('CONFIG_PATH', os.path.join(os.path.dirname(__file__), '..', '..', 'config.json'))
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'config.json')
if not os.path.exists(CONFIG_PATH):
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), '..', 'config.json')
CONFIG = json.load(open(CONFIG_PATH))

if not os.path.exists("data"): os.makedirs("data")
if not os.path.exists(WATCH_FILE):
    with open(WATCH_FILE, "w") as f: json.dump({}, f)

def load_watchlist(): 
    with open(WATCH_FILE) as f: return json.load(f)
def save_watchlist(data): 
    with open(WATCH_FILE, "w") as f: json.dump(data, f, indent=2)

class Watchlist(commands.Cog):
    def __init__(self, bot): self.bot = bot

    @app_commands.command(name="watch", description="Get DMs when item dumps or pumps")
    async def watch(self, interaction: discord.Interaction, item_name: str):
        data = load_watchlist()
        user_id = str(interaction.user.id)
        if user_id not in data: data[user_id] = []
        if item_name.lower() not in [i.lower() for i in data[user_id]]:
            data[user_id].append(item_name)
            save_watchlist(data)
            await interaction.response.send_message(f"Now watching **{item_name}** — I'll DM you on 30%+ moves", ephemeral=True)
        else:
            await interaction.response.send_message(f"Already watching **{item_name}**", ephemeral=True)

    @app_commands.command(name="unwatch", description="Stop watching an item")
    async def unwatch(self, interaction: discord.Interaction, item_name: str):
        data = load_watchlist()
        user_id = str(interaction.user.id)
        if user_id in data and item_name.lower() in [i.lower() for i in data[user_id]]:
            data[user_id] = [i for i in data[user_id] if i.lower() != item_name.lower()]
            save_watchlist(data)
            await interaction.response.send_message(f"Stopped watching **{item_name}**", ephemeral=True)

    @app_commands.command(name="watching", description="Your watchlist")
    async def watching(self, interaction: discord.Interaction):
        data = load_watchlist()
        items = data.get(str(interaction.user.id), [])
        await interaction.response.send_message(f"You're watching: {', '.join(items) or 'nothing'}", ephemeral=True)

async def setup(bot): await bot.add_cog(Watchlist(bot))