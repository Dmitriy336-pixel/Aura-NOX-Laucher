# theme.py
"""
Темы оформления для PySide6.
Каждый цветовой ключ — пара [светлая, тёмная].
apply(name, mode, app) генерирует QSS и применяет его к QApplication.

Использование в коде:
    import theme
    theme.color("button")        -> "#1f538d"  (строка для текущего режима)
    theme.shape("button_radius") -> 6
    theme.CURRENT_TILE_COLORS    -> список "#rrggbb"
"""

import json
import os
import re

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from config import BASE_DIR, SETTINGS_FILE

# ---------------------------------------------------------------------------
# Директории
# ---------------------------------------------------------------------------

THEMES_DIR = os.path.join(BASE_DIR, "themes")
DEFAULT_NAME = "default"
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
IMAGE_EXTS = (".png", ".webp")
DEFAULT_ICON_FONT = "Segoe UI Symbol"  # значки ✎ ⚡ ⚙ есть в этом шрифте: размер не зависит от шрифта темы

# ---------------------------------------------------------------------------
# Дефолтные значения
# ---------------------------------------------------------------------------

COLORS = {
    # кнопки
    "button":            ("#34506b", "#1f538d"),
    "button_hover":      ("#283f55", "#14375e"),
    "button_text":       ("#ffffff", "#DCE4EE"),
    "button_border":     ("#3E454A", "#949A9F"),
    "active":            ("#a8660a", "#27ae60"),
    "active_hover":      ("#8a5408", "#219653"),
    "select_border":     ("#4b9574", "#ffffff"),
    "ghost_text":        ("#1a1a1a", "#e5e5e5"),
    "ghost_hover":       ("#cccccc", "#474747"),
    "danger":            ("#7b2d26", "#7b2d26"),
    "danger_hover":      ("#a03a30", "#a03a30"),
    # окна и панели
    "window_bg":         ("#ebebeb", "#242424"),
    "panel_bg":          ("#dbdbdb", "#2b2b2b"),
    "panel_top_bg":      ("#cfcfcf", "#333333"),
    "card_bg":           ("#dbdbdb", "#363636"),
    "card_hover":        ("#c7c7c7", "#4a4a4a"),
    "nav_selected":      ("#bfbfbf", "#404040"),
    "select_bg":         ("#cfe3f6", "#2b3f55"),
    "help_badge":        ("#4682B4", "#4682B4"),
    "help_text":         ("#ffffff", "#ffffff"),
    # текст
    "text":              ("#1a1a1a", "#DCE4EE"),
    "text_dim":          ("#4c4c4c", "#9e9e9e"),
    "accent":            ("#14507f", "#6aa9e0"),
    "error":             ("#c0392b", "#e5766b"),
    # поля ввода
    "entry_bg":          ("#F9F9FA", "#343638"),
    "entry_border":      ("#979DA2", "#565B5E"),
    "entry_text":        ("#1a1a1a", "#DCE4EE"),
    "entry_placeholder": ("#858585", "#9e9e9e"),
    "textbox_bg":        ("#F9F9FA", "#343638"),
    "textbox_border":    ("#979DA2", "#565B5E"),
    "textbox_text":      ("#1a1a1a", "#DCE4EE"),
    # элементы управления
    "scrollbar":         ("#8c8c8c", "#696969"),
    "scrollbar_hover":   ("#666666", "#878787"),
    "switch_off":        ("#939BA2", "#4A4D50"),
    "slider_track":      ("#939BA2", "#4A4D50"),
    "dropdown_bg":       ("#e5e5e5", "#333333"),
    "dropdown_hover":    ("#bfbfbf", "#474747"),
    "dropdown_text":     ("#1a1a1a", "#e5e5e5"),
    "segmented_bg":      ("#979DA2", "#4a4a4a"),
    "segmented_hover":   ("#b2b2b2", "#696969"),
    # командная строка
    "cmd_panel_bg":      ("#e0e0e0", "#2b2b2b"),
    "cmd_box_bg":        ("#f2f2f2", "#1f1f1f"),
    "cmd_line":          ("#b2b2b2", "#525252"),
    # плитки
    "tile_border":       ("#777777", "#888888"),
    "tile_select":       ("#1a1a1a", "#ffffff"),
    "tile_text_light":   ("#DCE4EE", "#DCE4EE"),
    "tile_text_dark":    ("#1a1a1a", "#1a1a1a"),
    "caption":           ("#4c4c4c", "#bfbfbf"),
    "drag_source":       ("#f1c40f", "#f1c40f"),
    "drag_target":       ("#1a1a1a", "#ffffff"),
    # подсказка
    "tooltip_bg":        ("#4d26fa", "#4d26fa"),
    "tooltip_text":      ("#ffffff", "#ffffff"),
}

