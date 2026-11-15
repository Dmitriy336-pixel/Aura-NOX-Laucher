"""Данные: загрузка и сохранение плиток и настроек.
Плитка = {"type": "app", "name": "Блокнот", "target": "C:\\...\\notepad.exe", "key": "1"}
"""
import json
import os
from config import DATA_FILE, DEFAULT_SETTINGS, SETTINGS_FILE


def load_tiles():
    try:
        with open(DATA_FILE, encoding="utf-8-sig") as f:  # utf-8-sig читает и файлы с BOM
            data = json.load(f)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        # файл повреждён: не затираем его, а откладываем в сторону
        os.replace(DATA_FILE, DATA_FILE + ".broken")
        return []


def write_json(path, data):
    """Пишет JSON через временный файл: если программа закроется посреди записи, старый файл останется целым."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def save_tiles(tiles):
    write_json(DATA_FILE, tiles)


def load_settings():
    settings = dict(DEFAULT_SETTINGS)  # начинаем со значений по умолчанию
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            saved = json.load(f)
            settings.update(saved)  # поверх кладём то, что сохранил пользователь
            if saved.get("tile_icon_only") and "tile_label" not in saved:
                settings["tile_label"] = "hover"  # старая настройка «только иконка» стала режимом «при наведении»
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        # файл повреждён: откладываем в сторону, чтобы следующее сохранение его не затёрло
        try:
            os.replace(SETTINGS_FILE, SETTINGS_FILE + ".broken")
        except OSError:
            pass
    return settings


def save_settings(settings):
    write_json(SETTINGS_FILE, settings)