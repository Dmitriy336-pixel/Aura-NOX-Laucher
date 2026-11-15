"""Навигация по папкам и файлам для команды «папка»: подсказки по ходу ввода, переход вглубь,
действия над найденным (открыть, терминал, VS Code, скопировать путь, список, поиск, плитка, избранное...)."""
import ctypes
import json
import os
import re
import shutil
import subprocess
import time

import i18n
import launchers
import storage
from commands import Paged, Reply
from config import FAVORITES_FILE
from i18n import tr

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
SEP = "\\"
SPLIT = re.compile(r"[\\/]")
HOME = os.path.expanduser("~")
MAX_ITEMS = 200
REMOVE_WORDS = ("убрать", "remove", "rm")


def _known(csidl):
    """Системная папка по номеру CSIDL (Документы, Рабочий стол... даже если их перенесли)."""
    buf = ctypes.create_unicode_buffer(260)
    try:
        if ctypes.windll.shell32.SHGetFolderPathW(None, csidl, None, 0, buf) == 0 and buf.value:
            return buf.value
    except (AttributeError, OSError):
        pass
    return None


# (имена, подпись, как узнать путь)
ROOTS = [
    (["загрузки", "downloads"], tr("Загрузки"), lambda: os.path.join(HOME, "Downloads")),
    (["документы", "documents"], tr("Документы"), lambda: _known(5)),
    (["рабочий", "desktop"], tr("Рабочий стол (папка)"), lambda: _known(0)),
    (["изображения", "pictures"], tr("Изображения"), lambda: _known(39)),
    (["видео", "videos"], tr("Видео"), lambda: _known(14)),
    (["музыка", "music"], tr("Музыка"), lambda: _known(13)),
    (["автозагрузка", "startup"], tr("Автозагрузка"), lambda: _known(7)),
    (["домой", "home"], tr("Домашняя папка"), lambda: HOME),
]

# (ключ, имена, описание, текст после действия: "" нет, "need" обязателен, "opt" по желанию, только для папок)
ACTIONS = [
    ("open", ["открыть", "open", "o"], tr("открыть в проводнике (файл: запустить)"), "", False),
    ("term", ["терминал", "term", "cmd"], tr("терминал в этой папке"), "", True),
    ("code", ["код", "code"], tr("открыть в VS Code"), "", False),
    ("copy", ["путь", "path", "copy"], tr("скопировать путь"), "", False),
    ("show", ["показать", "show"], tr("показать в проводнике"), "", False),
    ("ls", ["список", "ls"], tr("что лежит внутри"), "", True),
    ("find", ["найти", "find"], tr("найти по имени внутри, с подпапками: найти текст"), "need", True),
    ("new", ["создать", "new", "mkdir"], tr("создать подпапку: создать имя"), "need", True),
    ("tile", ["плитка", "tile"], tr("добавить плиткой на главный экран"), "", False),
    ("pin", ["закрепить", "pin"], tr("добавить в избранное: закрепить или закрепить имя"), "opt", True),
]


