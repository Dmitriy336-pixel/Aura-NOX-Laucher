"""Работа с папками тем для страницы «Темы»: добавить готовую, создать свою, картинка-превью карточки.
Отделено от theme.py, чтобы тот оставался чистым генератором QSS."""
import json
import os
import re
import shutil

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap

import theme
from i18n import tr

PREVIEW_FILES = ("preview.png", "preview.webp", "preview.jpg")
_cache = {}


def clear_previews():
    _cache.clear()


def add_theme(src):
    """Копирует папку темы в themes. Возвращает (имя папки, None) или (None, текст ошибки)."""
    src = os.path.normpath(src)
    if not os.path.isfile(os.path.join(src, "theme.json")):
        return None, tr("В выбранной папке нет theme.json")
    name = os.path.basename(src)
    if name == theme.DEFAULT_NAME or name.startswith(("_", ".")):
        return None, tr("Недопустимое имя папки темы")
    if os.path.normcase(os.path.dirname(src)) == os.path.normcase(os.path.normpath(theme.THEMES_DIR)):
        return name, None  # папка уже лежит в themes
    dest = os.path.join(theme.THEMES_DIR, name)
    if os.path.exists(dest):
        return None, tr('Тема «{name}» уже есть в папке themes', name=name)
    try:
        os.makedirs(theme.THEMES_DIR, exist_ok=True)
        shutil.copytree(src, dest)
    except OSError as e:
        return None, str(e)
    return name, None


def create_theme(title):
    """Создаёт тему-копию стандартной с полным списком цветов. Возвращает (имя папки, None) или (None, ошибка)."""
    title = (title or "").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip(" .")[:40]
    if not name or name.startswith(("_", ".")) or name == theme.DEFAULT_NAME:
        return None, tr("Недопустимое название темы")
    dest = os.path.join(theme.THEMES_DIR, name)
    if os.path.exists(dest):
        return None, tr('Тема «{name}» уже есть в папке themes', name=name)
    data = {
        "name": title,
        "colors": {key: list(pair) for key, pair in theme.COLORS.items()},
        "shapes": dict(theme.SHAPES),
        "tiles": {"palette": list(theme.TILE_COLORS)},
    }
    try:
        os.makedirs(dest)
        with open(os.path.join(dest, "theme.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        return None, str(e)
    return name, None


def _draw_preview(folder, size):
    colors, shapes, tiles = theme.load(folder)
    pick = lambda key: QColor(theme._pick(colors[key], theme.current_mode()))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    r = shapes["tile_radius"]
    p.setBrush(pick("window_bg"))
    p.drawRoundedRect(QRectF(0, 0, size, size), 10, 10)
    bar = size * 0.2
    p.setBrush(pick("panel_bg"))
    p.drawRoundedRect(QRectF(size - bar - 6, 6, bar, size - 12), 6, 6)
    cell = (size - bar - 6 - 6 - 8) / 2
    for i in range(4):
        x, y = 6 + (i % 2) * (cell + 8), 6 + (i // 2) * (cell + 8)
        p.setBrush(QColor(tiles[i % len(tiles)]))
        p.drawRoundedRect(QRectF(x, y, cell, cell), r, r)
    p.setBrush(pick("accent"))
    p.drawEllipse(QRectF(size - bar - 6 + bar / 2 - 5, 16, 10, 10))
    p.end()
    return pm


def preview(folder, size=96):
    """QPixmap карточки темы: preview.png из папки темы или нарисованный по цветам темы."""
    key = (folder, size)
    if key in _cache:
        return _cache[key]
    pm = None
    if folder != theme.DEFAULT_NAME:
        for fname in PREVIEW_FILES:
            path = os.path.join(theme.THEMES_DIR, folder, fname)
            if os.path.isfile(path):
                loaded = QPixmap(path)
                if not loaded.isNull():
                    pm = loaded.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                       Qt.TransformationMode.SmoothTransformation)
                    break
    if pm is None:
        pm = _draw_preview(folder, size)
    _cache[key] = pm
    return pm
