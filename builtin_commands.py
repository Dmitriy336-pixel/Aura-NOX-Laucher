"""Встроенные команды командной строки. Новая команда = одна запись reg.add(...) в build_registry.
У команд, которым нужны аргументы, есть подсказки (complete): они строятся из того, что есть сейчас
(сколько столов, какие окна открыты), поэтому «рб 1», «рб 2»... прописывать не нужно."""
import subprocess
import webbrowser
from urllib.parse import quote_plus

import calc
import firstrun
import user_commands
import winapi
from config import SCREENSHOT_DELAY_MS
from notes_store import NoteStore, default_dir
from commands import CommandRegistry, Paged, Reply
import i18n
import path_nav
from i18n import tr

SEARCH_URL = "https://www.google.com/search?q="  # поисковик для команды «поиск»
SHUTDOWN_DELAY = 30                              # секунд до выключения, чтобы успеть передумать
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)




def short(text, limit=60):
    return text if len(text) <= limit else text[:limit - 1] + "…"


def build_registry(app):
    reg = CommandRegistry()

    def later(action, delay=50):
        """Обработчик, который запускает действие чуть позже: строка успевает закрыться раньше."""
        def handler(args):
            app.after(delay, action)  # возвращаем None, значит, строка закроется
        return handler

    # --- помощь и команды самого лаунчера ---
    def help_cmd(args):
        lines = [(c.names, c.description) for c in reg.commands]
        page = int(args) - 1 if args.isdigit() else 0
        return Paged(tr("Команды"), lines, page=page)

    reg.add(["помощь", "help"], tr("список команд (помощь 2 — вторая страница)"), help_cmd)
    reg.add(["настройки", "settings"], tr("открыть настройки"), later(app.open_settings))
    reg.add(["скрыть", "hide"], tr("спрятать лаунчер"), later(app.hide_window))
    reg.add(["выход", "exit", "quit"], tr("закрыть лаунчер полностью"), later(app.quit_app))

    # --- рабочие столы ---
    def desk_complete(args):
        count, index = winapi.desktop_state()
        items = [
            (str(i), str(i), tr('Рабочий стол {i}', i=i) + (tr("  (сейчас здесь)") if i == index else ""))
            for i in range(1, count + 1)
        ]
        items.append(("+", "+", tr("создать новый стол")))
        if count > 1:
            items.append(("-", "-", tr("закрыть текущий стол")))
        a = args.strip()
        return [item for item in items if item[0].startswith(a)] if a else items

    def desk_cmd(args):
        count, index = winapi.desktop_state()
        a = args.strip().lower()
        if not a:
            where = tr('сейчас стол {index} из {count}', index=index, count=count) if index else tr('всего столов: {count}', count=count)
            return Reply(tr('Рабочие столы: {where}. Введи рб 1–{count}, рб + (новый) или рб - (закрыть)', where=where, count=count))
        if a in ("+", "new", "нов"):
            app.after(50, winapi.desktop_new)
            return None
        if a in ("-", "close", "закр"):
            if count == 1:
                return Reply(tr("Это единственный рабочий стол, закрывать нечего"), error=True)
            app.after(50, winapi.desktop_close)
            return None
        if a.isdigit():
            target = int(a)
            if not 1 <= target <= count:
                return Reply(tr('Есть только столы 1–{count}', count=count), error=True)
            if target == index:
                return Reply(tr('Ты уже на столе {target}', target=target))
            app.after(50, lambda: winapi.desktop_go(target, count, index))
            return None
        return Reply(tr("Не понял. Введи рб 1–N, рб + или рб -"), error=True)

    reg.add(["рб", "стол", "desk"], tr("рабочие столы: рб 2 — перейти, рб + — новый, рб - — закрыть"),
            desk_cmd, desk_complete)

    # --- открытые окна ---
    def win_complete(args):
        a = args.strip().lower()
        items = []
        for number, (_hwnd, title) in enumerate(winapi.list_windows(), start=1):
            if a:
                matches = str(number).startswith(a) if a.isdigit() else a in title.lower()
                if not matches:
                    continue
            items.append((str(number), str(number), short(title)))
        return items

    def win_cmd(args):
        windows = winapi.list_windows()
        a = args.strip().lower()
        if not a:
            return Reply(tr('Открыто окон: {v}. Введи окно и номер или часть названия', v=len(windows)))
        if a.isdigit():
            number = int(a)
            if not 1 <= number <= len(windows):
                return Reply(tr('Окна с номером {number} нет, всего окон: {v}', number=number, v=len(windows)), error=True)
            hwnd = windows[number - 1][0]
        else:
            hwnds = [h for h, title in windows if a in title.lower()]
            if not hwnds:
                return Reply(tr('Нет окна со словом «{v}»', v=args.strip()), error=True)
            hwnd = hwnds[0]
        app.after(50, lambda: winapi.focus_window(hwnd))
        return None

    reg.add(["окно", "пр", "программа", "win"],
            tr("перейти к открытому окну: по номеру или части названия"), win_cmd, win_complete)

    # --- звук ---
    def vol_complete(args):
        mute = "mute" if i18n.language() != "ru" else "выкл"  # подсказка на языке интерфейса (оба слова понимаются)
        items = [("+", "+", tr("громче на 10%")), ("-", "-", tr("тише на 10%")),
                 (mute, mute, tr("включить или выключить звук"))]
        a = args.strip().lower()
        return [item for item in items if item[0].startswith(a)] if a else items

    def vol_cmd(args):
        a = args.strip().lower()
        if a in ("выкл", "вкл", "mute", "m"):
            winapi.volume("mute")
            return Reply(tr("Звук переключён"))
        if a[:1] in ("+", "-"):
            percent = int(a[1:]) if a[1:].isdigit() else 10
            winapi.volume("up" if a[0] == "+" else "down", max(1, percent // 2))
            return Reply((tr("Громче") if a[0] == "+" else tr("Тише")) + tr(' на {percent}%', percent=percent))
        return Reply(tr("Введи громкость + или -, можно с числом (громкость +20), либо выкл"), error=True)

    reg.add(["громкость", "гр", "volume", "vol"], tr("громкость: + громче, - тише, выкл — звук"), vol_cmd, vol_complete)

    # --- питание ---
    def power_cmd(flag, what):
        def handler(args):
            seconds = max(5, min(3600, int(args))) if args.isdigit() else SHUTDOWN_DELAY
            done = subprocess.run(["shutdown", flag, "/t", str(seconds)], creationflags=NO_WINDOW)
            if done.returncode != 0:
                return Reply(tr("Не получилось: возможно, выключение уже запланировано. Введи «отмена»"), error=True)
            return Reply(tr('{what} через {seconds} с. Команда «отмена» остановит', what=what, seconds=seconds))
        return handler

    def cancel_cmd(args):
        done = subprocess.run(["shutdown", "/a"], creationflags=NO_WINDOW)
        if done.returncode != 0:
            return Reply(tr("Сейчас ничего не запланировано"), error=True)
        return Reply(tr("Выключение отменено"))

    reg.add(["блок", "lock"], tr("заблокировать компьютер"), later(winapi.lock))
    reg.add(["выключить", "shutdown", "off"],
            tr('выключить компьютер через {SHUTDOWN_DELAY} с (можно указать секунды)', SHUTDOWN_DELAY=SHUTDOWN_DELAY),
            power_cmd("/s", tr("Выключение")))
    reg.add(["перезагрузить", "restart", "reboot"],
            tr('перезагрузить компьютер через {SHUTDOWN_DELAY} с', SHUTDOWN_DELAY=SHUTDOWN_DELAY), power_cmd("/r", tr("Перезагрузка")))
    reg.add(["отмена", "cancel", "abort"], tr("отменить запланированное выключение или перезагрузку"), cancel_cmd)

    # --- режим высокой производительности ---
    def perf_complete(args):
        on, off = ("on", "off") if i18n.language() != "ru" else ("вкл", "выкл")
        items = [(on, on, tr("включить высокую производительность")), (off, off, tr("вернуть прежнюю схему питания"))]
        a = args.strip().lower()
        return [item for item in items if item[0].startswith(a)] if a else items

    def perf_cmd(args):
        a = args.strip().lower()
        if a and a not in ("вкл", "on", "1", "выкл", "off", "0"):
            return Reply(tr("Введи производительность вкл, выкл или без слов, чтобы переключить"), error=True)
        want = None if not a else a in ("вкл", "on", "1")
        text, error = app.toggle_performance(want)
        return Reply(text, error=error)

    reg.add(["производительность", "perf", "turbo"],
            tr("режим высокой производительности: вкл, выкл или переключить"), perf_cmd, perf_complete)

    # --- заметки ---
    reg.add(["заметки", "notes", "note"], tr("открыть окно заметок"), later(app.open_notes))
    reg.add(["условия", "terms"], tr("условия использования"), later(lambda: firstrun.TermsWindow(app)))

    # --- папки, поиск, скриншот, калькулятор ---
    def search_cmd(args):
        if not args:
            return Reply(tr("Введи поиск и текст запроса, например: поиск погода"), error=True)
        app.after(50, lambda: webbrowser.open(SEARCH_URL + quote_plus(args)))
        return None

    def calc_cmd(args):
        if not args:
            return Reply(tr("Введи счёт и выражение, например: счёт 2+2*3"), error=True)
        try:
            return Reply(f"{args} = {calc.calculate(args)}")
        except ZeroDivisionError:
            return Reply(tr("Деление на ноль"), error=True)
        except (ValueError, SyntaxError, OverflowError) as e:
            return Reply(tr('Не получилось посчитать: {e}', e=e), error=True)

    reg.add(["папка", "folder", "dir"],
            tr("папки и файлы: папка загрузки\\..., пробел после пути покажет действия"),
            lambda args: path_nav.run(app, args), path_nav.complete)

    # --- запуск плиток по названию ---
    def run_complete(args):
        a = args.strip().lower()
        return [(t["name"], t["name"], t.get("target", "")) for t in app.tiles
                if not a or a in t["name"].lower()]

    def run_cmd(args):
        a = args.strip().lower()
        if not a:
            return Reply(tr("Введи запуск и название плитки"), error=True)
        found = [t for t in app.tiles if t["name"].lower() == a] or [t for t in app.tiles if a in t["name"].lower()]
        if not found:
            return Reply(tr('Нет плитки «{v}»', v=args), error=True)
        app.after(50, lambda: app.run_tile(found[0]))
        return None

    reg.add(["запуск", "run", "пуск"], tr("запустить плитку по названию"), run_cmd, run_complete)
        # --- избранные папки ---
    reg.add(["избранное", "favs", "fav"], tr("избранные папки: избранное убрать имя"),
            path_nav.favs_cmd, path_nav.favs_complete)

    # --- быстрая заметка ---
    def jot_cmd(args):
        if not args:
            return Reply(tr("Введи записать и текст заметки"), error=True)
        try:
            store = NoteStore(app.settings.get("notes_dir") or default_dir())
            title = store.unique_title(args.splitlines()[0][:40])
            store.write(title, args)
        except OSError as e:
            return Reply(tr('Не удалось сохранить: {e}', e=e), error=True)
        return Reply(tr('Заметка создана: {v}', v=title))

    reg.add(["записать", "jot", "зам"], tr("быстрая заметка: записать купить хлеб"), jot_cmd)
    reg.add(["поиск", "search", "g"], tr("поиск в интернете: поиск погода"), search_cmd)
    reg.add(["скрин", "shot", "screenshot"], tr("снимок экрана (вырезка, Win+Shift+S)"),
            later(lambda: winapi.send_combo("win", "shift", "s"), SCREENSHOT_DELAY_MS))  # дольше: размытие должно успеть пропасть
    reg.add(["счёт", "счет", "calc"], tr("калькулятор: счёт 2+2*3"), calc_cmd)

    # свои команды пользователя подключаем последними; их имена не должны совпадать со встроенными
    reg.builtin_names = {name for cmd in reg.commands for name in cmd.names}
    user_commands.register_all(reg, app)
    return reg