SHAPES = {
    "button_radius":  6,
    "frame_radius":   6,
    "entry_radius":   6,
    "tile_radius":    6,
    "sidebar_radius": 6,
    "texture_inset":  0,
}

TILE_COLORS = [
    "#2d6a4f", "#1d4e89", "#7b2d26",
    "#5a3e85", "#8a5a00", "#006466",
]

# ---------------------------------------------------------------------------
# Внутреннее состояние
# ---------------------------------------------------------------------------

_current = {"name": DEFAULT_NAME, "mode": "dark", "dir": None}
_colors: dict[str, str] = {}   # ключ → "#rrggbb" для текущего режима
_shapes: dict[str, int] = {}

CURRENT_TILE_COLORS: list[str] = list(TILE_COLORS)
_pairs: dict = {}              # ключ → (светлый, тёмный): картинки кнопок рисуются сразу для обеих тем
_images: dict = {}
FONT_FAMILY = None             # шрифт и размер из theme.json (None = стандартные)
FONT_SIZE = None
ICON_FONT = DEFAULT_ICON_FONT

# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _pick(pair, mode: str) -> str:
    """Из пары (светлый, тёмный) выбирает нужный цвет."""
    if isinstance(pair, str):
        return pair
    return pair[0] if mode == "light" else pair[1]


def _effective_mode(mode: str) -> str:
    """
    Если mode == "system" — определяет тему через QPalette.
    Возвращает "light" или "dark".
    """
    if mode != "system":
        return mode
    qapp = QApplication.instance()
    if qapp:
        from PySide6.QtGui import QPalette
        bg = qapp.palette().color(QPalette.ColorRole.Window)
        return "dark" if bg.lightness() < 128 else "light"
    return "dark"


def _pair(value):
    """Значение из theme.json → пара или None."""
    if isinstance(value, str) and HEX.match(value):
        return (value, value)
    if (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, str) and HEX.match(v) for v in value)):
        return tuple(value)
    return None


# ---------------------------------------------------------------------------
# Загрузка темы из файла
# ---------------------------------------------------------------------------

