"""Свои команды пользователя: хранятся в commands.json и подключаются к командной строке.

Запись команды: {"names": ["ютуб", "yt"], "description": "...", "action": "open", "target": "..."}
  action "open"  - открыть программу, файл, папку или сайт (target: путь или адрес);
  action "set"   - открыть несколько по очереди (target: по одному в строке);
  action "shell" - выполнить команду командной строки Windows.
В target можно написать {}: туда подставится текст, введённый после команды
(в адресах сайтов он кодируется сам, так получаются быстрые поиски)."""
import json
import os
import re
import shutil
import subprocess
import webbrowser
import launchers
import storage

from functools import partial
from urllib.parse import quote_plus

from commands import Reply
from config import USER_COMMANDS_FILE
from i18n import tr

ACTIONS = {"open": tr("Открыть"), "set": tr("Набор"), "shell": tr("Команда")}
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
URI = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.\-]+:")  # http:, shell:, ms-settings: (а не диск C:)


def load():
    try:
        with open(USER_COMMANDS_FILE, encoding="utf-8-sig") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        os.replace(USER_COMMANDS_FILE, USER_COMMANDS_FILE + ".broken")  # повреждённый файл не затираем
        return []
    return [e for e in data if isinstance(e, dict) and e.get("names") and e.get("target")]


def save(entries):
    storage.write_json(USER_COMMANDS_FILE, entries)


def parse_names(text):
    """'ютуб, yt' -> ['ютуб', 'yt']"""
    return [n for n in re.split(r"[,\s]+", text.strip().lower()) if n]


def validate(entry, other_names, builtin_names):
    """Текст ошибки или None, если запись в порядке."""
    if not entry["names"]:
        return tr("Укажи хотя бы одно название команды")
    for name in entry["names"]:
        if name in builtin_names:
            return tr('«{name}» уже занято встроенной командой', name=name)
        if name in other_names:
            return tr('«{name}» уже используется другой твоей командой', name=name)
    if not entry["target"].strip():
        return tr("Укажи, что открыть или выполнить")
    return None


def summary(entry):
    """Короткое описание для списка в настройках: своё описание или начало того, что запускается."""
    if entry.get("description"):
        return entry["description"]
    first = entry["target"].strip().splitlines()[0]
    return first if len(first) <= 45 else first[:44] + "…"


def describe(entry):
    """Описание для списка команд («помощь»)."""
    if entry.get("description"):
        return entry["description"]
    return {"open": tr("открыть "), "set": tr("открыть набор: "), "shell": tr("выполнить ")}[entry["action"]] + summary(entry)


def _expand(path):
    return os.path.expandvars(os.path.expanduser(path.strip()))

def command_dir(command):
    """Рабочая папка для команды: папка программы, с которой она начинается (как у ярлыка)."""
    command = command.strip()
    if command.startswith('"') and command.find('"', 1) > 0:
        first = command[1:command.find('"', 1)]
    else:
        first = command.split(" ")[0]
    first = _expand(first)
    return os.path.dirname(first) if os.path.isfile(first) else None

def open_target(target):
    target = target.strip()
    if target.lower().startswith(("http://", "https://")):
        webbrowser.open(target)
    else:
        launchers.open_path(_expand(target))  # программа, файл, папка, shell: и ms-settings:


def missing(target):
    """Описание проблемы, если обычный путь не найден (адреса и shell: не проверяем)."""
    target = target.strip()
    if URI.match(target):
        return None
    path = _expand(target)
    if os.path.exists(path) or shutil.which(path):
        return None
    return tr('Не найдено: {target}', target=target)


def fill(template, args, as_url):
    """Подставляет текст после команды вместо {}; в адресах кодирует его."""
    return template.replace("{}", quote_plus(args) if as_url else args)


def make_handler(app, entry):
    names, action = entry["names"], entry["action"]
    target = entry["target"].strip()

    def handler(args):
        if "{}" in target and not args:
            return Reply(tr('Нужен текст после команды, например: {v} что-нибудь', v=names[0]), error=True)
        if action == "shell":
            command = fill(target, args, False)
            app.after(50, lambda: subprocess.Popen(
                command, shell=True, cwd=command_dir(command), creationflags=NO_WINDOW))
            return None
        lines = [target] if action == "open" else [ln.strip() for ln in target.splitlines() if ln.strip()]
        ready = []
        for line in lines:
            what = fill(line, args, line.lower().startswith("http"))
            problem = missing(what)
            if problem:
                return Reply(problem, error=True)  # ничего не запускаем, пока не поправлена ошибка
            ready.append(what)
        for i, what in enumerate(ready):
            app.after(50 + i * 250, partial(open_target, what))
        return None

    return handler


def register_all(reg, app):
    for entry in load():
        if entry.get("action") in ACTIONS:
            reg.add(entry["names"], describe(entry), make_handler(app, entry))