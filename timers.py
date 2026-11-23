"""Таймеры и напоминания для команд «таймер» и «напомни».

Список активных таймеров хранится в памяти. Каждый таймер — это QTimer, поэтому отмена
действительно останавливает его, а сигнал приходит в главном потоке.

    timers.start(app, label, seconds)   -> номер таймера
    timers.cancel(app, number)          -> (ok, message)
    timers.list_active()                -> [(number, label, remaining_sec), ...]
"""
import re
import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QMessageBox

import sounds
from i18n import tr

_timers: list = []   # {id, label, fire_at, timer (QTimer)}
_boxes: list = []    # окна уведомлений: пока на них есть ссылка, их не соберёт сборщик мусора
_next_id = 1
MAX_MS = 2 ** 31 - 1  # предел QTimer (около 24 дней)


def _notify(app, label):
    """Сигнал и окно поверх всех окон. Оно не модальное и работает, даже если лаунчер спрятан в фон."""
    sounds.play("command_ok")
    box = QMessageBox(QMessageBox.Icon.Information, tr("Таймер"), f"⏰ {label}", QMessageBox.StandardButton.Ok)
    box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    _boxes.append(box)
    box.destroyed.connect(lambda *_: _boxes.remove(box) if box in _boxes else None)
    box.show()
    box.raise_()
    box.activateWindow()


def _fire(app, timer_id):
    """Таймер сработал."""
    global _timers
    fired = [t for t in _timers if t["id"] == timer_id]
    _timers = [t for t in _timers if t["id"] != timer_id]
    if fired:
        _notify(app, fired[0]["label"])


def fmt_delta(seconds):
    """120 -> '2 мин', 3661 -> '1 ч 1 мин 1 с'"""
    s = int(seconds)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    parts = []
    if h:
        parts.append(f"{h} ч")
    if m:
        parts.append(f"{m} мин")
    if s or not parts:
        parts.append(f"{s} с")
    return " ".join(parts)


# единицы от длинных к коротким: иначе «м» съедает начало слова «минут», а «ч» — слова «часа»
_H = r"(?:часов|часа|час|ч|hours|hour|hrs|hr|h)"
_M = r"(?:минуты|минуту|минут|мин|м|minutes|minute|mins|min|m)"
_S = r"(?:секунды|секунду|секунд|сек|с|seconds|second|secs|sec|s)"
_NUM = r"(\d+(?:[.,]\d+)?)"
_DURATION = re.compile(
    rf"^(?:{_NUM}\s*{_H}(?![a-zа-яё]))?\s*(?:{_NUM}\s*{_M}(?![a-zа-яё]))?\s*(?:{_NUM}\s*{_S}(?![a-zа-яё]))?\s*(.*)$",
    re.IGNORECASE | re.DOTALL)


def parse_duration(text):
    """'10м чай' -> (600, 'чай'); '1ч30м', '90с', '2 мин 30 сек', '1.5ч'. Возвращает (секунды, метка) или None."""
    m = _DURATION.match(text.strip())
    if not m:
        return None
    h, mi, s, label = m.groups()
    total = 0.0
    if h:
        total += float(h.replace(",", ".")) * 3600
    if mi:
        total += float(mi.replace(",", ".")) * 60
    if s:
        total += float(s.replace(",", "."))
    if total <= 0:
        return None
    return int(total), label.strip()


def start(app, label, seconds):
    """Запустить таймер. Возвращает его номер."""
    global _next_id
    tid = _next_id
    _next_id += 1
    timer = QTimer(app)
    timer.setSingleShot(True)
    timer.timeout.connect(lambda: _fire(app, tid))
    timer.start(min(int(seconds * 1000), MAX_MS))
    _timers.append({"id": tid, "label": label or f"{tr('Таймер')} {tid}", "fire_at": time.time() + seconds,
                    "timer": timer})
    return tid


def cancel(app, number):
    """Отменить таймер по номеру. Возвращает (True, '') или (False, причина)."""
    global _timers
    found = [t for t in _timers if t["id"] == number]
    if not found:
        return False, tr('Таймера #{n} нет', n=number)
    found[0]["timer"].stop()
    found[0]["timer"].deleteLater()
    _timers = [t for t in _timers if t["id"] != number]
    return True, ""


def list_active():
    """[(номер, метка, осталось_секунд), ...]"""
    now = time.time()
    return [(t["id"], t["label"], max(0, t["fire_at"] - now)) for t in _timers]
