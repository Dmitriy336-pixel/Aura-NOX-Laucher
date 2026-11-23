# hotkey_capture.py
"""Окно «нажми новую комбинацию»: записывает сочетание клавиш для глобальной горячей клавиши (PySide6)."""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout

import theme
from hotkey import is_free
from i18n import tr

ORDER = ["ctrl", "alt", "shift"]
SPECIAL = {32: "space", 13: "enter", 9: "tab"}
MODIFIER_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta, Qt.Key.Key_AltGr}


def pretty(combo):
    """'ctrl+alt+t' -> 'Ctrl+Alt+T'"""
    return "+".join(p.capitalize() if len(p) > 1 else p.upper() for p in combo.split("+"))


def key_name(keycode):
    """Код физической клавиши (VK) -> имя для hotkey.py; None, если такая клавиша не поддерживается.
    Работает одинаково на любой раскладке."""
    if 48 <= keycode <= 57 or 65 <= keycode <= 90:  # цифры и буквы
        return chr(keycode).lower()
    if 112 <= keycode <= 135:                       # F1-F24
        return f"f{keycode - 111}"
    return SPECIAL.get(keycode)


def modifiers_of(flags):
    held = set()
    if flags & Qt.KeyboardModifier.ControlModifier:
        held.add("ctrl")
    if flags & Qt.KeyboardModifier.AltModifier:
        held.add("alt")
    if flags & Qt.KeyboardModifier.ShiftModifier:
        held.add("shift")
    return held


class HotkeyCapture(QDialog):
    def __init__(self, master, title, current, taken, on_pick):
        super().__init__(master)
        self.current = current  # комбинация, которая назначена сейчас
        self.taken = taken      # комбинации, уже занятые другими действиями лаунчера
        self.on_pick = on_pick  # on_pick(новая комбинация)

        self.setWindowTitle(tr("Новая комбинация"))
        self.setFixedSize(420, 210)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        head = QLabel(title)
        head.setAlignment(Qt.AlignmentFlag.AlignCenter)
        head.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.preview = QLabel("…")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("font-size: 24px; font-weight: bold;")
        self.status = QLabel(tr("Нажми нужное сочетание клавиш.\nEsc — отмена"))
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status.setWordWrap(True)
        self.status.setStyleSheet(f"color: {theme.color('text_dim')};")
        layout.addWidget(head)
        layout.addWidget(self.preview)
        layout.addWidget(self.status)
        layout.addStretch(1)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def say(self, text):
        self.status.setText(text)

    def show_held(self, held):
        mods = [m for m in ORDER if m in held]
        self.preview.setText(pretty("+".join(mods)) + "+…" if mods else "…")

    def event(self, e):
        # Tab иначе уйдёт на перебор фокуса, а он нужен как клавиша комбинации
        if e.type() == QEvent.Type.KeyPress and e.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.keyPressEvent(e)
            return True
        return super().event(e)

    def keyReleaseEvent(self, event):
        self.show_held(modifiers_of(QApplication.keyboardModifiers()))

    def keyPressEvent(self, event):
        key = event.key()
        held = modifiers_of(event.modifiers())
        if key in MODIFIER_KEYS:
            self.show_held(held)
            return
        if key == Qt.Key.Key_Escape and not held:
            self.reject()
            return

        name = key_name(event.nativeVirtualKey() or key)
        if name is None:
            self.say(tr("Эта клавиша не подходит: можно буквы, цифры, F1–F24, Space, Enter, Tab"))
            return
        mods = [m for m in ORDER if m in held]
        if "ctrl" not in mods and "alt" not in mods:
            self.say(tr("Нужен Ctrl или Alt, иначе клавиша перестанет работать во всех программах"))
            return

        combo = "+".join(mods + [name])
        self.preview.setText(pretty(combo))
        if combo == self.current:
            self.accept()
        elif combo in self.taken:
            self.say(tr("Эта комбинация уже назначена на другое действие лаунчера"))
        elif not is_free(combo):
            self.say(tr("Эту комбинацию уже занимает другая программа или система"))
        else:
            self.accept()
            self.on_pick(combo)
