"""Вкладка «Управление» в настройках: справочник клавиш и смена быстрых клавиш плиток."""
import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

import theme
from i18n import tr

ACCENT = theme.ACCENT
DIM = theme.DIM
ERROR = theme.ERROR
CTRL, ALT = 0x0004, 0x20000  # биты Ctrl и Alt в event.state
IGNORED = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock", "Num_Lock"}

# Справочник: группа -> (клавиши, что делают). Меняешь текст здесь, и он меняется в настройках.
SHORTCUTS = [
    (tr("Главное окно"), [
        ("Arrow Keys", tr("выбрать плитку; на панели справа Up Arrow / Down Arrow выбирают кнопку, Left Arrow возвращает к плиткам")),
        ("Tab", tr("перенести выбор между плитками и панелью справа")),
        ("Enter", tr("запустить выбранную плитку или нажать выбранную кнопку панели")),
        (tr("Клавиша плитки"), tr("сразу запускает плитку (клавиша написана на плитке, сменить её можно выше)")),
        ("Delete", tr("меню выбранной плитки: удалить, цвет, иконка")),
        (tr("Правый клик"), tr("то же меню у плитки под курсором")),
        (tr("Мышь"), tr("зажать плитку и потянуть: поменять плитки местами")),
        ("Ctrl Arrow Keys", tr("передвинуть выбранную плитку (если перетаскивание не заблокировано кнопкой ⇅)")),
        ("F2", tr("открыть настройки")),
        ("Ctrl+Q", tr("полностью закрыть лаунчер")),
    ]),
    (tr("Командная строка"), [
        ("Tab", tr("подставить выбранную подсказку")),
        ("Up Arrow / Down Arrow", tr("выбрать подсказку")),
        ("Enter", tr("выполнить команду")),
        ("PgUp / PgDn", tr("листать длинный ответ")),
        ("Esc", tr("закрыть строку")),
    ]),
    (tr("Заметки"), [
        ("Ctrl+N", tr("новая заметка")),
        ("Ctrl+S", tr("сохранить сразу (иначе заметка сохраняется сама)")),
    ]),
]


def assign_key(tiles, index, key):
    """Назначает плитке быструю клавишу ("" значит «убрать»).
    Если эту клавишу занимала другая плитка, плитки меняются клавишами."""
    tile = tiles[index]
    if key:
        for other in tiles:
            if other is not tile and other.get("key") == key:
                other["key"] = tile.get("key") or ""
    tile["key"] = key or ""


def redistribute(tiles, keys):
    """Раздаёт клавиши из keys всем плиткам заново по порядку; кому не хватило, остаются без клавиши."""
    for i, tile in enumerate(tiles):
        tile["key"] = keys[i] if i < len(keys) else ""