def _theme_json(folder: str):
    try:
        with open(os.path.join(THEMES_DIR, folder, "theme.json"),
                  encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def load(name: str) -> tuple[dict, dict, list]:
    """
    Возвращает (colors_spec, shapes_spec, tiles_palette).
    colors_spec: ключ → пара или строка (ещё не выбран режим)
    shapes_spec: ключ → int
    tiles_palette: список строк "#rrggbb"
    """
    colors_spec = dict(COLORS)
    shapes_spec = dict(SHAPES)
    tiles = list(TILE_COLORS)

    data = None if name == DEFAULT_NAME else _theme_json(name)
    if data is None:
        return colors_spec, shapes_spec, tiles

    raw_colors = data.get("colors", {})
    if isinstance(raw_colors, dict):
        for key in COLORS:
            pair = _pair(raw_colors.get(key))
            if pair:
                colors_spec[key] = pair

    raw_shapes = data.get("shapes", {})
    if isinstance(raw_shapes, dict):
        for key in SHAPES:
            val = raw_shapes.get(key)
            if isinstance(val, int) and 0 <= val <= 40:
                shapes_spec[key] = val

    raw_tiles = data.get("tiles", {})
    if isinstance(raw_tiles, dict):
        palette = [c for c in raw_tiles.get("palette", [])
                   if isinstance(c, str) and HEX.match(c)][:24]
        if palette:
            tiles = palette

    return colors_spec, shapes_spec, tiles


def load_fonts(name: str) -> dict:
    """Шрифты из theme.json: {"family", "size", "icon_family"} (только заданные и верные)."""
    out = {}
    data = None if name == DEFAULT_NAME else _theme_json(name)
    fonts = data.get("fonts") if data else None
    if not isinstance(fonts, dict):
        return out
    for key in ("family", "icon_family"):
        value = fonts.get(key)
        if isinstance(value, str) and 0 < len(value.strip()) <= 60 and value.isprintable():
            out[key] = value.strip()
    size = fonts.get("size")
    if isinstance(size, int) and not isinstance(size, bool) and 8 <= size <= 24:
        out["size"] = size
    return out


def _find(folder, base):
    """Файл base.png / base.webp в папке темы или None."""
    for ext in IMAGE_EXTS:
        path = os.path.join(folder, base + ext)
        if os.path.isfile(path):
            return path
    return None


def pair(key: str) -> tuple:
    """(светлый, тёмный) цвет по ключу для текущей темы."""
    value = _pairs.get(key, ("#ff00ff", "#ff00ff"))
    return (value, value) if isinstance(value, str) else tuple(value)


def pil_to_pixmap(image):
    """Картинка PIL (RGBA) -> QPixmap."""
    from PySide6.QtGui import QImage, QPixmap
    image = image.convert("RGBA")
    data = image.tobytes("raw", "RGBA")
    qimage = QImage(data, image.width, image.height, image.width * 4, QImage.Format.Format_RGBA8888).copy()
    return QPixmap.fromImage(qimage)


def image(name: str, size: int):
    """Картинка темы (QPixmap size x size) для текущего режима или None.
    Файлы: name.png для обеих тем или name_light.png и name_dark.png по отдельности."""
    folder = current_dir()
    if not folder:
        return None
    key = (name, size, _current["mode"])
    if key not in _images:
        both = _find(folder, name)
        path = (_find(folder, name + ("_light" if _current["mode"] == "light" else "_dark")) or both)
        result = None
        if path:
            from PySide6.QtGui import QPixmap
            from PySide6.QtCore import Qt as _Qt
            pix = QPixmap(path)
            if not pix.isNull():
                result = pix.scaled(size * 2, size * 2, _Qt.AspectRatioMode.KeepAspectRatio,
                                    _Qt.TransformationMode.SmoothTransformation)
                result.setDevicePixelRatio(2)
        _images[key] = result
    return _images[key]


# ---------------------------------------------------------------------------
# Генератор QSS
# ---------------------------------------------------------------------------

def _make_qss(c: dict, s: dict) -> str:
    br = s["button_radius"]
    fr = s["frame_radius"]
    er = s["entry_radius"]

    return f"""
/* === Общее === */
QMainWindow, QDialog, QWidget[window_root="true"] {{
    background-color: {c['window_bg']};
}}
QWidget {{
    color: {c['text']};
}}

/* === Фреймы / панели === */
QFrame {{
    background-color: {c['panel_bg']};
    border-radius: {fr}px;
    border: none;
}}
QFrame[top="true"] {{
    background-color: {c['panel_top_bg']};
}}
QFrame[flat="true"] {{
    border-radius: 0px;
}}
QFrame[card="true"] {{
    background-color: {c['card_bg']};
}}
QScrollArea {{
    background-color: {c['window_bg']};
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background-color: {c['window_bg']};
}}

/* === Кнопки === */
QPushButton {{
    background-color: {c['button']};
    color: {c['button_text']};
    border: none;
    border-radius: {br}px;
    padding: 6px 14px;
    min-height: 28px;
}}
QPushButton:hover {{
    background-color: {c['button_hover']};
}}
QPushButton:pressed {{
    background-color: {c['button_hover']};
}}
QPushButton:disabled {{
    background-color: {c['panel_bg']};
    color: {c['text_dim']};
}}

QPushButton[danger="true"] {{
    background-color: {c['danger']};
    color: {c['button_text']};
}}
QPushButton[danger="true"]:hover {{
    background-color: {c['danger_hover']};
}}

QPushButton[ghost="true"] {{
    background-color: transparent;
    color: {c['ghost_text']};
    border: 1px solid {c['button_border']};
}}
QPushButton[ghost="true"]:hover {{
    background-color: {c['ghost_hover']};
}}

QPushButton[active="true"] {{
    background-color: {c['active']};
    color: {c['button_text']};
}}
QPushButton[active="true"]:hover {{
    background-color: {c['active_hover']};
}}

QPushButton[nav="true"] {{
    background-color: transparent;
    color: {c['ghost_text']};
    border: none;
    text-align: left;
    padding: 6px 12px;
}}
QPushButton[nav="true"]:hover {{
    background-color: {c['ghost_hover']};
}}
QPushButton[nav="true"][selected="true"] {{
    background-color: {c['nav_selected']};
}}

QPushButton[side="true"] {{
    padding: 0px;
    min-width: 44px;
    max-width: 44px;
    min-height: 44px;
    max-height: 44px;
    border-radius: {s['sidebar_radius']}px;
}}
QPushButton[compact="true"] {{
    padding: 0px 8px;
    min-height: 22px;
}}
QFrame[seg="true"] {{
    background-color: {c['segmented_bg']};
    border-radius: {br}px;
}}
QPushButton[seg="true"] {{
    background-color: transparent;
    color: {c['text']};
    border-radius: {max(br - 2, 0)}px;
    padding: 3px 14px;
    min-height: 22px;
}}
QPushButton[seg="true"]:hover {{
    background-color: {c['segmented_hover']};
}}
QPushButton[seg="true"][active="true"] {{
    background-color: {c['button']};
    color: {c['button_text']};
}}
QPushButton[seg="true"][active="true"]:hover {{
    background-color: {c['button_hover']};
}}

/* === Поля ввода === */
QLineEdit {{
    background-color: {c['entry_bg']};
    color: {c['entry_text']};
    border: 1px solid {c['entry_border']};
    border-radius: {er}px;
    padding: 4px 8px;
    selection-background-color: {c['select_bg']};
    min-height: 26px;
}}
QLineEdit:focus {{
    border-color: {c['accent']};
}}
QLineEdit:disabled {{
    color: {c['text_dim']};
}}

QTextEdit, QPlainTextEdit {{
    background-color: {c['textbox_bg']};
    color: {c['textbox_text']};
    border: 1px solid {c['textbox_border']};
    border-radius: {er}px;
    padding: 4px 8px;
    selection-background-color: {c['select_bg']};
}}
QTextEdit:focus, QPlainTextEdit:focus {{
    border-color: {c['accent']};
}}

/* === Метки === */
QLabel {{
    background: transparent;
    border: none;
    color: {c['text']};
}}
QLabel[dim="true"] {{
    color: {c['text_dim']};
}}
QLabel[accent="true"] {{
    color: {c['accent']};
}}
QLabel[error="true"] {{
    color: {c['error']};
}}

/* === Полоса прокрутки === */
QScrollBar:vertical {{
    background: transparent;
    width: 14px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {c['scrollbar']};
    border-radius: 5px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['scrollbar_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: {c['scrollbar']};
    border-radius: 4px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{
    background: {c['scrollbar_hover']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* === Список === */
QListWidget {{
    background-color: {c['panel_bg']};
    border: none;
    outline: none;
}}
QListWidget::item {{
    padding: 6px 10px;
    border-radius: 4px;
    color: {c['ghost_text']};
}}
QListWidget::item:selected {{
    background-color: {c['select_bg']};
    color: {c['text']};
}}
QListWidget::item:hover:!selected {{
    background-color: {c['card_hover']};
}}

/* === Выпадающий список === */
QComboBox {{
    background-color: {c['button']};
    color: {c['button_text']};
    border: none;
    border-radius: {br}px;
    padding: 4px 10px;
    min-height: 28px;
}}
QComboBox:hover {{
    background-color: {c['button_hover']};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['dropdown_bg']};
    color: {c['dropdown_text']};
    border: 1px solid {c['entry_border']};
    selection-background-color: {c['select_bg']};
    outline: none;
}}

/* === Слайдер === */
QSlider::groove:horizontal {{
    background: {c['slider_track']};
    height: 8px;
    border-radius: 4px;
}}
QSlider::handle:horizontal {{
    background: {c['button']};
    width: 16px;
    height: 16px;
    margin: -4px 0;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: {c['button_hover']};
}}
QSlider::sub-page:horizontal {{
    background: {c['button']};
    border-radius: 4px;
}}

/* === Чекбокс / переключатель === */
QCheckBox {{
    color: {c['text']};
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid {c['entry_border']};
    background: {c['entry_bg']};
}}
QCheckBox::indicator:checked {{
    background: {c['button']};
    border-color: {c['button']};
}}

/* === Контекстное меню (правый клик по плитке, Delete) === */
QMenu {{
    background-color: {c['dropdown_bg']};
    color: {c['dropdown_text']};
    border: 1px solid {c['entry_border']};
    padding: 4px;
}}
QMenu::item {{
    background-color: transparent;
    color: {c['dropdown_text']};
    padding: 6px 24px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {c['dropdown_hover']};
}}
QMenu::item:disabled {{
    color: {c['scrollbar']};
}}
QMenu::separator {{
    height: 1px;
    background: {c['entry_border']};
    margin: 4px 8px;
}}

/* === Подсказка === */
QToolTip {{
    background-color: {c['tooltip_bg']};
    color: {c['tooltip_text']};
    border: none;
    padding: 6px 10px;
    border-radius: 4px;
}}

/* === Разделитель === */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    background-color: {c['cmd_line']};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}

/* === Вкладки (если понадобятся) === */
QTabWidget::pane {{
    border: none;
    background-color: {c['panel_bg']};
}}
QTabBar::tab {{
    background: transparent;
    color: {c['ghost_text']};
    padding: 6px 16px;
    border: none;
}}
QTabBar::tab:selected {{
    color: {c['text']};
    border-bottom: 2px solid {c['accent']};
}}
QTabBar::tab:hover:!selected {{
    background-color: {c['ghost_hover']};
}}
"""


# ---------------------------------------------------------------------------
# Применение темы
# ---------------------------------------------------------------------------

def apply(name: str = None, mode: str = None,
          app: QApplication = None) -> None:
    """
    Применяет тему к QApplication.
    name — папка темы (None = оставить текущую)
    mode — "dark" / "light" / "system" (None = оставить текущий)
    app  — экземпляр QApplication (None = QApplication.instance())
    """
    global _colors, _shapes, CURRENT_TILE_COLORS, _pairs, FONT_FAMILY, FONT_SIZE, ICON_FONT

    if name is not None:
        _current["name"] = name
    if mode is not None:
        _current["mode"] = _effective_mode(mode)

    colors_spec, shapes_spec, tiles = load(_current["name"])

    _pairs = dict(colors_spec)
    _images.clear()
    fonts = load_fonts(_current["name"])
    FONT_FAMILY, FONT_SIZE = fonts.get("family"), fonts.get("size")
    ICON_FONT = fonts.get("icon_family", DEFAULT_ICON_FONT)
    _colors = {k: _pick(v, _current["mode"]) for k, v in colors_spec.items()}
    _shapes = shapes_spec
    CURRENT_TILE_COLORS = tiles

    qapp = app or QApplication.instance()
    if qapp:
        qapp.setStyleSheet(_make_qss(_colors, _shapes))
        font = QFont(FONT_FAMILY or "Segoe UI")
        font.setPixelSize(FONT_SIZE or 13)
        qapp.setFont(font)  # шрифт не в QSS: иначе он перебивает setFont/setPixelSize у виджетов


# ---------------------------------------------------------------------------
# Публичный API для виджетов
# ---------------------------------------------------------------------------

def color(key: str) -> str:
    """Возвращает текущий цвет по ключу ("#rrggbb")."""
    return _colors.get(key, "#ff00ff")   # маджента = сигнал об ошибке


def shape(key: str) -> int:
    """Возвращает текущее значение формы."""
    return _shapes.get(key, 6)


def current_name() -> str:
    return _current["name"]


def current_mode() -> str:
    return _current["mode"]


def current_dir():
    """Папка включённой темы или None для стандартной."""
    name = _current["name"]
    if name == DEFAULT_NAME:
        return None
    folder = os.path.join(THEMES_DIR, name)
    return folder if os.path.isdir(folder) else None


def list_themes() -> list[tuple[str, str]]:
    """[(папка, название)]: сначала стандартная, потом найденные."""
    found = [(DEFAULT_NAME, "Стандартная")]
    try:
        folders = sorted(os.listdir(THEMES_DIR))
    except OSError:
        return found
    for folder in folders:
        if folder == DEFAULT_NAME or folder.startswith(("_", ".")):
            continue
        data = _theme_json(folder)
        if data is not None:
            title = data.get("name")
            found.append((
                folder,
                title if isinstance(title, str) and title.strip() else folder
            ))
    return found


# ---------------------------------------------------------------------------
# Утилита: цвет текста на плитке (тёмный или светлый)
# ---------------------------------------------------------------------------

def tile_text_color(background: str) -> str:
    """Возвращает цвет текста для данного фона плитки."""
    try:
        r = int(background[1:3], 16)
        g = int(background[3:5], 16)
        b = int(background[5:7], 16)
    except (ValueError, TypeError, IndexError):
        return color("tile_text_light")
    brightness = 0.299 * r + 0.587 * g + 0.114 * b
    return color("tile_text_dark") if brightness > 160 else color("tile_text_light")


# ---------------------------------------------------------------------------
# Инициализация при импорте (только данные, без QApplication)
# ---------------------------------------------------------------------------

def _saved_theme_settings() -> tuple[str, str]:
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            s = json.load(f)
        return s.get("theme_name", DEFAULT_NAME), s.get("theme_mode", "dark")
    except (OSError, ValueError):
        return DEFAULT_NAME, "dark"


_theme_name, _theme_mode = _saved_theme_settings()
_current["name"] = _theme_name
# mode пока сохраняем как есть; _effective_mode вызовется в apply()
# после создания QApplication в main.py
_current["mode"] = _theme_mode if _theme_mode != "system" else "dark"
