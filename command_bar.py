"""Командная строка: тонкая панель без рамки с полем ввода у нижнего края экрана.
Над полем появляются подсказки (пока печатаешь), список команд и ответы."""
import ctypes
import tkinter as tk
from ctypes import wintypes

import customtkinter as ctk

import sounds
import theme
import json

import storage
from config import HISTORY_FILE
from commands import Paged, Reply
import i18n
from i18n import tr

HINT = tr("Введи команду. «помощь» — список команд")
FOOTER = tr("Tab — подставить   ·   Up Arrow | Down Arrow — выбрать   ·   Enter — выполнить")
MAX_SUGGESTIONS = 6
MAX_ARG_ITEMS = 8   # сколько подсказок по аргументам показывать сразу
BAR_MARGIN = 12  # зазор между строкой и панелью задач, px

# Цвета: меняй здесь
KEY_COLOR = "#010101"                # этот цвет окно делает прозрачным: так получаются скруглённые углы
ACCENT = theme.ACCENT                   # названия команд
DIM = theme.DIM           # английские варианты, описания, подписи
ERROR = theme.ERROR                    # сообщения об ошибках
SELECT_BG = theme.SELECT_BG   # выбранная подсказка
PANEL_BG = theme.CMD_PANEL      # фон панели с подсказками
LINE = theme.CMD_LINE          # разделители


def taskbar_top():
    """Нижняя граница рабочей области экрана, то есть верхний край панели задач (px)."""
    try:
        rect = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)  # SPI_GETWORKAREA
        return rect.bottom
    except (AttributeError, OSError):
        return None


