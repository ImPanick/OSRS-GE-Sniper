# discord-bot/utils/item_utils.py
"""
Utility functions for OSRS items
"""
import urllib.parse

def get_item_thumbnail_url(item_name: str, item_id: int = None) -> str:
    """
    Get the OSRS Wiki thumbnail URL for an item
    
    Args:
        item_name: The item name (e.g., "Lantadyme")
        item_id: Item ID (preferred method for OSRS Wiki)
    
    Returns:
        URL to the item's thumbnail image
    """
    # OSRS Wiki uses item ID directly for images
    if item_id:
        # Format: https://oldschool.runescape.wiki/images/{item_id}.png
        return f"https://oldschool.runescape.wiki/images/{item_id}.png"
    
    if not item_name:
        return None
    
    # Fallback to item name if ID not available
    # Format item name for wiki URL
    wiki_name = item_name.strip()
    
    # Replace spaces with underscores
    wiki_name = wiki_name.replace(' ', '_')
    
    # Capitalize first letter of each word (OSRS wiki format)
    parts = wiki_name.split('_')
    wiki_name = '_'.join(part.capitalize() for part in parts)
    
    # URL encode special characters but keep underscores
    wiki_name = urllib.parse.quote(wiki_name, safe='_')
    
    # OSRS Wiki image URL format
    thumbnail_url = f"https://oldschool.runescape.wiki/images/{wiki_name}.png"
    
    return thumbnail_url

def get_item_wiki_url(item_id: int) -> str:
    """Get the OSRS Wiki page URL for an item"""
    return f"https://prices.runescape.wiki/osrs/item/{item_id}"

