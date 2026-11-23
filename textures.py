"""Текстуры кнопок правой панели: картинка из папки темы вместо цветной заливки, значок рисуется поверх.

Файлы в папке темы (png или webp; для светлой и тёмной темы можно _light и _dark):
  texture_button.png        обычная кнопка (если файла нет, текстур нет и кнопки остаются цветными)
  texture_button_hover.png  кнопка под курсором (нет файла: та же текстура, чуть светлее)
  texture_active.png        включённая функция (нет файла: та же текстура, подкрашенная цветом «active» темы)
Значок берётся из sidebar_<имя>.png темы, а если его нет, рисуется символ кнопки шрифтом значков темы.
Рамка выбора кнопки (стрелками с клавиатуры) тоже «запекается» в картинку, потому что обычная рамка кнопки под картинкой не видна."""
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

import theme

SCALE = 3  # рисуем в 3 раза крупнее и уменьшаем: края получаются гладкими
BASES = {"normal": "texture_button", "hover": "texture_button_hover", "active": "texture_active"}
FONT_FILES = {  # шрифты Windows: название семейства -> файл (PIL ищет его в системной папке шрифтов)
    "segoe ui symbol": "seguisym.ttf", "segoe ui": "segoeui.ttf", "segoe ui emoji": "seguiemj.ttf",
    "consolas": "consola.ttf", "arial": "arial.ttf", "calibri": "calibri.ttf", "tahoma": "tahoma.ttf",
    "verdana": "verdana.ttf", "cambria math": "cambria.ttc",
}
ICON_FILL = 0.62       # какую долю кнопки занимает значок-картинка
GLYPH_FILL = 0.52      # размер символа относительно кнопки
HOVER_BRIGHTNESS = 1.18
ACTIVE_BLEND = 0.55    # насколько сильно текстура подкрашивается цветом «active», если своей текстуры включённого состояния нет

_fonts = {}


def load_font(family, px):
    """Шрифт PIL для символа или None, если такого файла в системе нет."""
    key = (family.lower(), px)
    if key not in _fonts:
        names = [FONT_FILES.get(family.lower()), family + ".ttf", family.lower().replace(" ", "") + ".ttf"]
        font = None
        for name in names:
            if not name:
                continue
            try:
                font = ImageFont.truetype(name, px)
                break
            except OSError:
                continue
        _fonts[key] = font
    return _fonts[key]


def _rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


def _open(path):
    try:
        with Image.open(path) as image:
            return image.convert("RGBA")
    except (OSError, ValueError):
        return None


def _pair(base):
    """(светлая, тёмная) картинки из папки темы по имени base или None. Если есть только одна, берётся для обеих."""
    folder = theme.current_dir()
    if not folder:
        return None
    both = theme._find(folder, base)
    light, dark = theme._find(folder, base + "_light") or both, theme._find(folder, base + "_dark") or both
    if not (light or dark):
        return None
    a, b = _open(light or dark), _open(dark or light)
    return (a, b) if a is not None and b is not None else None


def _cover(image, size):
    """Вписать картинку в квадрат со стороной size, обрезав лишнее по краям (без искажений)."""
    w, h = image.size
    side = min(w, h)
    box = ((w - side) // 2, (h - side) // 2, (w - side) // 2 + side, (h - side) // 2 + side)
    return image.crop(box).resize((size, size), Image.LANCZOS)


def _state_texture(kind, mode, textures, size):
    """Текстура нужного состояния для светлой (0) или тёмной (1) темы, уже размером size x size."""
    own = textures.get(kind)
    if own is not None:
        return _cover(own[mode], size)
    base = _cover(textures["normal"][mode], size)
    if kind == "hover":
        lighter = ImageEnhance.Brightness(base.convert("RGB")).enhance(HOVER_BRIGHTNESS)
        lighter.putalpha(base.getchannel("A"))  # прозрачность текстуры не трогаем
        return lighter
    if kind == "active":
        tint = Image.new("RGB", base.size, _rgb(theme.pair("active")[mode]))
        tinted = Image.blend(base.convert("RGB"), tint, ACTIVE_BLEND)
        tinted.putalpha(base.getchannel("A"))
        return tinted
    return base


def compose(kind, mode, textures, glyph, icon, size, selected, ratio=1):
    """Одна картинка кнопки: текстура состояния, значок и рамка выбора. mode: 0 светлая, 1 тёмная.
    Возвращает None, если значок нарисовать нечем (нет ни картинки значка, ни подходящего шрифта)."""
    big = size * SCALE
    canvas = _state_texture(kind, mode, textures, big)
    if icon is not None:
        fitted = icon.copy()
        fitted.thumbnail((int(big * ICON_FILL),) * 2, Image.LANCZOS)
        canvas.alpha_composite(fitted, ((big - fitted.width) // 2, (big - fitted.height) // 2))
    elif glyph:
        font = load_font(theme.ICON_FONT, int(big * GLYPH_FILL))
        if font is None:
            return None
        ImageDraw.Draw(canvas).text((big // 2, big // 2), glyph, font=font, fill=_rgb(theme.pair("button_text")[mode]) + (255,), anchor="mm")
    radius = min(theme.shape("sidebar_radius") * ratio, size // 2) * SCALE
    if selected:
        width = (4 if mode == 0 else 3) * ratio * SCALE  # как у обычной рамки выбора: на светлой теме толще
        ImageDraw.Draw(canvas).rounded_rectangle(
            [0, 0, big - 1, big - 1], radius=radius, outline=_rgb(theme.pair("select_border")[mode]) + (255,), width=width)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, big - 1, big - 1], radius=radius, fill=255)
    canvas.putalpha(Image.composite(canvas.getchannel("A"), Image.new("L", (big, big), 0), mask))
    return canvas.resize((size, size), Image.LANCZOS)


class Skin:
    """Все картинки одной кнопки панели: по состояниям (обычная, под курсором, включена) и с рамкой выбора или без."""

    def __init__(self, textures, glyph, icon, size):
        self.textures, self.glyph, self.icon, self.size = textures, glyph, icon, size
        self.shown = max(8, size - 2 * theme.shape("texture_inset"))  # отступ от края, если края текстуры обрезаются
        self._cache = {}

    def image(self, kind, selected):
        """QPixmap кнопки для текущей темы (светлой или тёмной), с учётом устройства с высокой плотностью пикселей."""
        mode = 0 if theme.current_mode() == "light" else 1
        key = (kind, bool(selected), mode)
        if key not in self._cache:
            icon = self.icon[mode] if self.icon else None
            picture = compose(kind, mode, self.textures, self.glyph, icon, self.shown * 2, selected, 2)  # в 2 раза крупнее: чётко на экранах с масштабом
            self._cache[key] = theme.pil_to_pixmap(picture) if picture is not None else None
        return self._cache[key]


def skin(name, glyph, size=44):
    """Оформление кнопки панели с текстурой или None: тогда кнопка остаётся обычной цветной.
    name: имя кнопки (command, notes, lock, perf, settings); glyph: её символ, если нет картинки значка."""
    normal = _pair(BASES["normal"])
    if normal is None:
        return None
    textures = {"normal": normal}
    for kind in ("hover", "active"):
        pair = _pair(BASES[kind])
        if pair is not None:
            textures[kind] = pair
    icon = _pair("sidebar_" + name)
    candidate = Skin(textures, glyph, icon, size)
    # заранее проверяем, что значок получится нарисовать: иначе лучше оставить обычную кнопку, чем пустую текстуру
    if compose("normal", 0, textures, glyph, icon[0] if icon else None, candidate.shown, False) is None:
        return None
    return candidate