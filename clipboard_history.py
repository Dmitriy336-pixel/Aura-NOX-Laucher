"""История буфера обмена для PySide6/PyQt.

Мониторинг через QTimer (polling), безопасно для GUI-потока.
API:
    start_monitoring(app)        — вызвать один раз при старте
    get_history()                — [(номер, краткий_текст, полный_текст), ...]
    paste(app, index)            — положить запись в буфер и нажать Ctrl+V
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

HISTORY_SIZE = 20
POLL_MS = 800

_history: list[str] = []
_last_text: str = ""
_timer: object = None


def _short(text, limit=80):
    text = text.replace("\n", " ").replace("\r", "")
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _poll():
    global _last_text, _history
    try:
        text = QApplication.clipboard().text()
    except Exception:
        text = ""
    if text and text != _last_text:
        _last_text = text
        if text in _history:
            _history.remove(text)
        _history.insert(0, text)
        if len(_history) > HISTORY_SIZE:
            _history.pop()


def start_monitoring(app):
    global _timer
    if _timer is not None:
        return
    _timer = QTimer()
    _timer.timeout.connect(_poll)
    _timer.start(POLL_MS)


def get_history():
    return [(i + 1, _short(t), t) for i, t in enumerate(_history)]


def paste(app, index):
    if not 1 <= index <= len(_history):
        return False
    text = _history[index - 1]
    QApplication.clipboard().setText(text)
    # Ctrl+V в предыдущее окно
    try:
        import ctypes
        KEYEVENTF_KEYUP = 0x0002
        kbe = ctypes.windll.user32.keybd_event
        kbe(0x11, 0, 0, 0)        # Ctrl down
        kbe(0x56, 0, 0, 0)        # V down
        kbe(0x56, 0, KEYEVENTF_KEYUP, 0)
        kbe(0x11, 0, KEYEVENTF_KEYUP, 0)
    except Exception:
        pass
    return True
