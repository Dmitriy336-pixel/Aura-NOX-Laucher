"""Звуки событий. Файлы лежат в папке «sounds» рядом с программой (она создаётся сама).
Имя файла = событие, формат .wav или .mp3; нет файла: событие остаётся без звука.

Список событий и их имён: словарь EVENTS ниже; тот же список лежит в папке sounds в файле «имена_звуков.txt».

Громкость и переключатель берутся из настроек. Играет системный MCI (winmm), он умеет менять громкость
отдельно от системной. Звуки открываются заранее и играют из отдельного потока, поэтому задержки нет и интерфейс не ждёт."""
import ctypes
import itertools
import os
import queue
import sys
import threading
import time

import i18n
from config import BASE_DIR, RESOURCE_DIR

EVENTS = {
    "launch": "запуск плитки",
    "error": "ошибка (плитка не запустилась, команда не выполнена)",
    "tile_add": "добавлена плитка",
    "tile_delete": "удалена плитка",
    "tile_move": "плитка переставлена",
    "select": "рамка выбора сдвинулась (стрелки, Tab)",
    "lock_on": "перетаскивание плиток заблокировано",
    "lock_off": "перетаскивание плиток разблокировано",
    "perf_on": "режим высокой производительности включён",
    "perf_off": "режим высокой производительности выключен",
    "window_show": "лаунчер показан (горячей клавишей или вторым запуском)",
    "window_hide": "лаунчер спрятан в фон",
    "settings_open": "открыты настройки",
    "settings_close": "закрыты настройки",
    "command": "появилась командная строка",
    "command_ok": "команда выполнена",
    "notes_open": "открыты заметки",
    "notes_close": "закрыты заметки",
    "note_new": "создана заметка",
    "note_delete": "удалена заметка",
    "click": "обычное нажатие кнопки; запасной звук для событий ниже, у которых нет своего файла",
    "nav": "переключён отдел настроек",
    "toggle_on": "переключатель в настройках включён",
    "toggle_off": "переключатель в настройках выключен",
    "option": "выбран вариант или сдвинут ползунок в настройках",
    "hotkey_set": "назначена новая горячая клавиша",
    "menu_open": "открыто меню плитки",
    "drag_start": "плитку взяли для перетаскивания",
    "hover": "курсор навели на плитку или кнопку панели (запасного звука нет)",
    "note_select": "выбрана другая заметка",
    "note_pin": "заметка закреплена",
    "note_unpin": "заметка откреплена",
    "cmd_move": "подсказка в командной строке сменилась (стрелки); запасной звук select",
    "cmd_complete": "подсказка подставлена (Tab)",
    "command_close": "командная строка закрыта клавишей Esc (запасного звука нет)",
    "theme_select": "выбрана тема",
    "color_set": "выбран цвет плитки",
    "faq_toggle": "открыт или закрыт ответ в FAQ",
    "copied": "текст скопирован (вкладка «О программе»)",
    "note_save": "заметка сохранена вручную (Ctrl+S)",
    "type": "нажата клавиша в командной строке (запасного звука нет)",
}
EXTENSIONS = (".wav", ".mp3")
SOUNDS_DIR = os.path.join(BASE_DIR, "sounds")
MIN_GAP = 0.08   # секунд: один и тот же звук чаще не повторяем (дребезг, двойные вызовы)
GAPS = {"hover": 0.3, "cmd_move": 0.05, "type": 0.03}   # для некоторых событий свой промежуток
# Запасные звуки: у события нет своего файла, играет этот (если файл запасного есть). Так один звук click
# сразу «оживляет» весь интерфейс, а свои файлы для отдельных событий можно добавлять потом.
FALLBACK = {
    "nav": "click", "toggle_on": "click", "toggle_off": "click", "option": "click", "hotkey_set": "click",
    "menu_open": "click", "note_select": "click", "note_pin": "click", "note_unpin": "click",
    "cmd_complete": "click", "theme_select": "click", "color_set": "click", "faq_toggle": "click",
    "copied": "click", "note_save": "click", "cmd_move": "select",
}
_resolved = {}

