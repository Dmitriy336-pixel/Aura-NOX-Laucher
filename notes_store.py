"""Хранилище заметок: обычные .md-файлы в отдельной папке ВНЕ проекта.

Формат (по нему же можно читать и писать заметки из других программ):
  - одна заметка = один файл «<заголовок>.md» в общей папке;
  - имя файла без .md = заголовок заметки, содержимое файла = текст (UTF-8);
  - время изменения заметки = время изменения файла;
  - файлы *.tmp служебные (запись идёт через временный файл), их игнорировать.
"""
import ctypes
import json
import os
import re
import shutil
from i18n import tr

EXT = ".md"
FOLDER_NAME = "SharedNotes"
PINS_FILE = ".pins.json"   # закреплённые заметки: список заголовков, лежит в самой папке заметок
INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')  # символы, запрещённые в именах файлов Windows
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def default_dir():
    """Папка заметок по умолчанию: «Документы\\SharedNotes» (настоящие «Документы», даже если перенесены)."""
    docs = None
    try:
        buf = ctypes.create_unicode_buffer(260)
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buf) == 0:  # 5 = CSIDL_PERSONAL
            docs = buf.value
    except (AttributeError, OSError):
        pass
    if not docs:
        docs = os.path.join(os.path.expanduser("~"), "Documents")
    return os.path.join(docs, FOLDER_NAME)


def clean_title(title):
    """Заголовок -> безопасное имя файла."""
    name = INVALID.sub("", title).strip(" .")[:100].strip(" .")
    if not name:
        return tr("Без названия")
    if name.split(".")[0].upper() in RESERVED:
        name += "_"
    return name


class NoteStore:
    def __init__(self, folder):
        self.folder = os.path.normpath(folder)
        os.makedirs(self.folder, exist_ok=True)  # может бросить OSError: ловит вызывающий

    def path(self, title):
        return os.path.join(self.folder, title + EXT)

    def exists(self, title):
        return os.path.exists(self.path(title))

    def mtime(self, title):
        try:
            return os.path.getmtime(self.path(title))
        except OSError:
            return None

    def list_notes(self, sort="date"):
        """[(заголовок, время изменения)]: свежие сверху (sort="date") или по алфавиту (sort="name")."""
        items = []
        with os.scandir(self.folder) as entries:
            for entry in entries:
                stem, ext = os.path.splitext(entry.name)
                if ext.lower() == EXT and entry.is_file():
                    items.append((stem, entry.stat().st_mtime))
        if sort == "name":
            items.sort(key=lambda item: item[0].lower())
        else:
            items.sort(key=lambda item: item[1], reverse=True)
        return items

    def copy_notes_to(self, dst_folder):
        """Копирует все заметки в другую папку, не перезаписывая одноимённые. Возвращает (скопировано, пропущено)."""
        os.makedirs(dst_folder, exist_ok=True)
        copied = skipped = 0
        for title, _mtime in self.list_notes():
            target = os.path.join(dst_folder, title + EXT)
            if os.path.exists(target):
                skipped += 1
                continue
            shutil.copy2(self.path(title), target)
            copied += 1
        return copied, skipped

    def read(self, title):
        """(текст, время изменения). Переводы строк приводятся к \\n."""
        path = self.path(title)
        with open(path, encoding="utf-8-sig", errors="replace") as f:
            text = f.read()
        return text, os.path.getmtime(path)

    def write(self, title, text):
        """Пишет заметку целиком через временный файл: читающая программа не увидит половину текста."""
        path = self.path(title)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
        return os.path.getmtime(path)

    def rename(self, old, new):
        os.replace(self.path(old), self.path(new))
        if self.is_pinned(old):  # закрепление переезжает вместе с заметкой
            self.set_pinned(old, False)
            self.set_pinned(new, True)

    def delete(self, title):
        os.remove(self.path(title))
        self.set_pinned(title, False)

    # --- закреплённые заметки ---
    def pinned(self):
        """Заголовки закреплённых заметок (без учёта регистра, как имена файлов Windows)."""
        try:
            with open(os.path.join(self.folder, PINS_FILE), encoding="utf-8-sig") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return []
        return [t for t in data if isinstance(t, str)] if isinstance(data, list) else []

    def is_pinned(self, title):
        return title.lower() in {t.lower() for t in self.pinned()}

    def set_pinned(self, title, value):
        pins = [t for t in self.pinned() if t.lower() != title.lower()]
        if value:
            pins.append(title)
        path = os.path.join(self.folder, PINS_FILE)
        if not pins and not os.path.exists(path):
            return
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(pins, f, ensure_ascii=False)
        os.replace(tmp, path)

    def unique_title(self, wanted, own=None):
        """Свободный заголовок: если имя занято другой заметкой, добавляет (2), (3)...
        own: заметка, которая сама носит это имя (её имя занятым не считается)."""
        base = clean_title(wanted)
        taken = {name.lower() for name, _mtime in self.list_notes()}  # без учёта регистра, как в Windows
        title, n = base, 2
        while title.lower() != (own or "").lower() and title.lower() in taken:
            title = f"{base} ({n})"
            n += 1
        return title
