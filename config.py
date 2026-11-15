"""Все настройки в одном месте. Меняешь число здесь, и оно меняется везде."""
import os
import sys

VERSION = "1.0.0"  # версия программы: показывается в «О программе»

FROZEN = getattr(sys, "frozen", False)  # True, когда запущен собранный exe

# Данные пользователя (плитки, настройки) лежат рядом с exe и переживают перезапуски
BASE_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
# Файлы, упакованные внутрь exe (иконка, текстуры): при запуске распаковываются во временную папку
RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)

DATA_FILE = os.path.join(BASE_DIR, "tiles.json")

# Окно
WINDOW_SCALE = 0.8     # окно открывается в 80% от экрана
SIDEBAR_WIDTH = 64     # ширина правой панели в пикселях

# Сетка плиток
COLUMNS = 5            # плиток в строке
GAP = 8                # отступ вокруг плитки
MAX_TILE_SIZE = 120    # плитки растут вместе с окном, но не крупнее этого

# Цвета плиток по кругу
COLORS = ["#2d6a4f", "#1d4e89", "#7b2d26", "#5a3e85", "#8a5a00", "#006466"]
# Палитра в окне выбора цвета плитки (первые шесть совпадают с цветами по кругу)
TILE_PALETTE = COLORS + ["#c0392b", "#d35400", "#f1c40f", "#27ae60", "#2980b9", "#8e44ad", "#34495e", "#7f8c8d"]
# Быстрые клавиши плиток: выдаются по порядку при добавлении плитки
QUICK_KEYS = "123456789qwertyuiopasdfghjklzxcvbnm"

# Файл с настройками и значения по умолчанию
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
DEFAULT_SETTINGS = {
    "autostart": False,
    "background_mode": False,
    "after_launch": "minimize",
    "columns": COLUMNS,                    # плиток в строке
    "max_tile_size": MAX_TILE_SIZE,        # максимальный размер плитки, px
    "sidebar_width": SIDEBAR_WIDTH,        # ширина правой панели, px
    "window_scale": int(WINDOW_SCALE * 100),  # размер окна при запуске, % от экрана
    "command_line": True,                  # командная строка включена
    "hotkey_summon": "ctrl+alt+space",     # вызов лаунчера из фонового режима
    "hotkey_command": "ctrl+alt+t",        # вызов командной строки из любой программы
    "hotkey_notes": "ctrl+alt+n",          # открыть заметки из любой программы
    "notes_hotkey": True,                  # включена ли эта горячая клавиша
    "notes_font_size": 14,                 # размер шрифта в заметках
    "notes_autosave_ms": 700,              # через сколько мс после правки заметка сохраняется
    "notes_sort": "date",                  # порядок в списке: date (новые сверху) или name (по алфавиту)
    "tile_icon_size": 60,                  # размер иконки на плитке, % от размера плитки
    "tile_label": "inside",                # где название плитки: inside (на плитке), below (под плиткой), hover (при наведении)
    "tile_show_key": True,                 # показывать быструю клавишу на плитке
    "confirm_delete": True,                # спрашивать подтверждение перед удалением плитки
    "theme_mode": "dark",                  # оформление: dark / light / system (как в Windows)
    "theme_name": "default",               # папка темы в themes
    "auto_icons": True,                    # подбирать иконку при добавлении программы
    "show_notes_btn": True,                # показывать кнопку заметок на правой панели
    "show_lock_btn": True,                 # показывать кнопку блокировки перетаскивания
    "show_perf_btn": True,                 # показывать кнопку режима производительности
    "language": "ru",                      # язык интерфейса: ru или en (включается перезапуском)
    "terms_seen": "",                      # версия условий использования, показанных при первом запуске
    "sounds_enabled": True,                # звуки событий (файлы лежат в папке sounds)
    "sound_volume": 70,                    # громкость звуков, %
}

USER_COMMANDS_FILE = os.path.join(BASE_DIR, "commands.json")  # свои команды пользователя

FAVORITES_FILE = os.path.join(BASE_DIR, "favorites.json")  # избранные папки командной строки

HISTORY_FILE = os.path.join(BASE_DIR, "history.json")      # история команд

ICONS_DIR = os.path.join(BASE_DIR, "icons")  # свои иконки плиток (копии выбранных картинок)

# Настройки, которые являются глобальными горячими клавишами (чтобы не назначить одну и ту же дважды)
HOTKEY_SETTINGS = ("hotkey_summon", "hotkey_command", "hotkey_notes")

# Иконка окна и панели задач
APP_NAME = "Aura NOX Launcher"   # название программы: заголовки окон, «О программе», условия
ICON_PATH = os.path.join(RESOURCE_DIR, "icon.ico")

