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
            
            # Use enhanced API endpoint that supports both ID and name
            if item_id:
                url = f"{CONFIG['backend_url']}/api/item/{item_id}"
            else:
                url = f"{CONFIG['backend_url']}/api/item?name={requests.utils.quote(query)}"
            
            response = requests.get(url, timeout=10)
            
            if response.status_code == 404:
                # Try search endpoint as fallback for multiple matches
                search_url = f"{CONFIG['backend_url']}/api/item/search?q={requests.utils.quote(query)}"
                search_response = requests.get(search_url, timeout=10)
                
                if search_response.status_code == 200:
                    matches = search_response.json()
                    if isinstance(matches, list) and len(matches) > 0:
                        embed = Embed(
                            title=f"Search Results for: {query}",
                            description=f"Found {len(matches)} matches. Please be more specific or use an ID.",
                            color=0x3498db
                        )
                        
                        for match in matches[:10]:
                            name = match.get('name', 'Unknown')
                            match_id = match.get('id', 0)
                            embed.add_field(
                                name=f"{name} (ID: {match_id})",
                                value=f"Use `/item {match_id}` or `/item {name}`",
                                inline=False
                            )
                        
                        await interaction.followup.send(embed=embed, ephemeral=True)
                        return
                
                await interaction.followup.send(f"Item not found: `{query}`", ephemeral=True)
                return
            
            if response.status_code != 200:
                await interaction.followup.send(f"Error fetching item data: HTTP {response.status_code}", ephemeral=True)
                return
            
            data = response.json()
            
            # Single item result
            item_id = data.get('id', 0)
            item_name = data.get('name', 'Unknown')
            examine = data.get('examine', '')
            members = data.get('members', True)
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
            
            # Add description with examine text if available
            if examine:
                embed.description = examine[:200]  # Limit length
            
            # Add thumbnail
            thumbnail_url = get_item_thumbnail_url(item_name, item_id)
            if thumbnail_url:
                embed.set_thumbnail(url=thumbnail_url)
            
            # Add price fields
            price_info = []
            if high is not None and low is not None:
                price_info.append(f"**High / Low:** {high:,} / {low:,} GP")
            
            if volume:
                price_info.append(f"**Volume:** {volume:,}")
            
            if max_buy_4h:
                price_info.append(f"**Max Buy / 4h:** {max_buy_4h:,}")
            
            if price_info:
                embed.add_field(
                    name="💰 Price Information",
                    value="\n".join(price_info),
                    inline=False
                )
            
            # Add opportunity info if available (dump detection)
            if opportunity:
                tier = opportunity.get('tier', '').capitalize()
                score = opportunity.get('score', 0)
                drop_pct = opportunity.get('drop_pct', 0)
                vol_spike_pct = opportunity.get('vol_spike_pct', 0)
                oversupply_pct = opportunity.get('oversupply_pct', 0)
                emoji = opportunity.get('emoji', '')
                flags = opportunity.get('flags', [])
                
                opp_text = []
                opp_text.append(f"**Tier:** {emoji} {tier} (Score: {score:.1f})")
                opp_text.append(f"**Drop %:** -{drop_pct:.1f}%")
                
                if vol_spike_pct > 0:
                    opp_text.append(f"**Volume Spike:** +{vol_spike_pct:.1f}%")
                
                if oversupply_pct > 0:
                    opp_text.append(f"**Oversupply:** {oversupply_pct:.1f}%")
                
                if flags:
                    flag_labels = []
                    if 'slow_buy' in flags:
                        flag_labels.append("Slow Buy")
                    if 'one_gp_dump' in flags:
                        flag_labels.append("1GP Dump")
                    if 'super' in flags:
                        flag_labels.append("Super Tier")
                    if flag_labels:
                        opp_text.append(f"**Flags:** {', '.join(flag_labels)}")
                
                embed.add_field(
                    name=f"{emoji} Current Dump Opportunity",
                    value="\n".join(opp_text),
                    inline=False
                )
                
                # Change embed color to indicate dump opportunity
                embed.color = 0xff6b6b  # Red for dump opportunity
            
            # Add members flag
            if not members:
                embed.add_field(
                    name="ℹ️ Note",
                    value="Free-to-play item",
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
            spread_info = data.get('spread_info', {})
            
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
            
            # Add ingredients with costs
            if ingredients:
                ingredients_text = []
                for ing in ingredients:
                    ing_name = ing.get('name', 'Unknown')
                    ing_high = ing.get('high')
                    ing_low = ing.get('low')
                    ing_max_buy = ing.get('max_buy_4h', 0)
                    ing_qty = ing.get('quantity', 1)
                    ing_cost_low = ing.get('cost_low', 0)
                    ing_cost_high = ing.get('cost_high', 0)
                    
                    ing_line = f"**{ing_name}** (x{ing_qty})"
                    if ing_high is not None and ing_low is not None:
                        ing_line += f"\n  Price: {ing_low:,} - {ing_high:,} GP"
                        if ing_cost_low > 0 or ing_cost_high > 0:
                            ing_line += f"\n  Total Cost: {ing_cost_low:,} - {ing_cost_high:,} GP"
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
            
            # Add profit calculations
            if spread_info:
                total_cost_low = spread_info.get('total_ingredient_cost_low', 0)
                total_cost_high = spread_info.get('total_ingredient_cost_high', 0)
                profit_best = spread_info.get('profit_best', 0)
                profit_best_pct = spread_info.get('profit_best_pct', 0)
                profit_worst = spread_info.get('profit_worst', 0)
                profit_worst_pct = spread_info.get('profit_worst_pct', 0)
                profit_avg = spread_info.get('profit_avg', 0)
                profit_avg_pct = spread_info.get('profit_avg_pct', 0)
                profit_per_limit = spread_info.get('profit_per_limit')
                
                profit_text = []
                
                # Total ingredient cost
                if total_cost_low > 0 or total_cost_high > 0:
                    profit_text.append(f"**Total Ingredient Cost:** {total_cost_low:,} - {total_cost_high:,} GP")
                
                # Profit scenarios
                if profit_best is not None:
                    profit_text.append(f"**Best Case:** +{profit_best:,} GP ({profit_best_pct:+.1f}%)")
                    profit_text.append(f"  *Buy ingredients low, sell product high*")
                
                if profit_worst is not None:
                    profit_text.append(f"**Worst Case:** {profit_worst:,} GP ({profit_worst_pct:+.1f}%)")
                    profit_text.append(f"  *Buy ingredients high, sell product low*")
                
                if profit_avg is not None:
                    profit_text.append(f"**Average:** {profit_avg:,} GP ({profit_avg_pct:+.1f}%)")
                
                # Profit per 4-hour limit
                if profit_per_limit is not None:
                    profit_text.append(f"**Profit per 4h Limit:** {profit_per_limit:,.0f} GP")
                
                if profit_text:
                    embed.add_field(
                        name="💰 Profit Analysis",
                        value="\n".join(profit_text),
                        inline=False
                    )
                    
                    # Change color based on profitability
                    if profit_avg and profit_avg > 0:
                        embed.color = 0x2ecc71  # Green for profitable
                    elif profit_avg and profit_avg < 0:
                        embed.color = 0xe74c3c  # Red for loss
            
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
                description=f"Comparing all dose variants by GP per dose"
            )
            
            # Add each variant
            for variant in variants:
                variant_name = variant.get('name', '')
                high = variant.get('high')
                low = variant.get('low')
                max_buy_4h = variant.get('max_buy_4h', 0)
                gp_per_dose_high = variant.get('gp_per_dose_high')
                gp_per_dose_low = variant.get('gp_per_dose_low')
                
                # Check if this is the best variant
                is_best = best_variant and variant.get('dose') == best_variant.get('dose')
                
                variant_text = []
                if high is not None and low is not None:
                    variant_text.append(f"**Price:** {high:,} / {low:,} GP")
                if max_buy_4h:
                    variant_text.append(f"**Max Buy / 4h:** {max_buy_4h:,}")
                if gp_per_dose_high is not None and gp_per_dose_low is not None:
                    gp_text = f"**GP/Dose:** {gp_per_dose_low:.2f} - {gp_per_dose_high:.2f} GP"
                    if is_best:
                        gp_text = f"⭐ {gp_text} ⭐"
                    variant_text.append(gp_text)
                
                # Mark best variant with star emoji
                field_name = f"{'⭐ ' if is_best else ''}{variant_name}"
                if is_best:
                    field_name = f"⭐ **{variant_name}** ⭐ (Best Value)"
                
                embed.add_field(
                    name=field_name,
                    value="\n".join(variant_text) if variant_text else "No price data",
                    inline=True
                )
            
            # Add best variant summary
            if best_variant:
                best_dose = best_variant.get('dose', 0)
                best_gp_low = best_variant.get('gp_per_dose_low', 0)
                best_gp_high = best_variant.get('gp_per_dose_high', 0)
                best_name = best_variant.get('name', f'{base_name}({best_dose})')
                
                summary_text = []
                summary_text.append(f"**{best_name}** offers the best value!")
                summary_text.append(f"**GP/Dose:** {best_gp_low:.2f} - {best_gp_high:.2f} GP")
                
                best_max_buy = best_variant.get('max_buy_4h', 0)
                if best_max_buy > 0:
                    total_doses = best_dose * best_max_buy
                    summary_text.append(f"**Max Doses / 4h:** {total_doses:,} (via {best_max_buy:,} pots)")
                
                embed.add_field(
                    name="💡 Best Value Recommendation",
                    value="\n".join(summary_text),
                    inline=False
                )
                
                # Change color to green for best value
                embed.color = 0x2ecc71
            
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

