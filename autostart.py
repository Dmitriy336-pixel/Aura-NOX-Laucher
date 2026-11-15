"""Автозапуск с Windows: запись в реестре текущего пользователя (права администратора не нужны)."""
import os
import sys
import winreg

from config import BASE_DIR

KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "TileLauncher"


def _command():
    if getattr(sys, "frozen", False):  # собранный exe запускается сам, без python
        return f'"{sys.executable}" --background'
    exe = sys.executable
    pythonw = os.path.join(os.path.dirname(exe), "pythonw.exe")  # запуск без чёрной консоли
    if os.path.exists(pythonw):
        exe = pythonw
    main_path = os.path.join(BASE_DIR, "main.py")
    return f'"{exe}" "{main_path}" --background'


def set_autostart(enabled):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _command())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass  # записи и так нет