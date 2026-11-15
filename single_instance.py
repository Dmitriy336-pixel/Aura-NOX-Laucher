"""Защита от второго экземпляра: общий именованный объект Windows (event).
Первый экземпляр его создаёт и ждёт сигнала. Второй видит, что объект уже есть,
шлёт сигнал и выходит."""
import ctypes
import hashlib
import os
import threading
from ctypes import wintypes

from config import BASE_DIR

# имя зависит от папки программы: основной лаунчер и демо-копия (make_demo.py) не принимают друг друга за второй экземпляр
EVENT_NAME = "Local\\TileLauncher.Show." + hashlib.md5(os.path.normcase(BASE_DIR).encode("utf-8")).hexdigest()[:10]
ERROR_ALREADY_EXISTS = 183
INFINITE = 0xFFFFFFFF
WAIT_OBJECT_0 = 0

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.SetEvent.argtypes = [wintypes.HANDLE]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]


class SingleInstance:
    def __init__(self):
        self.handle = kernel32.CreateEventW(None, False, False, EVENT_NAME)
        self.already_running = ctypes.get_last_error() == ERROR_ALREADY_EXISTS

    def signal_existing(self):
        """Разбудить уже работающий экземпляр."""
        kernel32.SetEvent(self.handle)

    def listen(self, on_signal):
        """Первый экземпляр: в отдельном потоке ждём сигнала от второго."""
        def loop():
            while kernel32.WaitForSingleObject(self.handle, INFINITE) == WAIT_OBJECT_0:
                on_signal()
        threading.Thread(target=loop, daemon=True).start()