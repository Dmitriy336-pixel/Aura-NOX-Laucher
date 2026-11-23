# tile_keys.py
"""Быстрые клавиши плиток: чистая логика без GUI (раньше лежала в controls_page.py)."""


def assign_key(tiles, index, key):
    """Назначает плитке быструю клавишу ("" значит «убрать»).
    Если эту клавишу занимала другая плитка, плитки меняются клавишами."""
    tile = tiles[index]
    if key:
        for other in tiles:
            if other is not tile and other.get("key") == key:
                other["key"] = tile.get("key") or ""
    tile["key"] = key or ""


def redistribute(tiles, keys):
    """Раздаёт клавиши из keys всем плиткам заново по порядку; кому не хватило, остаются без клавиши."""
    for i, tile in enumerate(tiles):
        tile["key"] = keys[i] if i < len(keys) else ""
