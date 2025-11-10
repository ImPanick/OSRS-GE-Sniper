import discord
from discord.ext import commands, tasks
import requests, json, asyncio

CONFIG = json.load(open('../config.json'))
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"{bot.user} ONLINE")
    for filename in ["flips", "dumps", "spikes", "watchlist", "stats", "config"]:
        await bot.load_extension(f"cogs.{filename}")
    poll_alerts.start()

@tasks.loop(seconds=20)
async def poll_alerts():
    """Poll backend and route notifications to per-server channels"""
    try:
        # Get latest data
        dumps = requests.get(f"{CONFIG['backend_url']}/api/dumps", timeout=5).json() or []
        spikes = requests.get(f"{CONFIG['backend_url']}/api/spikes", timeout=5).json() or []
        flips = requests.get(f"{CONFIG['backend_url']}/api/top", timeout=5).json() or []
        
        # Import router
        from utils.notification_router import broadcast_to_all_servers
        
        # Broadcast dumps
        if dumps:
            from utils.item_utils import get_item_thumbnail_url, get_item_wiki_url
            
            def dump_embed(item):
                item_name = item.get('name', 'Unknown')
                item_id = item.get('id', 0)
                thumbnail_url = get_item_thumbnail_url(item_name, item_id)
                
                buy_price = item.get('buy', 0)
                sell_price = item.get('sell', buy_price)
                insta_buy = item.get('insta_buy', buy_price)
                insta_sell = item.get('insta_sell', sell_price)
                
                # Build price description
                price_desc = f"Buy: {buy_price:,} GP → Sell: {sell_price:,} GP"
                if insta_buy != buy_price or insta_sell != sell_price:
                    price_desc += f"\n⚡ Insta Buy: {insta_buy:,} GP | Insta Sell: {insta_sell:,} GP"
                
                # Add risk metrics
                risk_score = item.get('risk_score', 0)
                risk_level = item.get('risk_level', 'UNKNOWN')
                profitability_confidence = item.get('profitability_confidence', 0)
                
                risk_info = f"\n⚠️ **Risk:** {risk_level} ({risk_score:.1f}/100) | **Confidence:** {profitability_confidence:.1f}%"
                
                embed = discord.Embed(
                    title=f"🔥 DUMP: {item_name}",
                    description=f"**{item.get('drop_pct', 0):.1f}% DROP**\n"
                              f"{price_desc}\n"
                              f"Vol: {item.get('volume', 0):,}\n"
                              f"{item.get('quality_label', '')}"
                              f"{risk_info}",
                    color=0x8B0000,
                    url=get_item_wiki_url(item_id)
                )
                
                # Add thumbnail if available
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                
                return embed
            await broadcast_to_all_servers(bot, dumps, "dump", dump_embed)
        
        # Broadcast spikes
        if spikes:
            from utils.item_utils import get_item_thumbnail_url, get_item_wiki_url
            
            def spike_embed(item):
                item_name = item.get('name', 'Unknown')
                item_id = item.get('id', 0)
                thumbnail_url = get_item_thumbnail_url(item_name, item_id)
                
                buy_price = item.get('buy', 0)
                sell_price = item.get('sell', 0)
                insta_buy = item.get('insta_buy', buy_price)
                insta_sell = item.get('insta_sell', sell_price)
                
                # Build price description
                price_desc = f"Buy: {buy_price:,} GP → Sell: {sell_price:,} GP"
                if insta_buy != buy_price or insta_sell != sell_price:
                    price_desc += f"\n⚡ Insta Buy: {insta_buy:,} GP | Insta Sell: {insta_sell:,} GP"
                
                # Add risk metrics
                risk_score = item.get('risk_score', 0)
                risk_level = item.get('risk_level', 'UNKNOWN')
                profitability_confidence = item.get('profitability_confidence', 0)
                
                risk_info = f"\n⚠️ **Risk:** {risk_level} ({risk_score:.1f}/100) | **Confidence:** {profitability_confidence:.1f}%"
                
                embed = discord.Embed(
                    title=f"📈 SPIKE: {item_name}",
                    description=f"**+{item.get('rise_pct', 0):.1f}% RISE**\n"
                              f"{price_desc}\n"
                              f"Vol: {item.get('volume', 0):,}"
                              f"{risk_info}",
                    color=0x00FF00,
                    url=get_item_wiki_url(item_id)
                )
                
                # Add thumbnail if available
                if thumbnail_url:
                    embed.set_thumbnail(url=thumbnail_url)
                
                return embed
            await broadcast_to_all_servers(bot, spikes, "spike", spike_embed)
        
    except Exception as e:
        print(f"[ERROR] poll_alerts: {e}")

bot.run(CONFIG["discord_token"])