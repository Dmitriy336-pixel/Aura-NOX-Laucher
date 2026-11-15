"""Темы оформления: цвета, скругления, шрифты и картинки лежат в папках внутри «themes» рядом с программой.
Тема это папка themes/<имя>/ с файлом theme.json и необязательными картинками (формат: themes/README.txt).

Весь список того, что можно менять, находится в таблицах ниже (COLORS, SHAPES, FONT_KEYS): ключ, значение по умолчанию,
описание и то, что именно он красит. Остальной код берёт значения из модульных переменных (theme.BUTTON, theme.DIM и так далее).
Тема включается ещё при первом импорте этого модуля, то есть до создания окон и до того, как другие модули прочитают свои константы.
Цвета пары (светлая тема, тёмная тема), поэтому переключатель «светлая / тёмная / как в Windows» работает с любой темой."""
import json
import os
import re
import shutil
import sys

import customtkinter as ctk
from PIL import Image, ImageDraw

from config import BASE_DIR, SETTINGS_FILE
from config import COLORS as DEFAULT_TILE_COLORS

THEMES_DIR = os.path.join(BASE_DIR, "themes")
DEFAULT_NAME = "default"
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
IMAGE_EXTS = (".png", ".webp")
MAX_THEME_BYTES = 20 * 1024 * 1024  # папка больше этого не считается темой (защита от случайного выбора диска)


def g(n):
    """Серый CustomTkinter grayN как #rrggbb (так цвета годятся и для картинок, и для виджетов)."""
    v = round(n * 2.55)
    return f"#{v:02x}{v:02x}{v:02x}"


def tok(default, var, desc, ctk_targets=(), always=False):
    """Описание цветового ключа: значение по умолчанию, переменная модуля, подпись и куда красит в CustomTkinter.
    always: значение подставляется в стандартную тему всегда, иначе только когда тема его задаёт."""
    return {"default": default, "var": var, "desc": desc, "ctk": list(ctk_targets), "always": always}


