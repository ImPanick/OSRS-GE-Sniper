#!/usr/bin/env python3
# backend/utils/recipe_data.py
"""
Recipe and Decant Data
Static mappings for OSRS recipes and potion decanting
"""

# Recipe mappings: product_name -> recipe data
RECIPES = {
    "prayer potion(4)": {
        "product_id": 2434,
        "ingredients": [
            {"id": 257, "name": "Ranarr weed"},
            {"id": 231, "name": "Snape grass"},
            {"id": 227, "name": "Vial of water"}
        ]
    },
    "super restore(4)": {
        "product_id": 3024,
        "ingredients": [
            {"id": 3000, "name": "Snapdragon"},
            {"id": 231, "name": "Snape grass"},
            {"id": 227, "name": "Vial of water"}
        ]
    },
    "saradomin brew(4)": {
        "product_id": 6685,
        "ingredients": [
            {"id": 3002, "name": "Toadflax"},
            {"id": 239, "name": "Crushed bird's nest"},
            {"id": 227, "name": "Vial of water"}
        ]
    },
    "super combat potion(4)": {
        "product_id": 12695,
        "ingredients": [
            {"id": 269, "name": "Torstol"},
            {"id": 2436, "name": "Super attack(4)"},
            {"id": 2440, "name": "Super strength(4)"},
            {"id": 2442, "name": "Super defence(4)"}
        ]
    },
    "ranging potion(4)": {
        "product_id": 2444,
        "ingredients": [
            {"id": 245, "name": "Dwarf weed"},
            {"id": 227, "name": "Vial of water"}
        ]
    },
    "magic potion(4)": {
        "product_id": 3042,
        "ingredients": [
            {"id": 247, "name": "Lantadyme"},
            {"id": 227, "name": "Vial of water"}
        ]
    },
    "antifire potion(4)": {
        "product_id": 2452,
        "ingredients": [
            {"id": 245, "name": "Dwarf weed"},
            {"id": 2436, "name": "Super attack(4)"},
            {"id": 227, "name": "Vial of water"}
        ]
    },
    "super antifire potion(4)": {
        "product_id": 15304,
        "ingredients": [
            {"id": 245, "name": "Dwarf weed"},
            {"id": 269, "name": "Torstol"},
            {"id": 15309, "name": "Antifire potion(4)"},
            {"id": 227, "name": "Vial of water"}
        ]
    },
    "stamina potion(4)": {
        "product_id": 12625,
        "ingredients": [
            {"id": 3010, "name": "Super energy(4)"},
            {"id": 3004, "name": "Amylase crystal"}
        ]
    },
    "antidote+(4)": {
        "product_id": 5943,
        "ingredients": [
            {"id": 5935, "name": "Antidote(4)"},
            {"id": 239, "name": "Crushed bird's nest"}
        ]
    }
}

# Decant sets: base_name -> list of dose items
DECANT_SETS = {
    "prayer potion": [
        {"id": 2434, "name": "Prayer potion(4)"},
        {"id": 139, "name": "Prayer potion(3)"},
        {"id": 141, "name": "Prayer potion(2)"},
        {"id": 143, "name": "Prayer potion(1)"}
    ],
    "super restore": [
        {"id": 3024, "name": "Super restore(4)"},
        {"id": 3026, "name": "Super restore(3)"},
        {"id": 3028, "name": "Super restore(2)"},
        {"id": 3030, "name": "Super restore(1)"}
    ],
    "saradomin brew": [
        {"id": 6685, "name": "Saradomin brew(4)"},
        {"id": 6687, "name": "Saradomin brew(3)"},
        {"id": 6689, "name": "Saradomin brew(2)"},
        {"id": 6691, "name": "Saradomin brew(1)"}
    ],
    "super combat potion": [
        {"id": 12695, "name": "Super combat potion(4)"},
        {"id": 12697, "name": "Super combat potion(3)"},
        {"id": 12699, "name": "Super combat potion(2)"},
        {"id": 12701, "name": "Super combat potion(1)"}
    ],
    "ranging potion": [
        {"id": 2444, "name": "Ranging potion(4)"},
        {"id": 169, "name": "Ranging potion(3)"},
        {"id": 171, "name": "Ranging potion(2)"},
        {"id": 173, "name": "Ranging potion(1)"}
    ],
    "magic potion": [
        {"id": 3042, "name": "Magic potion(4)"},
        {"id": 3040, "name": "Magic potion(3)"},
        {"id": 3044, "name": "Magic potion(2)"},
        {"id": 3046, "name": "Magic potion(1)"}
    ],
    "antifire potion": [
        {"id": 2452, "name": "Antifire potion(4)"},
        {"id": 2454, "name": "Antifire potion(3)"},
        {"id": 2456, "name": "Antifire potion(2)"},
        {"id": 2458, "name": "Antifire potion(1)"}
    ],
    "super antifire potion": [
        {"id": 15304, "name": "Super antifire potion(4)"},
        {"id": 15305, "name": "Super antifire potion(3)"},
        {"id": 15306, "name": "Super antifire potion(2)"},
        {"id": 15307, "name": "Super antifire potion(1)"}
    ],
    "stamina potion": [
        {"id": 12625, "name": "Stamina potion(4)"},
        {"id": 12627, "name": "Stamina potion(3)"},
        {"id": 12629, "name": "Stamina potion(2)"},
        {"id": 12631, "name": "Stamina potion(1)"}
    ],
    "antidote+": [
        {"id": 5943, "name": "Antidote+(4)"},
        {"id": 5945, "name": "Antidote+(3)"},
        {"id": 5947, "name": "Antidote+(2)"},
        {"id": 5949, "name": "Antidote+(1)"}
    ],
    "super attack": [
        {"id": 2436, "name": "Super attack(4)"},
        {"id": 145, "name": "Super attack(3)"},
        {"id": 147, "name": "Super attack(2)"},
        {"id": 149, "name": "Super attack(1)"}
    ],
    "super strength": [
        {"id": 2440, "name": "Super strength(4)"},
        {"id": 157, "name": "Super strength(3)"},
        {"id": 159, "name": "Super strength(2)"},
        {"id": 161, "name": "Super strength(1)"}
    ],
    "super defence": [
        {"id": 2442, "name": "Super defence(4)"},
        {"id": 163, "name": "Super defence(3)"},
        {"id": 165, "name": "Super defence(2)"},
        {"id": 167, "name": "Super defence(1)"}
    ]
}

def get_recipe(product_name: str):
    """Get recipe for a product by name"""
    # Try exact match first
    if product_name in RECIPES:
        return RECIPES[product_name]
    
    # Try case-insensitive match
    product_name_lower = product_name.lower()
    for key, recipe in RECIPES.items():
        if key.lower() == product_name_lower:
            return recipe
    
    return None

def get_decant_set(base_name: str):
    """Get decant set for a potion base name"""
    # Try exact match first
    if base_name in DECANT_SETS:
        return DECANT_SETS[base_name]
    
    # Try case-insensitive match
    base_name_lower = base_name.lower()
    for key, decant_set in DECANT_SETS.items():
        if key.lower() == base_name_lower:
            return decant_set
    
    return None