class ShortcutsReference(ctk.CTkFrame):
    """Справочник: какие клавиши что делают внутри лаунчера."""

    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        for group, rows in SHORTCUTS:
            ctk.CTkLabel(
                self, text=group.upper(), anchor="w", text_color=DIM,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(fill="x", padx=4, pady=(8, 2))
            box = ctk.CTkFrame(self, corner_radius=8)
            box.pack(fill="x", padx=2, pady=2)
            box.grid_columnconfigure(1, weight=1)
            for i, (keys, text) in enumerate(rows):
                ctk.CTkLabel(
                    box, text=keys, text_color=ACCENT, anchor="w", justify="left", width=130, wraplength=125,
                    font=ctk.CTkFont(size=14, weight="bold"),
                ).grid(row=i, column=0, sticky="nw", padx=(12, 6), pady=3)
                ctk.CTkLabel(
                    box, text=text, text_color=DIM, anchor="w", justify="left", wraplength=300,
                ).grid(row=i, column=1, sticky="w", padx=(0, 12), pady=3)


class TileKeysPage(ctk.CTkFrame):
    """Список плиток с быстрыми клавишами. Нажал на строку: сменить клавишу; «✕» убирает её.
    Лёгкий: на плитку всего два виджета, строки рисуются порциями, а правка меняет только затронутые строки."""

    CHUNK = 10  # сколько строк рисуем за один шаг, чтобы окно не замирало

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.rows = []    # [(кнопка со строкой, кнопка «✕»)] по номерам плиток
        self.shown = []   # клавиша, которая сейчас написана в строке
        self.job = None
        ctk.CTkLabel(
            self, anchor="w", justify="left", wraplength=480, text_color=DIM,
            text=tr("Нажми на плитку в списке, чтобы выбрать ей клавишу: подходят буквы и цифры, раскладка не важна. "
                 "Если клавишу уже занимает другая плитка, они поменяются клавишами. «✕» убирает клавишу."),
        ).pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(
            self, text=tr("Раздать заново по порядку"), width=200, command=self.reassign,
        ).pack(anchor="w", padx=8, pady=(0, 6))
        self.list = ctk.CTkFrame(self, fg_color="transparent")
        self.list.pack(fill="x")
        self.list.grid_columnconfigure(0, weight=1)
        self.render()

    def destroy(self):
        if self.job:
            self.after_cancel(self.job)
            self.job = None
        super().destroy()

    @staticmethod
    def row_text(tile):
        key = tile.get("key")
        return f"[{key.upper()}]   {tile['name']}" if key else f"  —     {tile['name']}"

    def render(self):
        if self.job:
            self.after_cancel(self.job)
            self.job = None
        for child in self.list.winfo_children():
            child.destroy()
        self.rows, self.shown = [], []
        if not self.app.tiles:
            ctk.CTkLabel(self.list, text=tr("Плиток пока нет."), text_color=DIM).grid(row=0, column=0, padx=8, pady=8)
            return
        self.add_rows(0)

    def add_rows(self, start):
        self.job = None
        if not self.winfo_exists():
            return
        tiles = self.app.tiles
        for index in range(start, min(start + self.CHUNK, len(tiles))):
            tile = tiles[index]
            key = tile.get("key") or ""
            name_btn = ctk.CTkButton(
                self.list, text=self.row_text(tile), anchor="w", height=30,
                fg_color=theme.CARD_BG, hover_color=theme.CARD_HOVER,
                text_color=theme.GHOST_TEXT, command=lambda i=index: self.change(i),
            )
            name_btn.grid(row=index, column=0, sticky="ew", padx=(6, 4), pady=2)
            clear_btn = ctk.CTkButton(
                self.list, text="✕", width=30, height=30, fg_color="transparent", border_width=1,
                text_color=theme.GHOST_TEXT, hover_color=theme.GHOST_HOVER, state="normal" if key else "disabled",
                command=lambda i=index: self.clear(i),
            )
            clear_btn.grid(row=index, column=1, padx=(0, 6), pady=2)
            self.rows.append((name_btn, clear_btn))
            self.shown.append(key)
        if start + self.CHUNK < len(tiles):
            self.job = self.after(10, lambda: self.add_rows(start + self.CHUNK))

    def sync_rows(self):
        """Обновляет только те строки, у которых клавиша изменилась."""
        for index, (name_btn, clear_btn) in enumerate(self.rows):
            if index >= len(self.app.tiles):
                break
            tile = self.app.tiles[index]
            key = tile.get("key") or ""
            if self.shown[index] != key:
                self.shown[index] = key
                name_btn.configure(text=self.row_text(tile))
                clear_btn.configure(state="normal" if key else "disabled")

    def change(self, index):
        tile = self.app.tiles[index]
        KeyCapture(self.winfo_toplevel(), tile["name"], tile.get("key"), lambda key: self.pick(index, key))

    def pick(self, index, key):
        tiles = self.app.tiles
        owner = next((t for t in tiles if t is not tiles[index] and t.get("key") == key), None)
        if owner is not None and not messagebox.askyesno(
                tr("Клавиша занята"),
                tr('Клавишу {v} уже занимает плитка «{name}».\nПоменять плитки клавишами?', v=key.upper(), name=owner['name']),
                parent=self.winfo_toplevel()):
            return
        self.app.set_tile_key(index, key)
        self.sync_rows()

    def clear(self, index):
        self.app.set_tile_key(index, "")
        self.sync_rows()

    def reassign(self):
        if not messagebox.askyesno(
                tr("Раздать заново"), tr("Все плитки получат клавиши заново по порядку: 1, 2, 3… q, w, e…\nПродолжить?"),
                parent=self.winfo_toplevel()):
            return
        self.app.reset_tile_keys()
        self.sync_rows()


class KeyCapture(ctk.CTkToplevel):
    """Маленькое окно «нажми клавишу»: записывает одну букву или цифру."""

    def __init__(self, master, name, current, on_pick):
        super().__init__(master)
        self.current = current
        self.on_pick = on_pick  # on_pick(клавиша строчной буквой или цифрой)

        self.title(tr("Быстрая клавиша"))
        self.geometry("380x190")
        self.resizable(False, False)
        self.transient(master)

        ctk.CTkLabel(self, text=name, wraplength=340, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(18, 4))
        ctk.CTkLabel(
            self, text=tr('Сейчас: {v}', v=current.upper()) if current else tr("Сейчас клавиши нет"),
            text_color=DIM,
        ).pack(pady=2)
        self.status = ctk.CTkLabel(
            self, text=tr("Нажми новую клавишу: букву или цифру.\nEsc — отмена"),
            text_color=DIM, wraplength=340, justify="center",
        )
        self.status.pack(pady=14)

        self.bind("<KeyPress>", self.on_press)
        self.after(150, self.start_listening)

    def start_listening(self):
        try:
            self.grab_set()  # все нажатия идут сюда
        except tk.TclError:
            pass
        self.focus_force()

    def say(self, text):
        self.status.configure(text=text, text_color=ERROR)

    def on_press(self, event):
        if event.keysym == "Escape":
            self.destroy()
            return "break"
        if event.keysym in IGNORED:
            return "break"
        if event.state & (CTRL | ALT):
            self.say(tr("Нажми клавишу без Ctrl и Alt"))
            return "break"
        code = event.keycode  # код физической клавиши: цифры 48-57, буквы 65-90, раскладка не важна
        if not (48 <= code <= 57 or 65 <= code <= 90):
            self.say(tr("Подходят только буквы и цифры"))
            return "break"
        key = chr(code).lower()
        self.destroy()
        if key != self.current:
            self.on_pick(key)
        return "break"