# Цвета: ключ -> описание. Каждый цвет это пара (светлая тема, тёмная тема).
COLORS = {
    # --- кнопки ---
    "button": tok(("#34506b", "#1f538d"), "BUTTON", "обычная кнопка (а также ползунки, переключатели, выбор вариантов)",
                  [("CTkButton", "fg_color"), ("CTkSegmentedButton", "selected_color"), ("CTkSwitch", "progress_color"),
                   ("CTkSlider", "progress_color"), ("CTkSlider", "button_color"), ("CTkOptionMenu", "fg_color")], True),
    "button_hover": tok(("#283f55", "#14375e"), "BUTTON_HOVER", "кнопка под курсором",
                        [("CTkButton", "hover_color"), ("CTkSegmentedButton", "selected_hover_color"),
                         ("CTkSwitch", "button_hover_color"), ("CTkSlider", "button_hover_color"),
                         ("CTkOptionMenu", "button_color"), ("CTkOptionMenu", "button_hover_color")], True),
    "button_text": tok(("#ffffff", "#DCE4EE"), "BUTTON_TEXT", "текст на обычной кнопке", [("CTkButton", "text_color")], True),
    "button_border": tok(("#3E454A", "#949A9F"), "BUTTON_BORDER", "рамка кнопок с обводкой", [("CTkButton", "border_color")]),
    "active": tok(("#a8660a", "#27ae60"), "ACTIVE", "включённая функция: подсвеченная кнопка правой панели"),
    "active_hover": tok(("#8a5408", "#219653"), "ACTIVE_HOVER", "включённая кнопка под курсором"),
    "select_border": tok(("#4b9574", "#ffffff"), "SELECT_BORDER", "рамка выбранной кнопки правой панели"),
    "ghost_text": tok((g(10), g(90)), "GHOST_TEXT", "текст на прозрачных кнопках (список разделов, «Сброс», «Отмена»)"),
    "ghost_hover": tok((g(80), g(28)), "GHOST_HOVER", "прозрачная кнопка под курсором"),
    "danger": tok(("#7b2d26", "#7b2d26"), "DANGER", "кнопки «Удалить» и «Сбросить всё»"),
    "danger_hover": tok(("#a03a30", "#a03a30"), "DANGER_HOVER", "кнопка «Удалить» под курсором"),
    # --- окна и панели ---
    "window_bg": tok((g(92), g(14)), "WINDOW_BG", "фон окон", [("CTk", "fg_color"), ("CTkToplevel", "fg_color")]),
    "panel_bg": tok((g(86), g(17)), "PANEL_BG", "фон панелей и рамок", [("CTkFrame", "fg_color")]),
    "panel_top_bg": tok((g(81), g(20)), "PANEL_TOP_BG", "фон панелей внутри панелей", [("CTkFrame", "top_fg_color")]),
    "card_bg": tok((g(86), g(21)), "CARD_BG", "строки списков и карточки тем"),
    "card_hover": tok((g(78), g(29)), "CARD_HOVER", "строка или карточка под курсором"),
    "nav_selected": tok((g(75), g(25)), "NAV_SELECTED", "выбранный раздел в списке настроек слева"),
    "select_bg": tok(("#cfe3f6", "#2b3f55"), "SELECT_BG", "выбранная строка: заметка в списке, подсказка в командной строке"),
    "help_badge": tok(("#4682B4", "#4682B4"), "HELP_BADGE", "кружок «?» с подсказкой"),
    "help_text": tok(("#ffffff", "#ffffff"), "HELP_TEXT", "знак в кружке «?»"),
    # --- текст ---
    "text": tok((g(10), "#DCE4EE"), "TEXT", "обычный текст",
                [("CTkLabel", "text_color"), ("CTkCheckBox", "text_color"), ("CTkSwitch", "text_color"),
                 ("CTkRadioButton", "text_color")]),
    "text_dim": tok((g(30), g(62)), "DIM", "приглушённый текст: описания, подписи, подсказки"),
    "accent": tok(("#14507f", "#6aa9e0"), "ACCENT", "выделенный текст: названия команд, быстрые клавиши в списках"),
    "error": tok(("#c0392b", "#e5766b"), "ERROR", "сообщения об ошибках"),
    # --- поля ввода ---
    "entry_bg": tok(("#F9F9FA", "#343638"), "ENTRY_BG", "фон полей ввода", [("CTkEntry", "fg_color")]),
    "entry_border": tok(("#979DA2", "#565B5E"), "ENTRY_BORDER", "рамка полей ввода", [("CTkEntry", "border_color")]),
    "entry_text": tok((g(10), "#DCE4EE"), "ENTRY_TEXT", "текст в полях ввода", [("CTkEntry", "text_color")]),
    "entry_placeholder": tok((g(52), g(62)), "ENTRY_PLACEHOLDER", "серая подсказка в пустом поле",
                             [("CTkEntry", "placeholder_text_color")]),
    "textbox_bg": tok(("#F9F9FA", "#343638"), "TEXTBOX_BG", "фон большого текстового поля (редактор заметок)",
                      [("CTkTextbox", "fg_color")]),
    "textbox_border": tok(("#979DA2", "#565B5E"), "TEXTBOX_BORDER", "рамка большого текстового поля",
                          [("CTkTextbox", "border_color")]),
    "textbox_text": tok((g(10), "#DCE4EE"), "TEXTBOX_TEXT", "текст заметки", [("CTkTextbox", "text_color")]),
    # --- элементы управления ---
    "scrollbar": tok((g(55), g(41)), "SCROLLBAR", "ползунок полосы прокрутки",
                     [("CTkScrollbar", "button_color"), ("CTkTextbox", "scrollbar_button_color")]),
    "scrollbar_hover": tok((g(40), g(53)), "SCROLLBAR_HOVER", "ползунок полосы прокрутки под курсором",
                           [("CTkScrollbar", "button_hover_color"), ("CTkTextbox", "scrollbar_button_hover_color")]),
    "switch_off": tok(("#939BA2", "#4A4D50"), "SWITCH_OFF", "выключенный переключатель", [("CTkSwitch", "fg_color")]),
    "switch_knob": tok((g(36), "#D5D9DE"), "SWITCH_KNOB", "кружок на переключателе", [("CTkSwitch", "button_color")]),
    "slider_track": tok(("#939BA2", "#4A4D50"), "SLIDER_TRACK", "дорожка ползунка", [("CTkSlider", "fg_color")]),
    "dropdown_bg": tok((g(90), g(20)), "DROPDOWN_BG", "выпадающий список: фон", [("DropdownMenu", "fg_color")]),
    "dropdown_hover": tok((g(75), g(28)), "DROPDOWN_HOVER", "выпадающий список: строка под курсором",
                          [("DropdownMenu", "hover_color")]),
    "dropdown_text": tok((g(10), g(90)), "DROPDOWN_TEXT", "выпадающий список: текст", [("DropdownMenu", "text_color")]),
    "segmented_bg": tok(("#979DA2", g(29)), "SEGMENTED_BG", "переключатель из нескольких кнопок: фон и невыбранные",
                        [("CTkSegmentedButton", "fg_color"), ("CTkSegmentedButton", "unselected_color")]),
    "segmented_hover": tok((g(70), g(41)), "SEGMENTED_HOVER", "невыбранная кнопка под курсором",
                           [("CTkSegmentedButton", "unselected_hover_color")]),
    # --- командная строка ---
    "cmd_panel_bg": tok((g(88), g(17)), "CMD_PANEL", "командная строка: панель с подсказками"),
    "cmd_box_bg": tok((g(95), g(12)), "CMD_BOX", "командная строка: фон окна"),
    "cmd_line": tok((g(70), g(32)), "CMD_LINE", "командная строка: рамка и разделители"),
    # --- плитки ---
    "tile_border": tok(("#777777", "#888888"), "TILE_BORDER", "рамка плитки «＋»"),
    "tile_select": tok(("#1a1a1a", "#ffffff"), "TILE_SELECT", "рамка выбранной плитки"),
    "tile_text_light": tok(("#DCE4EE", "#DCE4EE"), "TILE_TEXT_LIGHT", "текст на тёмных плитках"),
    "tile_text_dark": tok(("#1a1a1a", "#1a1a1a"), "TILE_TEXT_DARK", "текст на светлых плитках"),
    "caption": tok((g(30), g(75)), "CAPTION", "подпись под плиткой"),
    "drag_source": tok(("#f1c40f", "#f1c40f"), "DRAG_SOURCE", "рамка плитки, которую тащат"),
    "drag_target": tok(("#1a1a1a", "#ffffff"), "DRAG_TARGET", "рамка плитки, на чьё место встанет перетаскиваемая"),
    # --- подсказка при наведении ---
    "tooltip_bg": tok(("#4d26fa", "#4d26fa"), "TOOLTIP_BG", "всплывающая подсказка: фон"),
    "tooltip_text": tok(("#ffffff", "#ffffff"), "TOOLTIP_TEXT", "всплывающая подсказка: текст"),
}

