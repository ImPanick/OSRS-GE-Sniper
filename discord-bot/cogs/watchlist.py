# discord-bot/cogs/watchlist.py
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

class Watchlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _resolve_item_name(self, item_name: str):
        """Resolve item name to item ID using backend API"""
        try:
            url = f"{CONFIG['backend_url']}/api/item/search?q={requests.utils.quote(item_name)}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                matches = response.json()
                if not matches:
                    return None, None
                
                # Find exact match first (case-insensitive)
                for match in matches:
                    if match.get('name', '').lower() == item_name.lower():
                        return match.get('id'), match.get('name')
                
                # Return first match if no exact match
                if matches:
                    return matches[0].get('id'), matches[0].get('name')
        except Exception as e:
            print(f"[ERROR] Failed to resolve item name '{item_name}': {e}")
        
        return None, None

    @app_commands.command(name="watch", description="Add an item to your watchlist (guild-level)")
    @app_commands.describe(item="Item name or ID")
    async def watch(self, interaction: discord.Interaction, item: str):
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild.id) if interaction.guild else None
        if not guild_id:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        # Try to resolve item name to ID
        item_id = None
        item_name = None
        
        # Try as ID first
        try:
            item_id = int(item)
            # Fetch item name from backend
            item_response = requests.get(f"{CONFIG['backend_url']}/api/item/{item_id}", timeout=10)
            if item_response.status_code == 200:
                item_data = item_response.json()
                item_name = item_data.get('name', f'Item {item_id}')
        except ValueError:
            # Not an ID, try to resolve by name
            item_id, item_name = await self._resolve_item_name(item)
        
        if not item_id:
            await interaction.followup.send(f"Item not found: `{item}`\n\nTry using `/item` to search for items.", ephemeral=True)
            return
        
        # Add to watchlist via backend API
        try:
            response = requests.post(
                f"{CONFIG['backend_url']}/api/watchlist/add",
                json={
                    "guild_id": guild_id,
                    "user_id": str(interaction.user.id),
                    "item_id": item_id,
                    "item_name": item_name
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    await interaction.followup.send(
                        f"✅ Now watching **{item_name}** (ID: {item_id})\n\n"
                        f"You'll receive alerts when this item appears in dump opportunities.",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send(f"Failed to add item to watchlist: {data.get('error', 'Unknown error')}", ephemeral=True)
            else:
                error_data = response.json() if response.content else {}
                await interaction.followup.send(f"Error: {error_data.get('error', f'HTTP {response.status_code}')}", ephemeral=True)
        except Exception as e:
            print(f"[ERROR] /watch command failed: {e}")
            await interaction.followup.send(f"Error adding item to watchlist: {str(e)}", ephemeral=True)

    @app_commands.command(name="unwatch", description="Remove an item from your watchlist")
    @app_commands.describe(item="Item name or ID")
    async def unwatch(self, interaction: discord.Interaction, item: str):
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild.id) if interaction.guild else None
        if not guild_id:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        # Try to resolve item name to ID
        item_id = None
        
        # Try as ID first
        try:
            item_id = int(item)
        except ValueError:
            # Not an ID, try to resolve by name
            item_id, _ = await self._resolve_item_name(item)
        
        if not item_id:
            await interaction.followup.send(f"Item not found: `{item}`", ephemeral=True)
            return
        
        # Remove from watchlist via backend API
        try:
            response = requests.post(
                f"{CONFIG['backend_url']}/api/watchlist/remove",
                json={
                    "guild_id": guild_id,
                    "user_id": str(interaction.user.id),
                    "item_id": item_id
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    await interaction.followup.send(f"✅ Removed item (ID: {item_id}) from watchlist", ephemeral=True)
                else:
                    await interaction.followup.send(f"Failed to remove item: {data.get('error', 'Unknown error')}", ephemeral=True)
            else:
                error_data = response.json() if response.content else {}
                await interaction.followup.send(f"Error: {error_data.get('error', f'HTTP {response.status_code}')}", ephemeral=True)
        except Exception as e:
            print(f"[ERROR] /unwatch command failed: {e}")
            await interaction.followup.send(f"Error removing item from watchlist: {str(e)}", ephemeral=True)

    @app_commands.command(name="watching", description="List items in your watchlist")
    async def watching(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        guild_id = str(interaction.guild.id) if interaction.guild else None
        if not guild_id:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return
        
        # Get watchlist from backend API
        try:
            response = requests.get(
                f"{CONFIG['backend_url']}/api/watchlist?guild_id={guild_id}&user_id={str(interaction.user.id)}",
                timeout=10
            )
            
            if response.status_code == 200:
                watchlist = response.json()
                
                if not watchlist:
                    await interaction.followup.send("Your watchlist is empty. Use `/watch <item>` to add items.", ephemeral=True)
                    return
                
                # Build embed
                embed = Embed(
                    title="📋 Your Watchlist",
                    description=f"You're watching {len(watchlist)} item(s):",
                    color=0x3498db
                )
                
                # Add items (limit to 25 for Discord embed limits)
                items_text = []
                for item in watchlist[:25]:
                    item_id = item.get('item_id', 0)
                    item_name = item.get('item_name', f'Item {item_id}')
                    items_text.append(f"• **{item_name}** (ID: {item_id})")
                
                if items_text:
                    embed.add_field(
                        name="Items",
                        value="\n".join(items_text),
                        inline=False
                    )
                
                if len(watchlist) > 25:
                    embed.set_footer(text=f"Showing first 25 of {len(watchlist)} items")
                
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                error_data = response.json() if response.content else {}
                await interaction.followup.send(f"Error: {error_data.get('error', f'HTTP {response.status_code}')}", ephemeral=True)
        except Exception as e:
            print(f"[ERROR] /watching command failed: {e}")
            await interaction.followup.send(f"Error fetching watchlist: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Watchlist(bot))
