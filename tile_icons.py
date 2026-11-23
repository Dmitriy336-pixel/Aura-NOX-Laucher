# tile_icons.py
"""Свои иконки плиток: выбранная картинка копируется в папку icons рядом с данными
(так иконка не пропадёт, если исходный файл переместят) и показывается на плитке."""

import os
import shutil
import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QImage, QPixmap

from config import ICONS_DIR

_cache = {}  # (имя файла, размер) -> QPixmap, чтобы не читать файл при каждой перерисовке


def import_icon(source_path):
    """Проверяет и копирует картинку в папку icons. Возвращает новое имя файла.
    Если файл не картинка, бросает OSError."""
    if QImage(source_path).isNull():
        raise OSError(f"Не удалось прочитать картинку: {source_path}")
    os.makedirs(ICONS_DIR, exist_ok=True)
    name = uuid.uuid4().hex[:10] + (os.path.splitext(source_path)[1].lower() or ".png")
    shutil.copyfile(source_path, os.path.join(ICONS_DIR, name))
    return name


def load(name, size):
    """QPixmap для плитки (вписан в квадрат size x size, пропорции сохранены) или None.
    Размер pixmap учитывает масштаб экрана: логический размер = pixmap.deviceIndependentSize()."""
    if not name:
        return None
    key = (name, size)
    if key not in _cache:
        image = QImage(os.path.join(ICONS_DIR, name))
        if image.isNull():
            _cache[key] = None
        else:
            dpr = QGuiApplication.primaryScreen().devicePixelRatio() if QGuiApplication.primaryScreen() else 1.0
            target = max(1, int(size * dpr))
            pixmap = QPixmap.fromImage(image).scaled(
                target, target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            pixmap.setDevicePixelRatio(dpr)
            _cache[key] = pixmap
    return _cache[key]


def remove_if_unused(name, tiles):
    """Удаляет файл иконки, если на него больше не ссылается ни одна плитка."""
    if name and not any(tile.get("icon") == name for tile in tiles):
        for key in [k for k in _cache if k[0] == name]:
            del _cache[key]
        try:
            os.remove(os.path.join(ICONS_DIR, name))
        except OSError:
            pass
