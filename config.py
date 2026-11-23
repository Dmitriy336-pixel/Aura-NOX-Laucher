# config.py
"""Все пути, размеры и настройки по умолчанию. Не зависит от GUI-фреймворка."""

import os
import sys

VERSION = "2.0.0"

FROZEN = getattr(sys, "frozen", False)

BASE_DIR = (os.path.dirname(sys.executable) if FROZEN
            else os.path.dirname(os.path.abspath(__file__)))
RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)

DATA_FILE     = os.path.join(BASE_DIR, "tiles.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
USER_COMMANDS_FILE = os.path.join(BASE_DIR, "commands.json")
FAVORITES_FILE     = os.path.join(BASE_DIR, "favorites.json")
HISTORY_FILE       = os.path.join(BASE_DIR, "history.json")
SCREENSHOT_DELAY_MS = 250  # пауза между закрытием строки (и размытия) и запуском вырезки экрана, иначе вырезка снимет размытие
ICONS_DIR          = os.path.join(BASE_DIR, "icons")

# Окно
WINDOW_SCALE = 0.8
SIDEBAR_WIDTH = 64

# Сетка плиток
COLUMNS      = 5
GAP          = 8
MAX_TILE_SIZE = 120

# Цвета плиток по кругу (дефолт; тема может переопределить)
COLORS = ["#2d6a4f", "#1d4e89", "#7b2d26", "#5a3e85", "#8a5a00", "#006466"]

TILE_PALETTE = COLORS + [
    "#c0392b", "#d35400", "#f1c40f", "#27ae60",
    "#2980b9", "#8e44ad", "#34495e", "#7f8c8d",
]

QUICK_KEYS = "123456789qwertyuiopasdfghjklzxcvbnm"

APP_NAME  = "Aura NOX Launcher"
ICON_PATH = os.path.join(RESOURCE_DIR, "icon.ico")

HOTKEY_SETTINGS = ("hotkey_summon", "hotkey_command", "hotkey_notes")

DEFAULT_SETTINGS = {
    "autostart":         False,
    "background_mode":   False,
    "after_launch":      "minimize",
    "columns":           COLUMNS,
    "max_tile_size":     MAX_TILE_SIZE,
    "sidebar_width":     SIDEBAR_WIDTH,
    "window_scale":      int(WINDOW_SCALE * 100),
    "command_line":      True,
    "command_blur":      True,
    "add_tile_mode":     "file",  # что открывает «+»: "file" (выбор файла) или "search" (поиск программ); у поиска есть и своя плитка
    "command_blur_strength": 50,
    "command_blur_dim":  30,
    "command_blur_fade": 140,
    "hotkey_summon":     "ctrl+alt+space",
    "hotkey_command":    "ctrl+alt+t",
    "hotkey_notes":      "ctrl+alt+n",
    "notes_hotkey":      True,
    "notes_font_size":   14,
    "notes_autosave_ms": 700,
    "notes_sort":        "date",
    "tile_icon_size":    60,
    "tile_fill_color":   None,  # цвет «один для всех»: его получают новые плитки; None = палитра темы
    "tile_label":        "inside",
    "tile_show_key":     True,
    "confirm_delete":    True,
    "theme_mode":        "dark",
    "theme_name":        "default",
    "auto_icons":        True,
    "show_notes_btn":    True,
    "show_lock_btn":     True,
    "show_perf_btn":     True,
    "language":          "ru",
    "terms_seen":        "",
    "sounds_enabled":    True,
    "sound_volume":      70,
}
