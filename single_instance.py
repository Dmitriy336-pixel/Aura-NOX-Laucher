# single_instance.py
"""Защита от второго экземпляра через именованный Windows Event.
Первый экземпляр создаёт объект и ждёт сигнала.
Второй видит, что объект уже есть, шлёт сигнал и выходит.

Отличие от оригинала: колбек вызывается из фонового потока,
поэтому в App мы используем QMetaObject.invokeMethod для
безопасного перехода в главный поток Qt.
"""

import ctypes
import hashlib
import os
import threading
from ctypes import wintypes

from config import BASE_DIR

EVENT_NAME = (
    "Local\\TileLauncher.Show."
    + hashlib.md5(os.path.normcase(BASE_DIR).encode("utf-8")).hexdigest()[:10]
)

ERROR_ALREADY_EXISTS = 183
INFINITE   = 0xFFFFFFFF
WAIT_OBJECT_0 = 0

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.CreateEventW.restype  = wintypes.HANDLE
kernel32.CreateEventW.argtypes = [
    wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.SetEvent.argtypes    = [wintypes.HANDLE]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]


class SingleInstance:
    def __init__(self):
        self.handle = kernel32.CreateEventW(None, False, False, EVENT_NAME)
        self.already_running = (
            ctypes.get_last_error() == ERROR_ALREADY_EXISTS)

    def signal_existing(self):
        """Разбудить уже работающий экземпляр."""
        kernel32.SetEvent(self.handle)

    def close_handle(self):
        """Закрыть дескриптор (нужно при --restart, чтобы объект исчез)."""
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None

    def listen(self, on_signal):
        """
        Первый экземпляр: ждём сигнала от второго в отдельном потоке.
        on_signal() будет вызван из фонового потока — используй
        QMetaObject.invokeMethod или Qt.QueuedConnection в App.
        """
        def loop():
            while True:
                result = kernel32.WaitForSingleObject(
                    self.handle, INFINITE)
                if result == WAIT_OBJECT_0:
                    on_signal()
                else:
                    break   # дескриптор закрыт — выходим

        threading.Thread(target=loop, daemon=True).start()