_settings = {}
_last = {}
AMBIENT = ("hover", "type", "cmd_move")   # фоновые звуки: не считаются «ответом» на нажатие кнопки
_last_action = [0.0]


def init(settings):
    """Подключает общий словарь настроек (тот же, что у окна: изменения видны сразу) и создаёт папку."""
    global _settings
    _settings = settings
    try:
        os.makedirs(SOUNDS_DIR, exist_ok=True)
    except OSError:
        pass
    write_guide()
    if settings.get("sounds_enabled", True):
        preload()


EVENTS_EN = {
    "launch": "a tile is launched",
    "error": "an error (a tile did not launch, a command failed)",
    "tile_add": "a tile is added",
    "tile_delete": "a tile is deleted",
    "tile_move": "a tile is moved",
    "select": "the selection frame moves (arrows, Tab)",
    "lock_on": "dragging of tiles is locked",
    "lock_off": "dragging of tiles is unlocked",
    "perf_on": "high-performance mode is on",
    "perf_off": "high-performance mode is off",
    "window_show": "the launcher is shown (hotkey or second start)",
    "window_hide": "the launcher is hidden to the background",
    "settings_open": "settings are opened",
    "settings_close": "settings are closed",
    "command": "the command bar appears",
    "command_ok": "a command succeeded",
    "notes_open": "notes are opened",
    "notes_close": "notes are closed",
    "note_new": "a note is created",
    "note_delete": "a note is deleted",
    "click": "a plain button press; fallback sound for the events below that have no file of their own",
    "nav": "a settings section is switched",
    "toggle_on": "a switch in the settings is turned on",
    "toggle_off": "a switch in the settings is turned off",
    "option": "an option is chosen or a slider is moved in the settings",
    "hotkey_set": "a new hotkey is assigned",
    "menu_open": "the tile menu is opened",
    "drag_start": "a tile is picked up for dragging",
    "hover": "the cursor is over a tile or a sidebar button (no fallback)",
    "note_select": "another note is selected",
    "note_pin": "a note is pinned",
    "note_unpin": "a note is unpinned",
    "cmd_move": "the command bar suggestion changes (arrows); falls back to select",
    "cmd_complete": "a suggestion is inserted (Tab)",
    "command_close": "the command bar is closed with Esc (no fallback)",
    "theme_select": "a theme is chosen",
    "color_set": "a tile color is chosen",
    "faq_toggle": "an FAQ answer is opened or closed",
    "copied": "text is copied (About tab)",
    "note_save": "a note is saved by hand (Ctrl+S)",
    "type": "a key is pressed in the command bar (no fallback)",
}


EVENTS_UK = {
    "launch": "запущено плитку",
    "error": "помилка (плитка не запустилась, команда не виконалась)",
    "tile_add": "додано плитку",
    "tile_delete": "видалено плитку",
    "tile_move": "плитку переставлено",
    "select": "рамка вибору зсунулась (стрілки, Tab)",
    "lock_on": "перетягування плиток заблоковано",
    "lock_off": "перетягування плиток розблоковано",
    "perf_on": "режим високої продуктивності ввімкнено",
    "perf_off": "режим високої продуктивності вимкнено",
    "window_show": "лаунчер показано (гарячою клавішею або другим запуском)",
    "window_hide": "лаунчер сховано у фон",
    "settings_open": "відкрито налаштування",
    "settings_close": "закрито налаштування",
    "command": "з'явився командний рядок",
    "command_ok": "команду виконано",
    "notes_open": "відкрито нотатки",
    "notes_close": "закрито нотатки",
    "note_new": "створено нотатку",
    "note_delete": "видалено нотатку",
    "click": "звичайне натискання кнопки; запасний звук для подій нижче, які не мають свого файлу",
    "nav": "перемкнуто розділ налаштувань",
    "toggle_on": "перемикач у налаштуваннях увімкнено",
    "toggle_off": "перемикач у налаштуваннях вимкнено",
    "option": "обрано варіант або зсунуто повзунок у налаштуваннях",
    "hotkey_set": "призначено нову гарячу клавішу",
    "menu_open": "відкрито меню плитки",
    "drag_start": "плитку взято для перетягування",
    "hover": "курсор наведено на плитку або кнопку панелі (запасного звуку немає)",
    "note_select": "обрано іншу нотатку",
    "note_pin": "нотатку закріплено",
    "note_unpin": "нотатку відкріплено",
    "cmd_move": "підказка в командному рядку змінилась (стрілки); запасний звук select",
    "cmd_complete": "підказку підставлено (Tab)",
    "command_close": "командний рядок закрито клавішею Esc (запасного звуку немає)",
    "theme_select": "обрано тему",
    "color_set": "обрано колір плитки",
    "faq_toggle": "відкрито або закрито відповідь у FAQ",
    "copied": "текст скопійовано (вкладка «Про програму»)",
    "note_save": "нотатку збережено вручну (Ctrl+S)",
    "type": "натиснуто клавішу в командному рядку (запасного звуку немає)",
}