# ---------------------------------------------------------------- избранное
def load_favs():
    """{короткое имя в нижнем регистре: путь}."""
    try:
        with open(FAVORITES_FILE, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def save_favs(favs):
    storage.write_json(FAVORITES_FILE, favs)


def builtin_names():
    return {n for names, _title, _getter in ROOTS for n in names}


def favs_complete(args):
    """Подсказки для команды «избранное»: после слова «убрать» показываем имена."""
    word, sep, name = args.lstrip().partition(" ")
    if not sep or word.lower() not in REMOVE_WORDS:
        return []
    name = name.strip().lower()
    return [(f"{word} {n}", n, p) for n, p in sorted(load_favs().items()) if n.startswith(name)]


def favs_cmd(args):
    a = args.strip()
    favs = load_favs()
    if not a:
        if not favs:
            return Reply(tr("Избранных папок нет. Закрепить: папка путь закрепить"))
        return Paged(tr("Избранное"), [([n], p) for n, p in sorted(favs.items())], per_page=8)
    word, _, name = a.partition(" ")
    if word.lower() in REMOVE_WORDS:
        key = name.strip().lower()
        if key not in favs:
            return Reply(tr('Нет такого избранного: {v}', v=name.strip()), error=True)
        del favs[key]
        try:
            save_favs(favs)
        except OSError as e:
            return Reply(tr('Ошибка: {e}', e=e), error=True)
        return Reply(tr('Убрано: {v}', v=key))
    return Reply(tr("Введи избранное убрать имя"), error=True)


# ---------------------------------------------------------------- пути
def drives():
    try:
        mask = ctypes.windll.kernel32.GetLogicalDrives()
    except (AttributeError, OSError):
        return []
    return [f"{chr(65 + i)}:\\" for i in range(26) if mask >> i & 1]


def roots():
    """[(все имена, как показывать, путь, подпись)]: избранное, заготовки и диски."""
    ru = i18n.language() == "ru"
    items = []
    for name, path in sorted(load_favs().items()):
        if os.path.isdir(path):
            items.append(([name], name, path, tr("Избранное")))
    for names, title, getter in ROOTS:
        path = getter()
        if path and os.path.isdir(path):
            items.append((names, names[0] if ru else names[1], path, title))
    for drive in drives():
        items.append(([drive[:2].lower()], drive[:2], drive, tr("Диск")))
    return items


def split_root(text):
    """Первый отрезок пути (загрузки, имя из избранного, c:, ~) -> (папка, остальные отрезки) или None."""
    segs = SPLIT.split(text.strip())
    low = segs[0].strip().lower()
    base = None
    for names, _title, getter in ROOTS:
        if low in names:
            base = getter()
            break
    if base is None:
        base = load_favs().get(low)
    if base is None:
        if re.fullmatch(r"[a-z]:", low):
            base = low.upper() + SEP
        elif low == "~":
            base = HOME
    return (base, segs[1:]) if base else None


def resolve(text):
    """Введённый путь -> существующий путь на диске или None."""
    found = split_root(text) if text.strip() else None
    if not found:
        return None
    path, segs = found
    for seg in segs:
        if seg not in ("", "."):
            path = os.path.normpath(os.path.join(path, seg))  # «..» тоже работает
    return path if os.path.exists(path) else None


def list_children(folder, prefix=""):
    """[(имя, это папка)]: сначала папки, потом файлы; скрытые только если начали вводить имя."""
    prefix = prefix.lower()
    dirs, files = [], []
    try:
        with os.scandir(folder) as entries:
            for e in entries:
                if not e.name.lower().startswith(prefix):
                    continue
                try:
                    hidden = bool(getattr(e.stat(), "st_file_attributes", 0) & 2)
                    is_dir = e.is_dir()
                except OSError:
                    continue
                if hidden and not prefix:
                    continue
                (dirs if is_dir else files).append(e.name)
    except OSError:
        return []
    key = lambda n: n.lower()
    return [(n, True) for n in sorted(dirs, key=key)] + [(n, False) for n in sorted(files, key=key)]


def parse(text):
    """Если в начале уже стоит целый существующий путь и после него пробел: (текст пути, путь, остаток).
    Берём самый длинный подходящий кусок, поэтому имена папок с пробелами работают."""
    tokens = text.lstrip().split(" ")
    for k in range(len(tokens) - 1, 0, -1):
        candidate = " ".join(tokens[:k])
        if not candidate.strip() or candidate.endswith(" "):
            continue
        target = resolve(candidate)
        if target:
            return candidate, target, " ".join(tokens[k:])
    return None


def find_action(word):
    word = word.lower()
    for action in ACTIONS:
        if word in action[1]:
            return action
    hits = [a for a in ACTIONS if word and any(n.startswith(word) for n in a[1])]
    return hits[0] if len(hits) == 1 else None


# ---------------------------------------------------------------- подсказки
def short(text, limit=38):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def path_items(text):
    """Подсказки для пути, который ещё вводят: [(что подставить, метка, описание)]."""
    segs = SPLIT.split(text)
    if len(segs) == 1:  # ещё первый отрезок: заготовки, избранное и диски
        low = text.lower()
        return [(shown + SEP, shown, f"{title}  ({path})")
                for names, shown, path, title in roots() if not low or any(n.startswith(low) for n in names)]
    partial = segs[-1]
    prefix = text[:len(text) - len(partial)]
    parent = resolve(prefix)
    if not parent or not os.path.isdir(parent):
        return []
    items = []
    here = os.path.normpath(parent)
    if "..".startswith(partial) and os.path.dirname(here) not in ("", here):
        items.append((prefix + ".." + SEP, "..", tr("на уровень выше")))
    children = list_children(parent, partial)
    children.sort(key=lambda c: c[0].lower() != partial.lower())  # точное совпадение первым
    for name, is_dir in children:
        mark = SEP if is_dir else ""
        items.append((prefix + name + mark, short(name + mark), tr("папка") if is_dir else tr("файл")))
    return items[:MAX_ITEMS]


def find_items(path_text, target, text):
    """Результаты поиска как подсказки: Enter открывает найденное, Tab заходит в него."""
    found, _cut = find_in(target, text, limit=MAX_ITEMS, seconds=0.4)  # коротко: поиск идёт при каждом символе
    base = path_text.rstrip("\\/ ")
    return [(base + SEP + rel, short(rel), tr("папка") if is_dir else tr("файл")) for rel, is_dir in found]


def action_items(path_text, target, rest):
    """Действия после пути. None, если остаток не похож на действие (значит, это продолжение имени с пробелом)."""
    word, sep, extra = rest.partition(" ")
    word = word.lower()
    is_dir = os.path.isdir(target)
    ru = i18n.language() == "ru"
    found = []
    for action in ACTIONS:
        _key, names, description, text_mode, dir_only = action
        if dir_only and not is_dir:
            continue
        hit = word in names if sep else any(n.startswith(word) for n in names)
        if hit:
            shown = names[0] if ru else names[1]
            found.append((action, f"{path_text} {shown}" + (" " if text_mode else ""), shown, description))
    if sep:
        if not found:
            return None  # это не действие, а продолжение имени
        if found[0][0][0] == "find" and len(extra.strip()) >= 2:
            return find_items(path_text, target, extra.strip())
        return []  # действие выбрано, дальше человек пишет текст
    return [(insert, shown, description) for _a, insert, shown, description in found] or None


def complete(args):
    text = args.lstrip()
    parsed = parse(text)
    if parsed:
        items = action_items(*parsed)
        if items is not None:
            return items
    return path_items(text)


# ---------------------------------------------------------------- выполнение
def human(size):
    for unit in (tr("Б"), tr("КБ"), tr("МБ")):
        if size < 1024:
            return f"{size:.0f} {unit}"
        size /= 1024
    return f"{size:.1f} {tr('ГБ')}"


def find_in(folder, text, limit=100, seconds=1.5):
    """Поиск по имени с подпапками. Возвращает (найденное, прервано ли по времени)."""
    text = text.lower()
    found = []
    deadline = time.monotonic() + seconds
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in dirs + files:
            if text in name.lower():
                full = os.path.join(root, name)
                found.append((os.path.relpath(full, folder), os.path.isdir(full)))
                if len(found) >= limit:
                    return found, False
        if time.monotonic() > deadline:
            return found, True
    return found, False


def open_target(app, target):
    if os.path.isdir(target):
        app.after(50, lambda: subprocess.Popen(["explorer.exe", target]))
    else:
        app.after(50, lambda: launchers.open_path(target))


def do_action(app, target, action, arg):
    key, _names, _desc, text_mode, dir_only = action
    if dir_only and not os.path.isdir(target):
        return Reply(tr("Это файл, а не папка"), error=True)
    if text_mode == "need" and not arg:
        return Reply(tr("Укажи после действия имя или текст"), error=True)

    if key == "open":
        open_target(app, target)
        return None
    if key == "term":
        wt = shutil.which("wt")  # Windows Terminal, если есть
        if wt:
            app.after(50, lambda: subprocess.Popen([wt, "-d", target]))
        else:
            app.after(50, lambda: subprocess.Popen(["cmd.exe"], cwd=target, creationflags=NEW_CONSOLE))
        return None
    if key == "code":
        exe = shutil.which("code")
        if not exe:
            return Reply(tr("VS Code (команда code) не найден"), error=True)
        app.after(50, lambda: subprocess.Popen([exe, target], creationflags=NO_WINDOW))
        return None
    if key == "copy":
        app.clipboard_clear()
        app.clipboard_append(target)
        return Reply(tr('Путь скопирован: {v}', v=target))
    if key == "show":
        app.after(50, lambda: subprocess.Popen(["explorer.exe", f"/select,{target}"]))
        return None
    if key == "ls":
        items = list_children(target)
        if not items:
            return Reply(tr("Папка пуста"))
        lines = []
        for name, is_dir in items[:300]:
            if is_dir:
                lines.append(([name + SEP], tr("папка")))
            else:
                try:
                    size = human(os.path.getsize(os.path.join(target, name)))
                except OSError:
                    size = tr("файл")
                lines.append(([name], size))
        return Paged(target, lines, per_page=8)
    if key == "find":
        found, cut = find_in(target, arg)
        if not found:
            return Reply(tr("Ничего не найдено"))
        title = target + (f"  ({tr('Поиск прерван по времени')})" if cut else "")
        return Paged(title, [([rel], tr("папка") if d else tr("файл")) for rel, d in found], per_page=8)
    if key == "new":
        if re.search(r'[<>:"|?*]', arg):
            return Reply(tr('Ошибка: {e}', e=arg), error=True)
        path = os.path.join(target, arg)
        try:
            os.makedirs(path)
        except OSError as e:
            return Reply(tr('Ошибка: {e}', e=e), error=True)
        return Reply(tr('Создано: {v}', v=path))
    if key == "tile":
        return Reply(tr('Плитка «{v}» добавлена', v=app.add_tile_path(target)))
    if key == "pin":
        name = (arg or os.path.basename(target.rstrip("\\/"))).strip().lower()
        if not name or SPLIT.search(name) or ":" in name:
            return Reply(tr("Имя не должно содержать \\ / :"), error=True)
        if name in builtin_names():
            return Reply(tr("Имя занято встроенной папкой"), error=True)
        favs = load_favs()
        favs[name] = target
        try:
            save_favs(favs)
        except OSError as e:
            return Reply(tr('Ошибка: {e}', e=e), error=True)
        return Reply(tr('Закреплено: {name}', name=name))
    return None


def run(app, args):
    args = args.strip()
    if not args:
        return Reply(tr("Введи папка и путь: загрузки, документы, c:\\... Пробел после пути покажет действия"),
                     error=True)
    if args.lower() in ("корзина", "bin"):
        app.after(50, lambda: subprocess.Popen(["explorer.exe", "shell:RecycleBinFolder"]))
        return None
    target = resolve(args)
    if target:  # путь введён целиком: просто открываем
        open_target(app, target)
        return None
    parsed = parse(args)
    if not parsed:
        return Reply(tr('Нет такой папки: {args}', args=args), error=True)
    _text, target, rest = parsed
    word, _, extra = rest.partition(" ")
    action = find_action(word)
    if action is None:
        return Reply(tr('Нет такого действия: {v}', v=word), error=True)
    return do_action(app, target, action, extra.strip())