class InfoPanel(ctk.CTkFrame):
    """Панель над строкой: заголовок, строки с разделителями и подпись внизу."""

    def __init__(self, master):
        super().__init__(master, corner_radius=10, fg_color=PANEL_BG)
        self.wrap = 500  # перенос длинных строк, px

    def clear(self):
        for child in self.winfo_children():
            child.destroy()

    def header(self, text):
        ctk.CTkLabel(
            self, text=text.upper(), anchor="w", text_color=DIM,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(fill="x", padx=14, pady=(8, 2))

    def divider(self):
        ctk.CTkFrame(self, height=2, corner_radius=0, fg_color=LINE).pack(fill="x", padx=12, pady=2)

    def row(self, names, description, selected=False, matched=None):
        """Строка команды: название, остальные варианты написания, описание."""
        main = matched or names[0]
        if matched is None and i18n.language() != "ru":
            main = next((n for n in names if n.isascii()), main)  # английский интерфейс: английское имя первым
        aliases = ", ".join(n for n in names if n != main)
        row = ctk.CTkFrame(self, corner_radius=6, fg_color=SELECT_BG if selected else "transparent")
        row.pack(fill="x", padx=6, pady=1)
        row.grid_columnconfigure(0, minsize=100)
        row.grid_columnconfigure(1, minsize=90 if aliases else 0)
        row.grid_columnconfigure(2, weight=1)
        ctk.CTkLabel(
            row, text=main, text_color=ACCENT, anchor="w", font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=(8, 6), pady=3)
        if aliases:
            ctk.CTkLabel(row, text=aliases, text_color=DIM, anchor="w", font=ctk.CTkFont(size=12)).grid(
                row=0, column=1, sticky="w", padx=(0, 6)
            )
        # без вариантов написания описание занимает и их место, чтобы не оставалось пустоты
        ctk.CTkLabel(
            row, text=description, text_color=DIM, anchor="w", justify="left",
            wraplength=self.wrap, font=ctk.CTkFont(size=13),
        ).grid(row=0, column=1 if not aliases else 2, columnspan=2 if not aliases else 1,
               sticky="w", padx=(0, 8))

    def message(self, text, error=False):
        ctk.CTkLabel(
            self, text=text, anchor="w", justify="left", wraplength=self.wrap + 180,
            text_color=ERROR if error else DIM, font=ctk.CTkFont(size=13),
        ).pack(fill="x", padx=14, pady=8)

    def footer(self, text):
        ctk.CTkLabel(
            self, text=text, anchor="w", text_color=DIM, font=ctk.CTkFont(size=11),
        ).pack(fill="x", padx=14, pady=(3, 7))


class CommandBar(ctk.CTkToplevel):
    def __init__(self, master, registry):
        super().__init__(master)
        self.registry = registry
        self.suggestions = []   # подсказки: список пар (команда, подходящее имя)
        self.arg_items = []     # подсказки по аргументам: (что подставить, метка, описание)
        self.arg_word = ""      # как пользователь написал имя команды, чьи аргументы подсказываем
        self.sel = 0            # какая подсказка выбрана
        self.paged = None       # открытый многостраничный ответ
        self.history = self.load_history()  # команды прошлых запусков тоже
        self.hist_pos = None    # где мы в истории (None: не листаем)
        self.page = 0
        self.quiet = False      # True, пока текст меняем из кода, а не печатает пользователь
        self.w = self.x = self.bottom = 0

        self.withdraw()
        self.overrideredirect(True)          # без рамки и заголовка
        self.attributes("-topmost", True)
        self.configure(fg_color=KEY_COLOR)
        try:
            self.attributes("-transparentcolor", KEY_COLOR)  # Windows: прозрачные углы вокруг скруглённой панели
        except tk.TclError:
            pass

        # скруглённая тонкая рамка вокруг всего содержимого
        self.box = ctk.CTkFrame(
            self, corner_radius=14, border_width=1, border_color=LINE, fg_color=theme.CMD_BOX
        )
        self.box.pack(fill="both", expand=True)

        self.info = InfoPanel(self.box)

        self.var = ctk.StringVar()
        self.var.trace_add("write", self.on_text)
        self.entry = ctk.CTkEntry(
            self.box, textvariable=self.var, height=34, border_width=0, corner_radius=8,
            font=ctk.CTkFont(size=15),
        )
        self.entry.pack(side="bottom", fill="x", padx=8, pady=7)

        self.entry.bind("<Return>", self.run)
        self.entry.bind("<Tab>", self.complete)
        self.entry.bind("<Key>", lambda e: sounds.play("type") if e.char and e.char.isprintable() else None, add="+")
        self.entry.bind("<Up>", lambda e: self.move(-1))
        self.entry.bind("<Down>", lambda e: self.move(1))
        self.entry.bind("<Prior>", lambda e: self.turn_page(-1))  # PgUp
        self.entry.bind("<Next>", lambda e: self.turn_page(1))    # PgDn
        self.bind("<Escape>", lambda e: self.escape())
        self.bind("<FocusOut>", lambda e: self.after(150, self.close_if_unfocused))

    # --- открыть и закрыть ---
    def open(self):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.w = max(580, min(800, int(sw * 0.35) + 25))
        self.x = (sw - self.w) // 2                       # по центру экрана по ширине
        floor = taskbar_top() or int(sh * 0.95)           # верхний край панели задач
        self.bottom = floor - BAR_MARGIN                  # строка стоит прямо над ней, подсказки растут вверх
        self.info.wrap = self.w - 360
        self.set_text("")
        self.paged = None
        self.suggestions = []
        self.arg_items = []
        self.show_message(HINT)
        self.deiconify()
        self.lift()
        self.focus_force()
        self.entry.focus_set()
        self.hist_pos = None

    def escape(self):
        sounds.play("command_close")
        self.close()

    def close(self):
        self.withdraw()

    def close_if_unfocused(self):
        if self.winfo_exists() and self.winfo_viewable() and self.focus_displayof() is None:
            self.close()

    # --- размер и положение ---
    def present(self):
        self.info.pack(side="top", fill="x", padx=8, pady=(8, 0))
        self.fit()

    def fit(self):
        """Подгоняем высоту под содержимое, нижний край (поле ввода) остаётся на месте."""
        self.update_idletasks()
        h = self.winfo_reqheight()
        self.wm_geometry(f"{self.w}x{h}+{self.x}+{self.bottom - h}")

    def set_text(self, text):
        self.quiet = True
        self.entry.delete(0, "end")
        self.entry.insert(0, text)
        self.quiet = False

    # --- что показываем над полем ---
    def show_message(self, text, error=False):
        self.info.clear()
        self.info.message(text, error)
        self.present()

    def show_suggestions(self):
        self.info.clear()
        size = MAX_SUGGESTIONS
        pages = max(1, -(-len(self.suggestions) // size))
        page = min(self.sel // size, pages - 1)
        start = page * size
        for i, (cmd, name) in enumerate(self.suggestions[start:start + size]):
            if i:
                self.info.divider()
            self.info.row(cmd.names, cmd.description, selected=(start + i == self.sel), matched=name)
        self.info.divider()
        self.info.footer(FOOTER)
        if pages > 1:
            self.info.footer(tr('стр. {v} из {pages}   ·   PgUp / PgDn — листать', v=page + 1, pages=pages))
        self.present()

    def show_arg_items(self):
        self.info.clear()
        size = MAX_ARG_ITEMS
        pages = max(1, -(-len(self.arg_items) // size))
        page = min(self.sel // size, pages - 1)
        start = page * size
        for i, (_insert, label, description) in enumerate(self.arg_items[start:start + size]):
            if i:
                self.info.divider()
            self.info.row([label], description, selected=(start + i == self.sel))
        self.info.divider()
        self.info.footer(FOOTER)
        if pages > 1:
            self.info.footer(tr('стр. {v} из {pages}   ·   PgUp / PgDn — листать', v=page + 1, pages=pages))
        self.present()

    def show_page(self):
        p = self.paged
        pages = max(1, -(-len(p.lines) // p.per_page))
        self.page = max(0, min(pages - 1, self.page))
        chunk = p.lines[self.page * p.per_page:(self.page + 1) * p.per_page]
        self.info.clear()
        self.info.header(p.title)
        for i, (names, description) in enumerate(chunk):
            if i:
                self.info.divider()
            self.info.row(names, description)
        self.info.divider()
        self.info.footer(tr('стр. {v} из {pages}   ·   PgUp / PgDn — листать', v=self.page + 1, pages=pages))
        self.present()

    # --- подсказки при вводе ---
    def on_text(self, *_):
        if self.quiet:
            return
        self.hist_pos = None  # человек печатает сам: история закончилась
        self.paged = None
        self.suggestions = []
        self.arg_items = []
        raw = self.var.get()
        if not raw.strip():
            self.show_message(HINT)
            return
        word, sep, rest = raw.lstrip().partition(" ")
        cmd = self.registry.find(word)
        if sep and cmd:  # имя уже введено полностью, дальше идут аргументы
            self.arg_items = self.registry.complete(cmd, rest)
            if self.arg_items:
                self.arg_word = word
                self.sel = 0
                self.show_arg_items()
            else:
                self.info.clear()
                self.info.row(cmd.names, cmd.description)
                self.present()
            return
        self.suggestions = self.registry.suggest(word)
        self.sel = 0
        if self.suggestions:
            self.show_suggestions()
        else:
            self.show_message(tr("Нет такой команды. «помощь» — список команд"))

    def move(self, step):
        if self.hist_pos is not None or (not self.arg_items and not self.suggestions and not self.var.get().strip()):
            self.walk_history(step)
        elif self.arg_items:
            self.sel = (self.sel + step) % len(self.arg_items)
            sounds.play("cmd_move")
            self.show_arg_items()
        elif self.suggestions:
            self.sel = (self.sel + step) % len(self.suggestions)
            sounds.play("cmd_move")
            self.show_suggestions()
        return "break"

    def walk_history(self, step):
        """↑ идёт к старым командам, ↓ к новым; после самой новой поле очищается."""
        if not self.history:
            return
        if self.hist_pos is None:
            if step > 0:
                return
            self.hist_pos = len(self.history)
        pos = self.hist_pos + step
        if pos >= len(self.history):
            self.hist_pos = None
            self.set_text("")
            self.show_message(HINT)
            return
        self.hist_pos = max(0, pos)
        self.set_text(self.history[self.hist_pos])
        self.entry.icursor("end")
        self.show_message(tr("История: ↑ раньше, ↓ позже. Enter — выполнить, или правь текст"))

    def remember(self, text):
        text = text.strip()
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
            del self.history[:-50]
            self.save_history()
        self.hist_pos = None
        
    def load_history(self):
        try:
            with open(HISTORY_FILE, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return []
        return [t for t in data if isinstance(t, str)][-50:] if isinstance(data, list) else []

    def save_history(self):
        try:
            storage.write_json(HISTORY_FILE, self.history)
        except OSError:
            pass  # история не критична: программа не должна из-за неё падать

    def complete(self, event=None):
        """Tab: подставить выбранную подсказку в поле."""
        if self.arg_items or self.suggestions:
            sounds.play("cmd_complete")
        if self.arg_items:
            insert = self.arg_items[self.sel][0]
            self.set_text(f"{self.arg_word} {insert}")
            self.entry.icursor("end")
            self.on_text()
        elif self.suggestions:
            _cmd, name = self.suggestions[self.sel]
            self.set_text(name + " ")
            self.entry.icursor("end")
            self.on_text()
        return "break"

    # --- выполнение ---
    def run(self, event=None):
        text = self.var.get()
        if self.arg_items:  # если показан список вариантов, выполняем выбранный
            text = f"{self.arg_word} {self.arg_items[self.sel][0]}"
        if not text.strip():
            return "break"
        result = self.registry.run(text)
        if isinstance(result, str):
            result = Reply(result)
        if not (isinstance(result, Reply) and result.error):
            self.remember(text)
        self.suggestions = []
        self.arg_items = []
        if result is None:
            sounds.play("command_ok")
            self.close()
        elif isinstance(result, Paged):
            self.paged = result
            self.page = result.page
            self.set_text("")
            self.show_page()
        else:
            if result.error:
                sounds.play("error")
            self.show_message(result.text, error=result.error)  # текст остаётся в поле
        return "break"

    def turn_page(self, step):
        if self.paged:
            self.page += step
            self.show_page()
        elif self.arg_items or self.suggestions:
            args = bool(self.arg_items)
            items, size = (self.arg_items, MAX_ARG_ITEMS) if args else (self.suggestions, MAX_SUGGESTIONS)
            pages = -(-len(items) // size)
            self.sel = ((self.sel // size + step) % pages) * size  # на первую строку соседней страницы
            sounds.play("cmd_move")
            (self.show_arg_items if args else self.show_suggestions)()
        return "break"