def write_guide():
    """Памятка в папке звуков: какое имя файла какому событию соответствует. Обновляется при каждом запуске,
    на языке интерфейса."""
    if i18n.language() == "en":
        lines = ["Put .wav or .mp3 files here and name them after the event (case does not matter).",
                 "No file means no sound for that event. Switch and volume: Settings, General, Sounds.", ""]
        lines += [f"{name}.wav  -  {text}" for name, text in EVENTS_EN.items()]
        guide = "sound_names.txt"
    elif i18n.language() == "uk":
        lines = ["Поклади сюди файли .wav або .mp3 і назви їх за подією (регістр не важливий).",
                 "Немає файлу: у події немає звуку. Увімкнення та гучність: Налаштування, Загальні, Звуки.", ""]
        lines += [f"{name}.wav  -  {text}" for name, text in EVENTS_UK.items()]
        guide = "імена_звуків.txt"
    else:
        lines = ["Положи сюда файлы .wav или .mp3 и назови их по событию (регистр не важен).",
                 "Нет файла: у события нет звука. Включение и громкость: Настройки, Общие, Звуки.", ""]
        lines += [f"{name}.wav  -  {text}" for name, text in EVENTS.items()]
        guide = "имена_звуков.txt"
    try:
        with open(os.path.join(SOUNDS_DIR, guide), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        pass


def find(event):
    """Путь к файлу события или None. Регистр имени не важен; ищем в папке рядом с программой и в упакованной."""
    for folder in dict.fromkeys((SOUNDS_DIR, os.path.join(RESOURCE_DIR, "sounds"))):
        try:
            files = {name.lower(): name for name in os.listdir(folder)}
        except OSError:
            continue
        for ext in EXTENSIONS:
            name = files.get(event + ext)
            if name:
                return os.path.join(folder, name)
    return None


def _mci(command):
    return _mci_text(command)[0]


def _mci_text(command):
    buf = ctypes.create_unicode_buffer(128)
    err = ctypes.windll.winmm.mciSendStringW(command, buf, 127, 0)
    return err, buf.value


# Все обращения к MCI идут из одного потока-исполнителя: интерфейс не ждёт.
# Повторное проигрывание одного и того же открытого устройства звучит по-разному (бывает тише, «издалека»),
# поэтому каждый раз играет свежее, ещё ни разу не игравшее устройство. Следующее такое готовится
# заранее сразу после проигрыша: открытие файла занимает десятые доли секунды, а звук должен идти без задержки.
_queue = queue.Queue()
_spare = {}     # событие -> (путь, псевдоним) готовое к игре устройство
_playing = []   # псевдонимы, которые играют или доигрывают: закрываем, когда закончат
_counter = itertools.count(1)
_worker = None


def _open_new(event):
    """Открывает новое устройство для файла события: (путь, псевдоним) или None, если файла нет."""
    path = find(event)
    if path is None:
        return None
    alias = f"launcher_snd{next(_counter)}"
    # mpegvideo (DirectShow) играет и .wav, и .mp3 и умеет менять громкость; waveaudio только запасной вариант
    for kind in ("mpegvideo", "waveaudio"):
        if _mci(f'open "{path}" type {kind} alias {alias}') == 0:
            return path, alias
    return None


def _ready(event):
    """Готовое к игре устройство события (готовит, если его нет или файл заменили)."""
    current = _spare.get(event)
    if current and current[0] == find(event):
        return current
    if current:
        _mci(f"close {current[1]}")
        del _spare[event]
    fresh = _open_new(event)
    if fresh:
        _spare[event] = fresh
    return fresh


def _start(alias, volume):
    _mci(f"setaudio {alias} volume to {int(volume * 10)}")
    return _mci(f"play {alias}") == 0


def _cleanup():
    """Закрывает доигравшие устройства."""
    for alias in list(_playing):
        err, mode = _mci_text(f"status {alias} mode")
        if err != 0 or mode != "playing":
            _mci(f"close {alias}")
            _playing.remove(alias)


def _play_now(event, volume):
    for _ in range(2):                       # вторая попытка: если устройство оказалось негодным
        device = _ready(event)
        if device is None:
            return
        del _spare[event]
        if _start(device[1], volume):
            _playing.append(device[1])
            return
        _mci(f"close {device[1]}")


def _run():
    while True:
        try:
            action, event, volume = _queue.get(timeout=3)
        except queue.Empty:
            _cleanup()
            continue
        try:
            if action == "play":
                _play_now(event, volume)
            _ready(event)                    # следующее проигрывание уже ждёт готовым
            _cleanup()
        except Exception:
            pass  # звук не должен ронять программу


def _send(action, event, volume=0):
    global _worker
    if _worker is None:
        _worker = threading.Thread(target=_run, daemon=True)
        _worker.start()
    _queue.put((action, event, volume))


def preload():
    """Открывает все найденные звуки заранее, чтобы первое событие не запаздывало."""
    for event in EVENTS:
        if find(event):
            _send("load", event)


def resolve(event):
    """Событие, чей файл реально сыграет: своё, а если файла нет, запасное (или то же самое: тишина)."""
    if event not in _resolved:
        fallback = FALLBACK.get(event)
        _resolved[event] = fallback if fallback and not find(event) and find(fallback) else event
    return _resolved[event]


def _debug(text):
    """Отладка: если в папке sounds лежит файл debug.txt, каждое обращение к звуку пишется в debug.log рядом."""
    if not os.path.exists(os.path.join(SOUNDS_DIR, "debug.txt")):
        return
    try:
        frame = sys._getframe(2)
        where = f"{os.path.basename(frame.f_code.co_filename)}:{frame.f_lineno} {frame.f_code.co_name}"
        with open(os.path.join(SOUNDS_DIR, "debug.log"), "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')}.{int(time.time() * 1000) % 1000:03d}  {text}  <- {where}\n")
    except Exception:
        pass


def play(event, force=False):
    """Проиграть звук события. force=True: даже если звуки выключены (кнопка «проверить»)."""
    if not force and not _settings.get("sounds_enabled", True):
        return False
    volume = max(0, min(100, int(_settings.get("sound_volume", 70))))
    if volume == 0:
        return False
    requested = event
    event = resolve(event)
    now = time.monotonic()
    if now - _last.get(event, 0) < GAPS.get(event, MIN_GAP):
        _debug(f"{requested} -> {event}: пропущен (слишком часто)")
        return False
    _debug(f"{requested} -> {event}: играет")
    _last[event] = now
    if event not in AMBIENT:
        _last_action[0] = now
    _send("play", event, volume)
    return True


def auto_click(pressed_at):
    """Общий звук нажатия кнопки в окнах (настройки, заметки, диалоги). Вызывается чуть позже самого нажатия
    и играет, только если с момента нажатия не прозвучало никакого звука действия: у кнопок со своими
    событиями он уже был, второй не нужен."""
    if _last_action[0] < pressed_at - 0.03:
        play("click")
    else:
        _debug("общий click не нужен: звук уже был")
