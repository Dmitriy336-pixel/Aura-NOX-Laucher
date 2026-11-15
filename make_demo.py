"""Готовит чистую копию лаунчера для съёмки трейлера и показа функций.

Запуск из папки проекта тем же Python, что и main.py:
    python make_demo.py                      # русская демо-копия рядом с проектом
    python make_demo.py --lang en            # язык интерфейса: ru, en или uk
    python make_demo.py --theme "cyber neon" # какую тему включить (имя папки в themes)
    python make_demo.py D:\\Demo              # куда положить копию

Что получится: отдельная папка с копией программы, в которой свои плитки, команды, заметки, избранные
папки и история команд. Ваши настоящие данные не трогаются, потому что лаунчер хранит всё рядом с собой.
Повторный запуск пересоздаёт демо-данные заново (папку с кодом и темы он при этом только обновляет).
Список плиток, команд и заметок можно поправить ниже, в блоке «ЧТО ПОКАЗЫВАЕМ»."""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- ЧТО ПОКАЗЫВАЕМ
# Плитки: (название, возможные пути или имена программ: берётся первый найденный). Нет программы: плитки не будет.
PF = os.environ.get("ProgramFiles", r"C:\Program Files")
PF86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
TILES = [
    ("Notepad", ["notepad.exe"]),
    ("Calculator", ["calc.exe"]),
    ("Paint", ["mspaint.exe"]),
    ("File Explorer", ["explorer.exe"]),
    ("Edge", [PF86 + r"\Microsoft\Edge\Application\msedge.exe", PF + r"\Microsoft\Edge\Application\msedge.exe"]),
    ("Chrome", [PF + r"\Google\Chrome\Application\chrome.exe", PF86 + r"\Google\Chrome\Application\chrome.exe"]),
    ("Task Manager", ["taskmgr.exe"]),
    ("Snipping Tool", ["snippingtool.exe"]),
    ("Terminal", ["wt.exe", "cmd.exe"]),
    ("Projects", ["{demo}\\Projects"]),   # {demo}: папка DemoFiles внутри демо-копии
    ("Documents", ["{demo}\\Documents"]),
]
COLORS = ["#6366f1", "#8b5cf6", "#ec4899", "#f43f5e", "#f59e0b", "#10b981", "#06b6d4", "#3b82f6"]

# Свои команды (имя, что делает, действие, цель). {} в цели: подставится текст после команды.
COMMANDS = {
    "ru": [("yt", "поиск на YouTube", "open", "https://www.youtube.com/results?search_query={}"),
           ("gg", "поиск в Google", "open", "https://www.google.com/search?q={}"),
           ("work", "рабочий набор: блокнот и калькулятор", "set", "notepad.exe\ncalc.exe")],
    "en": [("yt", "search YouTube", "open", "https://www.youtube.com/results?search_query={}"),
           ("gg", "search Google", "open", "https://www.google.com/search?q={}"),
           ("work", "work set: notepad and calculator", "set", "notepad.exe\ncalc.exe")],
    "uk": [("yt", "пошук на YouTube", "open", "https://www.youtube.com/results?search_query={}"),
           ("gg", "пошук у Google", "open", "https://www.google.com/search?q={}"),
           ("work", "робочий набір: блокнот і калькулятор", "set", "notepad.exe\ncalc.exe")],
}

# История команд (стрелка вверх в пустой командной строке). Команды набраны английскими именами: они работают на любом языке.
HISTORY = ["vol +", "calc 1299*0.8", "folder demo\\Projects\\ ls", "yt lo-fi music", "desk 2", "jot call mom at 6"]

# Заметки: (название, текст). Первая закрепляется.
NOTES = {
    "ru": [("План трейлера", "# План трейлера\n\n1. Плитки: добавить, переставить, покрасить\n2. Командная строка\n3. Заметки\n4. Темы и звуки\n"),
           ("Идеи", "# Идеи\n\n- сделать тему с металлом\n- добавить звук на каждое действие\n"),
           ("Покупки", "# Покупки\n\n- хлеб\n- кофе\n- батарейки\n")],
    "en": [("Trailer plan", "# Trailer plan\n\n1. Tiles: add, rearrange, recolor\n2. The command bar\n3. Notes\n4. Themes and sounds\n"),
           ("Ideas", "# Ideas\n\n- make a metal theme\n- add a sound for every action\n"),
           ("Shopping", "# Shopping\n\n- bread\n- coffee\n- batteries\n")],
    "uk": [("План трейлера", "# План трейлера\n\n1. Плитки: додати, переставити, пофарбувати\n2. Командний рядок\n3. Нотатки\n4. Теми й звуки\n"),
           ("Ідеї", "# Ідеї\n\n- зробити тему з металом\n- додати звук на кожну дію\n"),
           ("Покупки", "# Покупки\n\n- хліб\n- кава\n- батарейки\n")],
}

# Файлы для показа навигации по папкам (команда «папка demo\...»)
DEMO_FILES = {
    "Projects/Website redesign/index.html": "<h1>Website redesign</h1>\n",
    "Projects/Website redesign/notes.txt": "Colors, fonts, layout.\n",
    "Projects/Mobile app/README.md": "# Mobile app\n",
    "Projects/Video trailer/script.md": "# Script\n",
    "Documents/Budget 2026.txt": "Rent, food, internet.\n",
    "Documents/Meeting notes.md": "# Meeting\n",
    "Music/playlist.txt": "lo-fi beats\n",
}
PHOTOS = [("sunrise.png", (255, 170, 90), (120, 80, 200)), ("ocean.png", (20, 120, 200), (10, 40, 90)),
          ("forest.png", (60, 160, 90), (15, 60, 40))]
# ---------------------------------------------------------------- конец блока


