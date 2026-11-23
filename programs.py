"""Поиск установленных программ, чтобы добавить плитку, не зная, где программа лежит.
Быстрый список: ярлыки из меню «Пуск» и с рабочего стола плюс программы из реестра (App Paths).
Поиск на диске медленнее: обходит папки с программами и ищет .exe по имени; запускается по кнопке.
Модуль не зависит от Qt: окно лежит в add_program.py."""
import os
import string
import time
from typing import NamedTuple

SKIP_NAMES = ("uninstall", "unins", "удалить", "удаление", "деинстал")  # ярлыки удаления программ не нужны
SKIP_EXE = ("unins", "uninstall", "crash", "update", "updater", "helper", "vc_redist", "dxsetup")
SKIP_DIRS = {"windows", "$recycle.bin", "system volume information", "appdata", "node_modules", ".git",
             "winsxs", "$windows.~bt", "$windows.~ws"}


class Program(NamedTuple):
    name: str
    path: str


def _skip_name(name):
    low = name.lower()
    return any(word in low for word in SKIP_NAMES)


def shortcut_roots():
    """Папки, где Windows хранит ярлыки установленных программ."""
    env = os.environ
    roots = [
        os.path.join(env.get("ProgramData", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(env.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs"),
        os.path.join(env.get("USERPROFILE", ""), "Desktop"),
        os.path.join(env.get("PUBLIC", ""), "Desktop"),
    ]
    return [r for r in roots if r and os.path.isdir(r)]


def scan_shortcuts(roots=None):
    found = {}
    for root in (shortcut_roots() if roots is None else roots):
        for folder, _dirs, files in os.walk(root):
            for file in files:
                if not file.lower().endswith(".lnk"):
                    continue
                name = file[:-4]
                if not _skip_name(name):
                    found.setdefault(name.lower(), Program(name, os.path.join(folder, file)))
    return list(found.values())


def scan_app_paths():
    """Программы, которые сами записались в реестр (Chrome, Word и многие другие)."""
    try:
        import winreg
    except ImportError:  # не Windows
        return []
    base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
    found = []
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                key = winreg.OpenKey(hive, base, 0, winreg.KEY_READ | view)
            except OSError:
                continue
            with key:
                index = 0
                while True:
                    try:
                        sub = winreg.EnumKey(key, index)
                    except OSError:
                        break
                    index += 1
                    if not sub.lower().endswith(".exe"):
                        continue
                    try:
                        with winreg.OpenKey(key, sub) as sub_key:
                            path = winreg.QueryValue(sub_key, None)
                    except OSError:
                        continue
                    path = os.path.expandvars((path or "").strip().strip('"'))
                    if os.path.isfile(path) and not _skip_name(sub[:-4]):
                        found.append(Program(sub[:-4], path))
    return found


def scan():
    """Все программы, которые можно показать сразу. Ярлыки важнее записей реестра: у них понятные названия."""
    shortcuts = scan_shortcuts()
    names = [p.name.lower() for p in shortcuts]
    result = list(shortcuts)
    seen = {p.path.lower() for p in shortcuts}
    for prog in scan_app_paths():
        stem = prog.name.lower()
        # «chrome» уже есть как ярлык «Google Chrome»: второй раз не добавляем
        if prog.path.lower() in seen or any(stem in name for name in names):
            continue
        seen.add(prog.path.lower())
        result.append(prog)
    return result


def search(items, query):
    """Программы, в названии которых есть все слова запроса. Сначала те, что начинаются с запроса."""
    words = query.lower().split()
    if not words:
        return sorted(items, key=lambda p: p.name.lower())
    ranked = []
    for prog in items:
        name = prog.name.lower()
        if not all(word in name for word in words):
            continue
        first = words[0]
        rank = 0 if name.startswith(first) else (1 if " " + first in name else 2)
        ranked.append((rank, name, prog))
    ranked.sort(key=lambda t: (t[0], t[1]))
    return [prog for _rank, _name, prog in ranked]


def disk_roots():
    """(папка, глубина поиска): сначала места, где обычно лежат программы, потом корни остальных дисков."""
    env = os.environ
    roots = [(env.get("ProgramFiles"), 5), (env.get("ProgramFiles(x86)"), 5),
             (os.path.join(env.get("LOCALAPPDATA", ""), "Programs"), 4), (env.get("APPDATA"), 3)]
    roots += [(f"{letter}:\\", 3) for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]
    return [(root, depth) for root, depth in roots if root and os.path.isdir(root)]


def walk_disk(query, cancel, roots=None, max_seconds=40):
    """Ищет .exe, в имени которых (или в имени их папки) есть все слова запроса. Генератор: результаты идут по мере нахождения.
    cancel: threading.Event, по нему поиск можно остановить. Не дольше max_seconds."""
    words = query.lower().split()
    if not words:
        return
    deadline = time.monotonic() + max_seconds
    seen = set()
    for root, max_depth in (disk_roots() if roots is None else roots):
        root = root.rstrip("\\/")
        for folder, dirs, files in os.walk(root):
            if cancel.is_set() or time.monotonic() > deadline:
                return
            depth = folder[len(root):].count(os.sep)
            if depth >= max_depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
            parent = os.path.basename(folder).lower()
            for file in files:
                if not file.lower().endswith(".exe"):
                    continue
                stem = file[:-4]
                low = stem.lower()
                if any(bad in low for bad in SKIP_EXE):
                    continue
                if not all(word in f"{low} {parent}" for word in words):
                    continue
                path = os.path.join(folder, file)
                if path.lower() not in seen:
                    seen.add(path.lower())
                    yield Program(stem, path)
