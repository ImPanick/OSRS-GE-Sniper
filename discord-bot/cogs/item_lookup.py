# discord-bot/cogs/item_lookup.py
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

class ItemLookup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="item", description="Look up an item by name or ID")
    @app_commands.describe(query="Item name or ID")
    async def item(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        
        try:
            # Try as ID first
            item_id = None
            try:
                item_id = int(query)
            except ValueError:
                pass
            
            if item_id:
                url = f"{CONFIG['backend_url']}/api/item/{item_id}"
            else:
                url = f"{CONFIG['backend_url']}/api/item/search?q={requests.utils.quote(query)}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 404:
                await interaction.followup.send(f"Item not found: `{query}`", ephemeral=True)
                return
            
            if response.status_code != 200:
                await interaction.followup.send(f"Error fetching item data: HTTP {response.status_code}", ephemeral=True)
                return
            
            data = response.json()
            
            # Handle multiple matches
            if 'matches' in data:
                matches = data.get('matches', [])[:10]
                if not matches:
                    await interaction.followup.send(f"No items found matching `{query}`", ephemeral=True)
                    return
                
                embed = Embed(
                    title=f"Search Results for: {query}",
                    description=f"Found {data.get('count', len(matches))} matches. Please be more specific.",
                    color=0x3498db
                )
                
                for match in matches:
                    name = match.get('name', 'Unknown')
                    item_id = match.get('id', 0)
                    embed.add_field(
                        name=f"{name} (ID: {item_id})",
                        value=f"Use `/item {item_id}` or `/item {name}`",
                        inline=False
                    )
                
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Single item result
            item_id = data.get('id', 0)
            item_name = data.get('name', 'Unknown')
            high = data.get('high') or data.get('sell')
            low = data.get('low') or data.get('buy')
            volume = data.get('volume', 0)
            max_buy_4h = data.get('max_buy_4h', 0) or data.get('limit', 0)
            opportunity = data.get('opportunity')
            
            # Build embed
            embed = Embed(
                title=f"📦 {item_name}",
                color=0x3498db,
                url=get_item_wiki_url(item_id)
            )
            
            # Add thumbnail
            thumbnail_url = get_item_thumbnail_url(item_name, item_id)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            
            # Add fields
            if high is not None and low is not None:
                embed.add_field(name="High / Low", value=f"{high:,} / {low:,} GP", inline=True)
            
            if volume:
                embed.add_field(name="Volume", value=f"{volume:,}", inline=True)
            
            if max_buy_4h:
                embed.add_field(name="Max Buy / 4h", value=f"{max_buy_4h:,}", inline=True)
            
            # Add opportunity info if available
            if opportunity:
                tier = opportunity.get('tier', '').capitalize()
                score = opportunity.get('score', 0)
                drop_pct = opportunity.get('drop_pct', 0)
                emoji = opportunity.get('emoji', '')
                embed.add_field(
                    name=f"{emoji} Current Opportunity",
                    value=f"**Tier:** {tier}\n**Score:** {score:.1f}\n**Drop %:** {drop_pct:.1f}%",
                    inline=False
                )
            
            embed.set_footer(text=f"ID: {item_id}")
            embed.timestamp = interaction.created_at
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"[ERROR] /item command failed: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"Error looking up item: {str(e)}", ephemeral=True)

    @app_commands.command(name="recipe", description="Get recipe information for an item")
    @app_commands.describe(item_name="Item name")
    async def recipe(self, interaction: discord.Interaction, item_name: str):
        await interaction.response.defer()
        
        try:
            url = f"{CONFIG['backend_url']}/api/recipe?name={requests.utils.quote(item_name)}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 404:
                await interaction.followup.send(f"Recipe not found for: `{item_name}`", ephemeral=True)
                return
            
            if response.status_code != 200:
                await interaction.followup.send(f"Error fetching recipe: HTTP {response.status_code}", ephemeral=True)
                return
            
            data = response.json()
            product = data.get('product', {})
            ingredients = data.get('ingredients', [])
            spread = data.get('spread', {})
            
            # Build embed
            product_name = product.get('name', item_name)
            product_id = product.get('id', 0)
            
            embed = Embed(
                title=f"📜 Recipe: {product_name}",
                color=0x9b59b6,
                url=get_item_wiki_url(product_id)
            )
            
            # Add product info
            product_high = product.get('high')
            product_low = product.get('low')
            product_max_buy = product.get('max_buy_4h', 0)
            
            product_info = []
            if product_high is not None and product_low is not None:
                product_info.append(f"**High / Low:** {product_high:,} / {product_low:,} GP")
            if product_max_buy:
                product_info.append(f"**Max Buy / 4h:** {product_max_buy:,}")
            
            if product_info:
                embed.add_field(
                    name="📦 Product",
                    value="\n".join(product_info),
                    inline=False
                )
            
            # Add ingredients
            if ingredients:
                ingredients_text = []
                for ing in ingredients:
                    ing_name = ing.get('name', 'Unknown')
                    ing_high = ing.get('high')
                    ing_low = ing.get('low')
                    ing_max_buy = ing.get('max_buy_4h', 0)
                    ing_qty = ing.get('quantity', 1)
                    
                    ing_line = f"**{ing_name}** (x{ing_qty})"
                    if ing_high is not None and ing_low is not None:
                        ing_line += f"\n  High/Low: {ing_high:,} / {ing_low:,} GP"
                    if ing_max_buy:
                        ing_line += f"\n  Max Buy/4h: {ing_max_buy:,}"
                    ingredients_text.append(ing_line)
                
                embed.add_field(
                    name="🧪 Ingredients",
                    value="\n\n".join(ingredients_text),
                    inline=False
                )
            else:
                embed.add_field(
                    name="🧪 Ingredients",
                    value="No recipe data available",
                    inline=False
                )
            
            # Add spread summary
            if spread:
                ing_total_high = spread.get('ingredient_total_high', 0)
                ing_total_low = spread.get('ingredient_total_low', 0)
                prod_high = spread.get('product_high', product_high)
                prod_low = spread.get('product_low', product_low)
                gp_per_unit_high = spread.get('gp_per_unit_high', 0)
                gp_per_unit_low = spread.get('gp_per_unit_low', 0)
                
                spread_text = []
                if ing_total_high and ing_total_low:
                    spread_text.append(f"**Ingredient Cost:** {ing_total_low:,} - {ing_total_high:,} GP")
                if prod_high and prod_low:
                    spread_text.append(f"**Product Value:** {prod_low:,} - {prod_high:,} GP")
                if gp_per_unit_high or gp_per_unit_low:
                    spread_text.append(f"**GP/Unit:** {gp_per_unit_low:,} - {gp_per_unit_high:,} GP")
                
                if spread_text:
                    embed.add_field(
                        name="💰 Profit Spread",
                        value="\n".join(spread_text),
                        inline=False
                    )
            
            embed.set_footer(text=f"Product ID: {product_id}")
            embed.timestamp = interaction.created_at
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"[ERROR] /recipe command failed: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"Error fetching recipe: {str(e)}", ephemeral=True)

    @app_commands.command(name="decant", description="Get decant information for a potion")
    @app_commands.describe(potion_name="Potion name (e.g., 'Prayer potion' or 'Prayer potion(4)')")
    async def decant(self, interaction: discord.Interaction, potion_name: str):
        await interaction.response.defer()
        
        try:
            url = f"{CONFIG['backend_url']}/api/decant?name={requests.utils.quote(potion_name)}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 404:
                await interaction.followup.send(f"No potion variants found for: `{potion_name}`", ephemeral=True)
                return
            
            if response.status_code != 200:
                await interaction.followup.send(f"Error fetching decant info: HTTP {response.status_code}", ephemeral=True)
                return
            
            data = response.json()
            base_name = data.get('base_name', potion_name)
            variants = data.get('variants', [])
            best_variant = data.get('best_gp_per_dose')
            
            if not variants:
                await interaction.followup.send(f"No potion variants found for: `{potion_name}`", ephemeral=True)
                return
            
            # Build embed
            embed = Embed(
                title=f"🧪 Decant: {base_name}",
                color=0xe74c3c,
                description=f"Comparing all dose variants"
            )
            
            # Add each variant
            for variant in variants:
                variant_name = variant.get('name', '')
                dose = variant.get('dose', 0)
                high = variant.get('high')
                low = variant.get('low')
                max_buy_4h = variant.get('max_buy_4h', 0)
                gp_per_dose_high = variant.get('gp_per_dose_high')
                gp_per_dose_low = variant.get('gp_per_dose_low')
                
                variant_text = []
                if high is not None and low is not None:
                    variant_text.append(f"**High / Low:** {high:,} / {low:,} GP")
                if max_buy_4h:
                    variant_text.append(f"**Max Buy / 4h:** {max_buy_4h:,}")
                if gp_per_dose_high is not None and gp_per_dose_low is not None:
                    variant_text.append(f"**GP/Dose:** {gp_per_dose_low:.1f} - {gp_per_dose_high:.1f} GP")
                
                # Mark best variant
                is_best = best_variant and variant.get('dose') == best_variant.get('dose')
                field_name = f"{'⭐ ' if is_best else ''}{variant_name} ({dose} dose)"
                
                embed.add_field(
                    name=field_name,
                    value="\n".join(variant_text) if variant_text else "No price data",
                    inline=True
                )
            
            # Add best variant note
            if best_variant:
                best_dose = best_variant.get('dose', 0)
                best_gp = best_variant.get('gp_per_dose_low', 0)
                embed.add_field(
                    name="💡 Best Value",
                    value=f"**{base_name}({best_dose})** has the best GP/dose at **{best_gp:.1f} GP/dose**",
                    inline=False
                )
            
            embed.set_footer(text=f"Base: {base_name}")
            embed.timestamp = interaction.created_at
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"[ERROR] /decant command failed: {e}")
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"Error fetching decant info: {str(e)}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(ItemLookup(bot))

