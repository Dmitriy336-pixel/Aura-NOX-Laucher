"""Вызовы Windows для команд: нажатия клавиш, рабочие столы, окна, звук."""
import ctypes
import os
import time
from ctypes import wintypes

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002

KEYS = {
    "win": 0x5B, "ctrl": 0x11, "shift": 0x10, "alt": 0x12,
    "left": 0x25, "right": 0x27,
    "d": 0x44, "s": 0x53, "f4": 0x73,
    "vol_mute": 0xAD, "vol_down": 0xAE, "vol_up": 0xAF,
}
EXTENDED = {0x25, 0x27, 0x5B}  # стрелки и клавиша Win относятся к «расширенным»

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
GW_OWNER = 4
SW_RESTORE = 9
DWMWA_CLOAKED = 14


# --- клавиши ---
def _key(code, down):
    flags = (KEYEVENTF_EXTENDEDKEY if code in EXTENDED else 0) | (0 if down else KEYEVENTF_KEYUP)
    ctypes.windll.user32.keybd_event(code, 0, flags, 0)


def send_combo(*names):
    """Нажать сочетание клавиш, например send_combo('win', 'ctrl', 'd')."""
    codes = [KEYS[n] for n in names]
    for code in codes:
        _key(code, True)
    for code in reversed(codes):
        _key(code, False)


def volume(direction, presses=1):
    """direction: 'up', 'down' или 'mute'. Одно нажатие меняет громкость примерно на 2%."""
    for _ in range(presses):
        send_combo(f"vol_{direction}")
        time.sleep(0.01)


def lock():
    ctypes.windll.user32.LockWorkStation()


# --- виртуальные рабочие столы ---
def desktop_state():
    """(сколько столов, номер текущего с единицы или None, если узнать не удалось).
    Число столов и текущий стол Windows хранит в реестре текущего пользователя."""
    import winreg
    base = r"Software\Microsoft\Windows\CurrentVersion\Explorer"

    def read(path, name):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                return winreg.QueryValueEx(key, name)[0]
        except OSError:
            return None

    ids = read(base + r"\VirtualDesktops", "VirtualDesktopIDs")
    if not ids:
        return 1, 1  # дополнительных столов ещё не создавали
    guids = [bytes(ids[i:i + 16]) for i in range(0, len(ids), 16)]  # по 16 байт на каждый стол

    session = wintypes.DWORD(0)
    ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session))
    current = read(base + rf"\SessionInfo\{session.value}\VirtualDesktops", "CurrentVirtualDesktop")
    if not current:
        current = read(base + r"\VirtualDesktops", "CurrentVirtualDesktop")
    index = guids.index(bytes(current)) + 1 if current and bytes(current) in guids else None
    return len(guids), index


def desktop_new():
    send_combo("win", "ctrl", "d")


def desktop_close():
    send_combo("win", "ctrl", "f4")


def desktop_go(target, count, index):
    """Перейти на стол номер target, листая системными сочетаниями Win+Ctrl+стрелка."""
    if index is None:  # не знаем, где мы: сначала в самый левый стол, потом вправо
        steps = [("left", count - 1), ("right", target - 1)]
    elif target > index:
        steps = [("right", target - index)]
    else:
        steps = [("left", index - target)]
    for direction, times in steps:
        for _ in range(times):
            send_combo("win", "ctrl", direction)
            time.sleep(0.12)  # даём Windows доиграть анимацию перехода


# --- окна ---
def _user32():
    u = ctypes.windll.user32
    u.IsWindowVisible.argtypes = [wintypes.HWND]
    u.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    u.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    u.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    u.GetWindow.restype = wintypes.HWND
    u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    u.IsIconic.argtypes = [wintypes.HWND]
    u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    u.SetForegroundWindow.argtypes = [wintypes.HWND]
    return u


def list_windows():
    """Открытые окна на текущем столе, как в Alt+Tab: список (дескриптор, заголовок).
    Окна самого лаунчера в список не попадают."""
    u = _user32()
    dwm = ctypes.windll.dwmapi
    dwm.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD]
    found = []
    my_pid = os.getpid()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _lparam):
        if not u.IsWindowVisible(hwnd):
            return True
        length = u.GetWindowTextLengthW(hwnd)
        if length == 0:
            return True
        style = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        if style & WS_EX_TOOLWINDOW:
            return True
        if u.GetWindow(hwnd, GW_OWNER) and not style & WS_EX_APPWINDOW:
            return True
        cloaked = wintypes.DWORD(0)  # «скрытые» окна: другие столы, замороженные приложения
        dwm.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        if cloaked.value:
            return True
        pid = wintypes.DWORD(0)
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == my_pid:
            return True
        buf = ctypes.create_unicode_buffer(length + 1)
        u.GetWindowTextW(hwnd, buf, length + 1)
        if buf.value != "Program Manager":
            found.append((hwnd, buf.value))
        return True

    u.EnumWindows(visit, 0)
    return found


def focus_window(hwnd):
    u = _user32()
    if u.IsIconic(hwnd):
        u.ShowWindow(hwnd, SW_RESTORE)  # свёрнутое окно сначала разворачиваем
    send_combo("alt")  # короткое нажатие Alt снимает запрет Windows на передачу фокуса
    u.SetForegroundWindow(hwnd)