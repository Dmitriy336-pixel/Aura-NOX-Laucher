"""Окно «нажми новую комбинацию»: записывает сочетание клавиш для глобальной горячей клавиши."""
import tkinter as tk

import customtkinter as ctk

import theme
from hotkey import is_free
from i18n import tr

MODIFIERS = {
    "Control_L": "ctrl", "Control_R": "ctrl",
    "Alt_L": "alt", "Alt_R": "alt",
    "Shift_L": "shift", "Shift_R": "shift",
}
ORDER = ["ctrl", "alt", "shift"]
SPECIAL = {32: "space", 13: "enter", 9: "tab"}


def pretty(combo):
    """'ctrl+alt+t' -> 'Ctrl+Alt+T'"""
    return "+".join(p.capitalize() if len(p) > 1 else p.upper() for p in combo.split("+"))


def key_name(keycode):
    """Код физической клавиши -> имя для hotkey.py; None, если такая клавиша не поддерживается.
    Работает одинаково на любой раскладке."""
    if 48 <= keycode <= 57 or 65 <= keycode <= 90:  # цифры и буквы
        return chr(keycode).lower()
    if 112 <= keycode <= 135:                       # F1-F24
        return f"f{keycode - 111}"
    return SPECIAL.get(keycode)


class HotkeyCapture(ctk.CTkToplevel):
    def __init__(self, master, title, current, taken, on_pick):
        super().__init__(master)
        self.current = current  # комбинация, которая назначена сейчас
        self.taken = taken      # комбинации, уже занятые другими действиями лаунчера
        self.on_pick = on_pick  # on_pick(новая комбинация)
        self.held = set()       # какие модификаторы зажаты прямо сейчас

        self.title(tr("Новая комбинация"))
        self.geometry("420x210")
        self.resizable(False, False)
        self.transient(master)

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(18, 4))
        self.preview = ctk.CTkLabel(self, text="…", font=ctk.CTkFont(size=24, weight="bold"))
        self.preview.pack(pady=6)
        self.status = ctk.CTkLabel(
            self, text=tr("Нажми нужное сочетание клавиш.\nEsc — отмена"), text_color=theme.DIM,
            wraplength=380, justify="center",
        )
        self.status.pack(pady=6)

        self.bind("<KeyPress>", self.on_press)
        self.bind("<KeyRelease>", self.on_release)
        self.bind("<FocusOut>", lambda e: self.held.clear())
        self.after(150, self.start_listening)

    def start_listening(self):
        try:
            self.grab_set()  # все нажатия идут сюда
        except tk.TclError:
            pass
        self.focus_force()

    def say(self, text):
        self.status.configure(text=text)

    def show_held(self):
        mods = [m for m in ORDER if m in self.held]
        self.preview.configure(text=pretty("+".join(mods)) + "+…" if mods else "…")

    def on_release(self, event):
        self.held.discard(MODIFIERS.get(event.keysym))
        self.show_held()

    def on_press(self, event):
        if event.keysym in MODIFIERS:
            self.held.add(MODIFIERS[event.keysym])
            self.show_held()
            return "break"
        if event.keysym == "Escape" and not self.held:
            self.destroy()
            return "break"

        name = key_name(event.keycode)
        if name is None:
            self.say(tr("Эта клавиша не подходит: можно буквы, цифры, F1–F24, Space, Enter, Tab"))
            return "break"
        mods = [m for m in ORDER if m in self.held]
        if "ctrl" not in mods and "alt" not in mods:
            self.say(tr("Нужен Ctrl или Alt, иначе клавиша перестанет работать во всех программах"))
            return "break"

        combo = "+".join(mods + [name])
        self.preview.configure(text=pretty(combo))
        if combo == self.current:
            self.destroy()
        elif combo in self.taken:
            self.say(tr("Эта комбинация уже назначена на другое действие лаунчера"))
        elif not is_free(combo):
            self.say(tr("Эту комбинацию уже занимает другая программа или система"))
        else:
            self.destroy()
            self.on_pick(combo)
        return "break"