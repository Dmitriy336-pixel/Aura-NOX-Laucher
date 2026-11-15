"""Глобальные горячие клавиши через WinAPI (RegisterHotKey).
Перехвата всех клавиш нет: Windows сама будит нас, когда нажата нужная комбинация.
Один поток обслуживает сразу несколько комбинаций."""
import ctypes
import threading
from ctypes import wintypes
from i18n import tr

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x0001, 0x0002, 0x0004, 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012

MODIFIERS = {"alt": MOD_ALT, "ctrl": MOD_CONTROL, "shift": MOD_SHIFT, "win": MOD_WIN}
SPECIAL_KEYS = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B}


def parse_combo(combo):
    """'ctrl+alt+space' -> (модификаторы, код клавиши)"""
    mods, vk = 0, None
    for part in combo.lower().replace(" ", "").split("+"):
        if part in MODIFIERS:
            mods |= MODIFIERS[part]
        elif part in SPECIAL_KEYS:
            vk = SPECIAL_KEYS[part]
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part.startswith("f") and part[1:].isdigit():
            vk = 0x70 + int(part[1:]) - 1  # F1 = 0x70
    if vk is None:
        raise ValueError(tr("В комбинации '{combo}' нет основной клавиши", combo=combo))
    return mods, vk

def is_free(combo):
    """Можно ли занять комбинацию, не держит ли её уже другая программа. Занимаем и сразу отпускаем."""
    mods, vk = parse_combo(combo)
    user32 = ctypes.windll.user32
    if user32.RegisterHotKey(None, 0x7FFF, mods | MOD_NOREPEAT, vk):
        user32.UnregisterHotKey(None, 0x7FFF)
        return True
    return False


class HotkeyListener:
    def __init__(self, on_hotkey):
        self.on_hotkey = on_hotkey  # вызывается как on_hotkey(имя) при нажатии комбинации
        self.thread = None
        self.thread_id = None

    def start(self, combos):
        """combos: {"имя": "ctrl+alt+space", ...}.
        Возвращает список имён, комбинации которых не удалось занять."""
        self.stop()
        if not combos:
            return []
        parsed = {name: parse_combo(combo) for name, combo in combos.items()}
        ready = threading.Event()
        result = {"failed": []}
        self.thread = threading.Thread(
            target=self._run, args=(parsed, ready, result), daemon=True
        )
        self.thread.start()
        ready.wait(2)
        return result["failed"]

    def stop(self):
        if self.thread is not None and self.thread.is_alive():
            ctypes.windll.user32.PostThreadMessageW(self.thread_id, WM_QUIT, 0, 0)
            self.thread.join(timeout=1)
        self.thread = None
        self.thread_id = None

    def _run(self, parsed, ready, result):
        user32 = ctypes.windll.user32
        self.thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        ids = {}  # числовой номер комбинации -> имя
        for number, (name, (mods, vk)) in enumerate(parsed.items(), start=1):
            if user32.RegisterHotKey(None, number, mods | MOD_NOREPEAT, vk):
                ids[number] = name
            else:
                result["failed"].append(name)  # комбинацию уже занимает другая программа
        ready.set()
        if not ids:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == WM_HOTKEY and msg.wParam in ids:
                self.on_hotkey(ids[msg.wParam])
        for number in ids:
            user32.UnregisterHotKey(None, number)