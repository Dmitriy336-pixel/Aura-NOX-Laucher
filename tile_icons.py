"""Свои иконки плиток: выбранная картинка копируется в папку icons рядом с данными
(так иконка не пропадёт, если исходный файл переместят) и показывается на плитке."""
import os
import shutil
import uuid

import customtkinter as ctk
from PIL import Image

from config import ICONS_DIR

_cache = {}  # (имя файла, размер) -> готовая картинка, чтобы не читать файл при каждой перерисовке


def import_icon(source_path):
    """Проверяет и копирует картинку в папку icons. Возвращает новое имя файла.
    Если файл не картинка, бросает OSError."""
    with Image.open(source_path) as im:
        im.load()  # убеждаемся, что картинка читается целиком
    os.makedirs(ICONS_DIR, exist_ok=True)
    name = uuid.uuid4().hex[:10] + (os.path.splitext(source_path)[1].lower() or ".png")
    shutil.copyfile(source_path, os.path.join(ICONS_DIR, name))
    return name


def load(name, size):
    """Картинка для плитки (вписанная в квадрат size x size) или None, если иконки нет или файл не читается."""
    if not name:
        return None
    key = (name, size)
    if key not in _cache:
        try:
            with Image.open(os.path.join(ICONS_DIR, name)) as im:
                im = im.convert("RGBA")
            scale = size / max(im.size)  # сохраняем пропорции
            fitted = (max(1, int(im.width * scale)), max(1, int(im.height * scale)))
            _cache[key] = ctk.CTkImage(light_image=im, dark_image=im, size=fitted)
        except OSError:
            _cache[key] = None
    return _cache[key]


def remove_if_unused(name, tiles):
    """Удаляет файл иконки, если на него больше не ссылается ни одна плитка."""
    if name and not any(tile.get("icon") == name for tile in tiles):
        try:
            os.remove(os.path.join(ICONS_DIR, name))
        except OSError:
            pass