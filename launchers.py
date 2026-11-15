"""Запуск: для каждого типа плитки свой способ открытия.
Новый тип (папка, команда...) = новая функция + строка в LAUNCHERS.
"""
import os


def open_path(target):
    """Открывает программу, файл, папку или адрес.
    Программа запускается из своей папки: многие (например, OBS) ищут свои файлы рядом с собой
    и без этого не стартуют. У ярлыков .lnk своя рабочая папка, их не трогаем."""
    folder = None
    if os.path.isfile(target) and not target.lower().endswith(".lnk"):
        folder = os.path.dirname(target) or None
    os.startfile(target, cwd=folder)


def launch_app(tile):
    open_path(tile["target"])


LAUNCHERS = {
    "app": launch_app,
    # "folder": launch_folder,
    # "command": launch_command,
}


def launch(tile):
    LAUNCHERS[tile["type"]](tile)