# Скругления (число от 0 до 40): ключ -> (по умолчанию, переменная, описание, куда в CustomTkinter)
SHAPES = {
    "button_radius": (6, "BUTTON_RADIUS", "скругление кнопок", [("CTkButton", "corner_radius")]),
    "frame_radius": (6, "FRAME_RADIUS", "скругление панелей", [("CTkFrame", "corner_radius")]),
    "entry_radius": (6, "ENTRY_RADIUS", "скругление полей ввода и текстовых полей",
                     [("CTkEntry", "corner_radius"), ("CTkTextbox", "corner_radius")]),
    "tile_radius": (6, "TILE_RADIUS", "скругление плиток", []),
    "sidebar_radius": (6, "SIDEBAR_RADIUS", "скругление кнопок правой панели", []),
    "texture_inset": (0, "TEXTURE_INSET", "отступ текстуры кнопок панели от края, px (если края картинки обрезаются, поставь 2)", []),
}
DEFAULT_ICON_FONT = "Segoe UI Symbol"  # значки ✎ ⚡ ⚙ есть в этом шрифте: так их размер не зависит от шрифта темы
FONT_KEYS = {"family": "название шрифта, например Segoe UI", "size": "основной размер текста, 8..24",
             "icon_family": "шрифт значков на кнопках правой панели (по умолчанию Segoe UI Symbol)"}