SKIP_DIRS = {"__pycache__", "icons", "demo", ".git"}
SKIP_FILES = {"make_demo.py", "check_update.py", "settings.json", "tiles.json", "commands.json",
              "favorites.json", "history.json", "Launcher.spec", "icon_probe.py", "convert_icon.py"}


def copy_program(dest):
    """Код, иконка, темы, звуки и готовые иконки. Данные пользователя (json, icons) не копируются."""
    for name in os.listdir(HERE):
        path = os.path.join(HERE, name)
        if os.path.isdir(path):
            if name in SKIP_DIRS or os.path.abspath(path) == os.path.abspath(dest):
                continue
            target = os.path.join(dest, name)
            shutil.copytree(path, target, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "debug.txt", "debug.log"))
        elif name in SKIP_FILES or name.startswith("apply_"):
            continue
        elif name.endswith((".py", ".ico", ".spec", ".png")) or name == "README.txt":
            shutil.copy2(path, os.path.join(dest, name))


def make_demo_files(demo):
    for rel, text in DEMO_FILES.items():
        path = os.path.join(demo, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    photos = os.path.join(demo, "Photos")
    os.makedirs(photos, exist_ok=True)
    try:
        from PIL import Image
    except ImportError:
        return
    for name, top, bottom in PHOTOS:
        image = Image.new("RGB", (640, 360))
        for y in range(360):
            k = y / 359
            row = tuple(int(top[i] * (1 - k) + bottom[i] * k) for i in range(3))
            image.paste(row, (0, y, 640, y + 1))
        image.save(os.path.join(photos, name))


def find_program(options, demo):
    for option in options:
        option = option.replace("{demo}", demo)
        if os.path.isabs(option):
            if os.path.exists(option):
                return option.replace("\\", "/")
        else:
            found = shutil.which(option)
            if found:
                return found.replace("\\", "/")
    return None


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def terms_version():
    """Версия условий из legal.py: чтобы в демо не показывалось окно первого запуска."""
    with open(os.path.join(HERE, "legal.py"), encoding="utf-8") as f:
        match = re.search(r'^TERMS_VERSION\s*=\s*"([^"]*)"', f.read(), re.M)
    return match.group(1) if match else "1"


def main():
    parser = argparse.ArgumentParser(description="Демо-копия лаунчера для съёмки")
    parser.add_argument("dest", nargs="?", default=os.path.join(os.path.dirname(HERE), os.path.basename(HERE) + "_demo"))
    parser.add_argument("--lang", choices=["ru", "en", "uk"], default="ru")
    parser.add_argument("--theme", default="default")
    args = parser.parse_args()
    dest = os.path.abspath(args.dest)
    if dest == HERE:
        sys.exit("Укажите другую папку: демо нельзя делать поверх рабочего лаунчера.")
    os.makedirs(dest, exist_ok=True)

    print("Копирую программу, темы и звуки...")
    copy_program(dest)
    demo = os.path.join(dest, "DemoFiles")
    make_demo_files(demo)

    notes_dir = os.path.join(dest, "DemoNotes")
    os.makedirs(notes_dir, exist_ok=True)
    for title, text in NOTES[args.lang]:
        with open(os.path.join(notes_dir, title + ".md"), "w", encoding="utf-8") as f:
            f.write(text)
    write_json(os.path.join(notes_dir, ".pins.json"), [NOTES[args.lang][0][0]])

    tiles = []
    for name, options in TILES:
        target = find_program(options, demo)
        if target is None:
            print(f"  нет на этом компьютере, пропускаю плитку: {name}")
            continue
        tiles.append({"type": "app", "name": name, "target": target, "key": "123456789qwertyuiop"[len(tiles)],
                      "color": COLORS[len(tiles) % len(COLORS)]})
    write_json(os.path.join(dest, "tiles.json"), tiles)

    write_json(os.path.join(dest, "commands.json"), [
        {"names": [n], "description": d, "action": a, "target": t} for n, d, a, t in COMMANDS[args.lang]])
    write_json(os.path.join(dest, "favorites.json"),
               {"demo": demo, "projects": os.path.join(demo, "Projects")})
    write_json(os.path.join(dest, "history.json"), HISTORY)
    write_json(os.path.join(dest, "settings.json"), {
        "autostart": False,            # запись автозапуска общая для всех копий: в демо её не трогаем
        "background_mode": False,
        "after_launch": "minimize",
        "columns": 4,
        "window_scale": 70,
        "tile_label": "below",
        "tile_show_key": True,
        "confirm_delete": False,
        "theme_name": args.theme,
        "theme_mode": "dark",
        "language": args.lang,
        "terms_seen": terms_version(),
        "sounds_enabled": True,
        "sound_volume": 70,
        "notes_dir": notes_dir,
    })

    print("Подбираю иконки плиткам...")
    code = (
        "import json, icon_tools\n"
        "tiles = json.load(open('tiles.json', encoding='utf-8'))\n"
        "for t in tiles:\n"
        "    icon = icon_tools.auto_icon(t)\n"
        "    if icon: t['icon'] = icon\n"
        "json.dump(tiles, open('tiles.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)\n")
    done = subprocess.run([sys.executable, "-c", code], cwd=dest, capture_output=True, text=True)
    if done.returncode != 0:
        print("  иконки подобрать не вышло (плитки останутся без картинок). Подробности:")
        print("  " + (done.stderr.strip().splitlines() or ["?"])[-1])

    print(f"\nГотово: {dest}")
    print("Запуск демо:  cd \"%s\"  и  python main.py" % dest)
    print("Перед съёмкой закройте основной лаунчер (у обоих одни и те же горячие клавиши).")
    print("Не включайте «Автозапуск» в демо: запись в реестре общая и заменит автозапуск основного.")


if __name__ == "__main__":
    main()
