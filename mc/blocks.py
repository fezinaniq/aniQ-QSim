"""Block names <-> modern Bukkit string material names (Paper 1.21.4 compatibility)."""

from __future__ import annotations

# name -> (material string, data)
LEGACY: dict[str, tuple[str | int, int]] = {
    "air": ("AIR", 0),
    "stone": ("STONE", 0),
    "grass_block": ("GRASS_BLOCK", 0),
    "dirt": ("DIRT", 0),
    "glass": ("GLASS", 0),
    "lapis_block": ("LAPIS_BLOCK", 0),
    "gold_block": ("GOLD_BLOCK", 0),
    "iron_block": ("IRON_BLOCK", 0),
    "obsidian": ("OBSIDIAN", 0),
    "diamond_block": ("DIAMOND_BLOCK", 0),
    "lever": ("LEVER", 5),
    "glowstone": ("GLOWSTONE", 0),
    "emerald_block": ("EMERALD_BLOCK", 0),
    "redstone_block": ("REDSTONE_BLOCK", 0),
    "quartz_block": ("QUARTZ_BLOCK", 0),
    "sea_lantern": ("SEA_LANTERN", 0),
    "coal_block": ("COAL_BLOCK", 0),
    "red_sandstone": ("RED_SANDSTONE", 0),
    "purpur_block": ("PURPUR_BLOCK", 0),
    "observer": ("OBSERVER", 0),
    # decoration only (never part of the circuit palette's gates)
    "polished_blackstone": ("POLISHED_BLACKSTONE", 0),
    "polished_blackstone_bricks": ("POLISHED_BLACKSTONE_BRICKS", 0),
    "chiseled_polished_blackstone": ("CHISELED_POLISHED_BLACKSTONE", 0),
    "gilded_blackstone": ("GILDED_BLACKSTONE", 0),
    "smooth_quartz": ("SMOOTH_QUARTZ", 0),
    "light_blue_stained_glass": ("LIGHT_BLUE_STAINED_GLASS", 0),
    "tinted_glass": ("TINTED_GLASS", 0),
}

CONCRETE_COLORS = [
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray",
    "light_gray", "cyan", "purple", "blue", "brown", "green", "red", "black",
]
for _color in CONCRETE_COLORS:
    LEGACY[f"{_color}_concrete"] = (f"{_color.upper()}_CONCRETE", 0)

LEVER_ID = "LEVER"
LEVER_FLOOR_DATA = 5
LEVER_POWERED_BIT = 8

_NAME_BY_ID: dict[int | str, str] = {}
for _name, (_id, _data) in LEGACY.items():
    _NAME_BY_ID[_id] = _name

GLYPHS = {
    "air": " ", "diamond_block": "=", "gold_block": "H", "iron_block": "X",
    "red_sandstone": "Y", "emerald_block": "Z", "lapis_block": "S", "purpur_block": "T",
    "redstone_block": "*", "coal_block": "+", "quartz_block": "x", "observer": "M",
    "obsidian": "#", "lever": "L", "glowstone": "o", "stone": ".",
    "light_blue_stained_glass": "=", "sea_lantern": "o", "polished_blackstone": "#",
    "polished_blackstone_bricks": "#", "chiseled_polished_blackstone": "#",
    "gilded_blackstone": "#", "smooth_quartz": "q", "tinted_glass": ":",
}

COLOR_GLYPHS = {
    "red_concrete": "r", "orange_concrete": "o", "yellow_concrete": "y", "lime_concrete": "l",
    "green_concrete": "g", "cyan_concrete": "c", "light_blue_concrete": "u",
    "blue_concrete": "b", "purple_concrete": "p", "magenta_concrete": "m",
    "pink_concrete": "k", "brown_concrete": "n", "white_concrete": "w",
    "black_concrete": "#", "gray_concrete": ".", "light_gray_concrete": ",",
}

def legacy(name: str) -> tuple[str | int, int]:
    """(material_name, data) for a block name."""
    try:
        return LEGACY[name]
    except KeyError:
        raise KeyError(
            f"block '{name}' has no material mapping in mc/blocks.py LEGACY"
        ) from None

def name_from_id(block_id: int | str) -> str:
    """Name for a block id/material read from the world."""
    if isinstance(block_id, str):
        clean = block_id.lower().replace("minecraft:", "")
        return _NAME_BY_ID.get(block_id, clean)
    return _NAME_BY_ID.get(block_id, f"unknown:{block_id}")

def glyph(name: str) -> str:
    """One character for ASCII dumps of the world."""
    if name in GLYPHS:
        return GLYPHS[name]
    if name in COLOR_GLYPHS:
        return COLOR_GLYPHS[name]
    return "?"