THEME_SECTIONS = ("colors", "shapes", "fonts", "tiles")

_current = {"name": DEFAULT_NAME, "dir": None}
_images = {}
_previews = {}
_orig = {}  # исходные значения стандартной темы CustomTkinter: чтобы смена темы не накапливала правки

# Переменные модуля (BUTTON, DIM, TILE_COLORS...) заполняются в apply()
TILE_COLORS = list(DEFAULT_TILE_COLORS)
FONT_FAMILY = None
FONT_SIZE = None
ICON_FONT = DEFAULT_ICON_FONT
for _t in COLORS.values():
    globals()[_t["var"]] = _t["default"]
for _k, (_d, _v, _x, _y) in SHAPES.items():
    globals()[_v] = _d


# ---------------------------------------------------------------- чтение тем
def _theme_json(folder):
    """Содержимое theme.json или None, если файла нет или он битый."""
    try:
        with open(os.path.join(THEMES_DIR, folder, "theme.json"), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def list_themes():
    """[(папка, название)]: сначала стандартная, дальше найденные в themes по алфавиту папок."""
    found = [(DEFAULT_NAME, "Стандартная")]
    try:
        folders = sorted(os.listdir(THEMES_DIR))
    except OSError:
        return found
    for folder in folders:
        if folder == DEFAULT_NAME or folder.startswith(("_", ".")):  # _template и скрытые папки в список не попадают
            continue
        data = _theme_json(folder)
        if data is not None:
            title = data.get("name")
            found.append((folder, title if isinstance(title, str) and title.strip() else folder))
    return found


def _pair(value):
    """Цвет из theme.json -> пара (светлая, тёмная) или None, если значение неверное."""
    if isinstance(value, str) and HEX.match(value):
        return (value, value)
    if isinstance(value, (list, tuple)) and len(value) == 2 and all(isinstance(v, str) and HEX.match(v) for v in value):
        return (value[0], value[1])
    return None


def _int(value, low, high):
    return value if isinstance(value, int) and not isinstance(value, bool) and low <= value <= high else None


def load(name):
    """Тема как словарь {"set": цвета, заданные темой, "colors": все цвета (заданные и стандартные),
    "shapes": скругления, "fonts": шрифты, "tiles": палитра плиток}. Возвращает (словарь, папка темы или None).
    Неверные значения и неизвестные ключи пропускаются, а не ломают запуск."""
    spec = {"set": {}, "colors": {k: t["default"] for k, t in COLORS.items()},
            "shapes": {k: v[0] for k, v in SHAPES.items()}, "fonts": {}, "tiles": list(DEFAULT_TILE_COLORS)}
    data = None if name == DEFAULT_NAME else _theme_json(name)
    if data is None:
        return spec, None  # стандартная, либо тему удалили или файл битый
    colors = data.get("colors")
    if isinstance(colors, dict):
        for key in COLORS:
            pair = _pair(colors.get(key))
            if pair:
                spec["set"][key] = pair
                spec["colors"][key] = pair
    shapes = data.get("shapes")
    if isinstance(shapes, dict):
        for key in SHAPES:
            value = _int(shapes.get(key), 0, 40)
            if value is not None:
                spec["shapes"][key] = value
    fonts = data.get("fonts")
    if isinstance(fonts, dict):
        for key in ("family", "icon_family"):
            name_value = fonts.get(key)
            if isinstance(name_value, str) and 0 < len(name_value.strip()) <= 60 and name_value.isprintable():
                spec["fonts"][key] = name_value.strip()
        size = _int(fonts.get("size"), 8, 24)
        if size is not None:
            spec["fonts"]["size"] = size
    tiles = data.get("tiles")
    if isinstance(tiles, dict) and isinstance(tiles.get("palette"), list):
        palette = [c for c in tiles["palette"] if isinstance(c, str) and HEX.match(c)][:24]
        if palette:
            spec["tiles"] = palette
    return spec, os.path.join(THEMES_DIR, name)


# ---------------------------------------------------------------- применение
def _set(theme, widget, param, value):
    """Подменяет параметр в стандартной теме CustomTkinter, запомнив исходное значение."""
    if widget in theme and param in theme[widget]:
        _orig.setdefault((widget, param), theme[widget][param])
        theme[widget][param] = value


def _font_section(theme):
    """Раздел шрифта в теме CustomTkinter зависит от системы: Windows / macOS / Linux."""
    font = theme.get("CTkFont", {})
    key = {"win32": "Windows", "darwin": "macOS"}.get(sys.platform, "Linux")
    return font.get(key) if isinstance(font.get(key), dict) else None


def apply(name=None):
    """Включает тему (без аргумента повторяет текущую). Вызывается при импорте модуля и ещё раз при старте программы."""
    global TILE_COLORS, FONT_FAMILY, FONT_SIZE, ICON_FONT
    if name is None:
        name = _current["name"]
    spec, folder = load(name)
    _current["name"] = name if folder or name == DEFAULT_NAME else DEFAULT_NAME
    _current["dir"] = folder
    _images.clear()
    for key, t in COLORS.items():
        globals()[t["var"]] = spec["colors"][key]
    for key, (_d, var, _x, _y) in SHAPES.items():
        globals()[var] = spec["shapes"][key]
    TILE_COLORS = list(spec["tiles"])
    FONT_FAMILY, FONT_SIZE = spec["fonts"].get("family"), spec["fonts"].get("size")
    ICON_FONT = spec["fonts"].get("icon_family", DEFAULT_ICON_FONT)

    manager = getattr(ctk, "ThemeManager", None)
    if manager is None:
        return
    theme = manager.theme
    for (widget, param), value in _orig.items():  # сначала возвращаем стандартные значения
        if widget in theme and param in theme[widget]:
            theme[widget][param] = value
    for key, t in COLORS.items():
        if t["always"] or key in spec["set"]:
            for widget, param in t["ctk"]:
                _set(theme, widget, param, list(spec["colors"][key]))
    for key, (_d, _v, _x, targets) in SHAPES.items():
        if spec["shapes"][key] != SHAPES[key][0]:
            for widget, param in targets:
                _set(theme, widget, param, spec["shapes"][key])
    section = _font_section(theme)
    if section is not None:
        for param, value in (("family", FONT_FAMILY), ("size", FONT_SIZE)):
            if value is not None and param in section:
                _orig.setdefault(("CTkFont", param), section[param])
                section[param] = value
        for param in ("family", "size"):  # возврат стандартного шрифта, если новая тема его не задаёт
            if spec["fonts"].get(param) is None and ("CTkFont", param) in _orig:
                section[param] = _orig[("CTkFont", param)]


def current_name():
    return _current["name"]


def current_dir():
    """Папка включённой темы или None для стандартной."""
    return _current["dir"]


def missing_targets():
    """Какие ключи таблиц не нашлись в установленной версии CustomTkinter: такие ключи темы ничего не меняют.
    Возвращает [(ключ темы, раздел CustomTkinter, параметр)]; пусто значит, всё на месте."""
    manager = getattr(ctk, "ThemeManager", None)
    if manager is None:
        return []
    theme = manager.theme
    missing = []
    for key, t in COLORS.items():
        missing += [(key, w, p) for w, p in t["ctk"] if w not in theme or p not in theme[w]]
    for key, (_d, _v, _x, targets) in SHAPES.items():
        missing += [(key, w, p) for w, p in targets if w not in theme or p not in theme[w]]
    section = _font_section(theme)
    if section is None:
        missing.append(("fonts", "CTkFont", sys.platform))
    return missing


def pick(pair):
    """Из пары (светлая, тёмная) выбирает цвет для текущего режима: нужно там, где виджет не понимает пары (tk.Label)."""
    return pair[0] if ctk.get_appearance_mode() == "Light" else pair[1]


# ---------------------------------------------------------------- картинки темы
def _find(folder, base):
    for ext in IMAGE_EXTS:
        path = os.path.join(folder, base + ext)
        if os.path.isfile(path):
            return path
    return None


def image(name, size):
    """Картинка темы (CTkImage size x size) или None. Файлы: name.png для обеих тем,
    или name_light.png и name_dark.png для светлой и тёмной отдельно."""
    folder = _current["dir"]
    if not folder:
        return None
    key = (name, size)
    if key not in _images:
        both = _find(folder, name)
        light = _find(folder, name + "_light") or both
        dark = _find(folder, name + "_dark") or both
        result = None
        if light or dark:
            try:
                with Image.open(light or dark) as a, Image.open(dark or light) as b:
                    result = ctk.CTkImage(light_image=a.convert("RGBA"), dark_image=b.convert("RGBA"), size=(size, size))
            except (OSError, ValueError):
                result = None  # битая картинка: остаётся обычная кнопка
        _images[key] = result
    return _images[key]


# ---------------------------------------------------------------- карточки тем в настройках
def _render_preview(colors, mode, size):
    """Мини-макет окна из цветов темы: фон, плитки, панель справа с тремя кнопками (одна «включена»).
    mode: 0 светлая, 1 тёмная."""
    def color(key):
        return colors[key][mode]

    s = size * 4  # рисуем крупнее и уменьшаем: края получаются гладкими
    image = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 8, fill=color("window_bg"))
    margin = s // 14
    panel_w = s // 4
    d.rounded_rectangle([s - margin - panel_w, margin, s - margin, s - margin], radius=s // 16, fill=color("panel_bg"))
    button = (panel_w * 6) // 10
    bx = s - margin - panel_w + (panel_w - button) // 2
    gap = (s - 2 * margin - 3 * button) // 4
    for i, key in enumerate(("button", "button", "active")):
        y = margin + gap + i * (button + gap)
        d.rounded_rectangle([bx, y, bx + button, y + button], radius=button // 5, fill=color(key))
    tile = (s - 2 * margin - panel_w - margin * 4) // 3
    for row in range(3):
        for col in range(3):
            x = margin * 2 + col * (tile + margin)
            y = margin * 2 + row * (tile + margin)
            d.rounded_rectangle([x, y, x + tile, y + tile], radius=tile // 6, fill=color("button"),
                                outline=color("select_border") if (row, col) == (0, 0) else None, width=s // 40)
    return image.resize((size, size), Image.LANCZOS)


def preview(name, size=96):
    """Картинка карточки темы: свой icon.png из папки темы или макет, нарисованный по цветам темы."""
    key = (name, size)
    if key not in _previews:
        spec, folder = load(name)
        custom = _find(folder, "icon") if folder else None
        result = None
        try:
            if custom:
                with Image.open(custom) as source:
                    fitted = source.convert("RGBA")
                    fitted.thumbnail((size, size), Image.LANCZOS)          # вписываем, не искажая
                    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                    canvas.paste(fitted, ((size - fitted.width) // 2, (size - fitted.height) // 2))
                light = dark = canvas
            else:
                light, dark = _render_preview(spec["colors"], 0, size), _render_preview(spec["colors"], 1, size)
            result = ctk.CTkImage(light_image=light, dark_image=dark, size=(size, size))
        except (OSError, ValueError):
            result = None  # битая картинка: карточка без превью, с названием
        _previews[key] = result
    return _previews[key]


def clear_previews():
    _previews.clear()


def _folder_size(path, limit):
    total = 0
    for root, _dirs, files in os.walk(path):
        for fname in files:
            try:
                total += os.path.getsize(os.path.join(root, fname))
            except OSError:
                pass
            if total > limit:
                return total
    return total


def _safe_folder_name(text):
    """Имя папки из произвольного текста: без запрещённых символов и без _ / . в начале (так не спрятать тему)."""
    return re.sub(r'[<>:"/\\|?*]', "", text).strip(" .").lstrip("_.") or "theme"


def _free_folder(base):
    root = os.path.abspath(THEMES_DIR)
    name, n = base, 2
    while os.path.exists(os.path.join(root, name)):
        name = f"{base} ({n})"
        n += 1
    return name


def add_theme(src):
    """Добавляет тему из папки src: проверяет её и копирует в themes.
    Возвращает (имя папки в themes, None) или (None, текст ошибки)."""
    src = os.path.abspath(src)
    json_path = os.path.join(src, "theme.json")
    if not os.path.isfile(json_path):
        return None, "В этой папке нет файла theme.json. Выбери папку самой темы."
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None, "Файл theme.json не читается: проверь, что это корректный JSON."
    if not isinstance(data, dict) or not any(isinstance(data.get(s), dict) for s in THEME_SECTIONS):
        return None, "В theme.json нет ни одного раздела (colors, shapes, fonts, tiles)."
    root = os.path.abspath(THEMES_DIR)
    if os.path.normcase(os.path.dirname(src)) == os.path.normcase(root):
        return os.path.basename(src), None  # тема уже лежит в themes
    if _folder_size(src, MAX_THEME_BYTES) > MAX_THEME_BYTES:
        return None, "Папка слишком большая для темы (больше 20 МБ)."
    name = _free_folder(_safe_folder_name(os.path.basename(src)))
    try:
        os.makedirs(root, exist_ok=True)
        shutil.copytree(src, os.path.join(root, name))
    except OSError as e:
        return None, f"Не удалось скопировать тему: {e}"
    return name, None


def template_spec(title="Моя тема"):
    """Полный theme.json со всеми ключами и стандартными значениями (основа для своей темы)."""
    return {
        "name": title,
        "colors": {k: list(t["default"]) for k, t in COLORS.items()},
        "shapes": {k: v[0] for k, v in SHAPES.items()},
        "fonts": {"family": "Segoe UI", "size": 13, "icon_family": DEFAULT_ICON_FONT},
        "tiles": {"palette": list(DEFAULT_TILE_COLORS)},
    }


def create_theme(title):
    """Создаёт в themes новую тему с полным theme.json (стандартные значения), чтобы поправить нужное.
    Возвращает (имя папки, None) или (None, текст ошибки)."""
    title = (title or "").strip()
    if not title:
        return None, "Название не может быть пустым."
    name = _free_folder(_safe_folder_name(title))
    folder = os.path.join(os.path.abspath(THEMES_DIR), name)
    try:
        os.makedirs(folder)
        with open(os.path.join(folder, "theme.json"), "w", encoding="utf-8") as f:
            json.dump(template_spec(title), f, ensure_ascii=False, indent=2)
    except OSError as e:
        return None, f"Не удалось создать тему: {e}"
    return name, None


def readme_text():
    """Описание формата темы (themes/README.txt), собранное из таблиц, чтобы оно не расходилось с кодом."""
    lines = ["ТЕМЫ ОФОРМЛЕНИЯ", "",
             "Тема это папка внутри «themes». Выбрать тему: Настройки -> Темы -> нажать на карточку -> «Перезапустить и применить».",
             "Папка «themes» лежит рядом с main.py (при запуске из VS Code) или рядом с exe (в собранной версии).", "",
             "КАК СДЕЛАТЬ СВОЮ ТЕМУ",
             "  Способ 1: Настройки -> Темы -> «Создать свою». Появится папка с готовым theme.json, где уже есть все ключи.",
             "  Способ 2: скопируй папку _template, назови как хочешь (имя без _ и точки в начале).",
             "  Дальше открой theme.json и поменяй нужное. Лишние ключи можно удалить: пропущенное берётся стандартное.",
             "  Положи свой icon.png (картинка карточки). Без него карточка покажет макет, нарисованный по цветам темы.",
             "  Настройки -> Темы -> «Обновить список». Тема вне themes добавляется кнопкой «＋ Добавить тему» (копируется).",
             "  Папки, имя которых начинается с _ или точки, в список не попадают (так спрятан шаблон).", "",
             "ФОРМАТ theme.json",
             '  { "name": "Название в списке", "colors": {...}, "shapes": {...}, "fonts": {...}, "tiles": {"palette": [...]} }',
             "  Цвет это пара [светлая, тёмная] вида \"#rrggbb\". Одна строка \"#rrggbb\" значит один цвет для обеих тем.",
             "  Неверное значение пропускается и берётся стандартное.", "", "ЦВЕТА (colors)"]
    width = max(len(k) for k in COLORS)
    lines += [f"  {k.ljust(width)}  {t['desc']}" for k, t in COLORS.items()]
    lines += ["", "СКРУГЛЕНИЯ (shapes), число от 0 до 40"]
    lines += [f"  {k.ljust(width)}  {v[2]}" for k, v in SHAPES.items()]
    lines += ["", "ШРИФТ (fonts)"] + [f"  {k.ljust(width)}  {d}" for k, d in FONT_KEYS.items()]
    lines += ["", "ПАЛИТРА ПЛИТОК (tiles.palette)",
              "  Список цветов #rrggbb (до 24): новые плитки получают их по кругу, они же в окне выбора цвета плитки.", "",
              "КАРТИНКИ (png или webp, лучше квадратные, от 128x128, с прозрачностью)",
              "  icon.png              картинка карточки темы в настройках (256x256)",
              "  plus.png              значок на плитке «＋»",
              "  sidebar_command.png   кнопка командной строки",
              "  sidebar_notes.png     кнопка заметок",
              "  sidebar_lock.png      кнопка блокировки плиток",
              "  sidebar_perf.png      кнопка режима производительности",
              "  sidebar_settings.png  кнопка настроек",
              "  Для светлой и тёмной темы можно положить разные: plus_light.png и plus_dark.png.",
              "  Текстуры кнопок правой панели (картинка вместо цветной заливки, значок рисуется поверх):",
              "  texture_button.png        обычная кнопка (без этого файла текстур нет, кнопки остаются цветными)",
              "  texture_button_hover.png  кнопка под курсором (нет файла: та же текстура, чуть светлее)",
              "  texture_active.png        включённая функция (нет файла: та же текстура, подкрашенная цветом active)",
              "  Значок берётся из sidebar_<имя>.png, а если его нет, рисуется символ кнопки шрифтом icon_family.",
              "  Картинка обрезается до квадрата и скругляется по sidebar_radius. Если края текстуры обрезаются,",
              "  поставь shapes.texture_inset = 2.",
              "  Нет картинки, остаётся обычный значок.", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- запуск
def _saved_theme_name():
    """Какую тему выбрали в прошлый раз (читаем settings.json напрямую, чтобы не тянуть лишние модули)."""
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            name = json.load(f).get("theme_name")
        return name if isinstance(name, str) and name else DEFAULT_NAME
    except (OSError, ValueError, AttributeError):
        return DEFAULT_NAME


apply(_saved_theme_name())  # тема включается при первом импорте: до окон и до констант в других модулях