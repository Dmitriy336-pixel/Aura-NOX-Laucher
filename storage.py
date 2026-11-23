# storage.py
"""Данные: загрузка и сохранение плиток и настроек.
Не зависит от GUI-фреймворка — чистый Python."""

import json
import os

from config import DATA_FILE, DEFAULT_SETTINGS, SETTINGS_FILE


def load_tiles() -> list:
    try:
        with open(DATA_FILE, encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        os.replace(DATA_FILE, DATA_FILE + ".broken")
        return []


def write_json(path: str, data) -> None:
    """Пишет JSON через временный файл — защита от обрыва записи."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_tiles(tiles: list) -> None:
    write_json(DATA_FILE, tiles)


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            saved = json.load(f)
            settings.update(saved)
            # миграция старой настройки
            if saved.get("tile_icon_only") and "tile_label" not in saved:
                settings["tile_label"] = "hover"
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        try:
            os.replace(SETTINGS_FILE, SETTINGS_FILE + ".broken")
        except OSError:
            pass
    return settings


def save_settings(settings: dict) -> None:
    write_json(SETTINGS_FILE, settings)
