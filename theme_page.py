"""Раздел «Темы» в настройках: карточки тем (картинка и название), добавление и создание темы, перезапуск для применения."""
import os
from tkinter import filedialog, messagebox

import customtkinter as ctk

import sounds
import theme
from i18n import tr

COLUMNS = 3
CARD_W, CARD_H = 140, 160
PREVIEW = 96  # размер картинки на карточке


def short(title, limit=17):
    return title if len(title) <= limit else title[:limit - 1] + "…"


class ThemePage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        known = {folder for folder, _ in theme.list_themes()}
        self.selected = app.settings.get("theme_name", theme.DEFAULT_NAME)
        if self.selected not in known:
            self.selected = theme.DEFAULT_NAME  # выбранную тему удалили
        self.cards = {}  # папка темы -> кнопка-карточка

        ctk.CTkLabel(
            self, anchor="w", justify="left", wraplength=480, text_color=theme.DIM,
            text=tr("Нажми на карточку, чтобы выбрать тему. «✓» отмечает ту, что включена сейчас. "
                 "Новая тема это папка в «themes»: скопируй её туда, добавь кнопкой «＋» или создай свою "
                 "(получится копия с полным списком цветов, шрифтов и скруглений, останется поправить нужное). "
                 "Выбранная тема применяется после перезапуска."),
        ).pack(fill="x", padx=8, pady=(0, 8))
        self.grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.grid_frame.pack(fill="x")

        # кнопки в два ряда: так они помещаются при любом масштабе экрана
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(anchor="w", padx=8, pady=(10, 0))
        self.restart_btn = ctk.CTkButton(
            top, text=tr("Перезапустить и применить"), width=240, state="disabled", command=self.restart)
        self.restart_btn.pack(side="left")
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(anchor="w", padx=8, pady=(8, 0))
        ctk.CTkButton(bottom, text=tr("Создать свою"), width=130, command=self.create).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bottom, text=tr("Папка тем"), width=110, command=self.open_folder).pack(side="left", padx=(0, 8))
        ctk.CTkButton(bottom, text=tr("Обновить"), width=100, command=self.refresh).pack(side="left")
        self.status = ctk.CTkLabel(self, text="", anchor="w", justify="left", wraplength=480, text_color=theme.DIM)
        self.status.pack(fill="x", padx=10, pady=(6, 0))
        self.render()

    # --- карточки ---
    def render(self):
        for child in self.grid_frame.winfo_children():
            child.destroy()
        self.cards = {}
        active = theme.current_name()
        themes = theme.list_themes()
        for i, (folder, title) in enumerate(themes):
            card = ctk.CTkButton(
                self.grid_frame, text=("✓ " if folder == active else "") + short(title),
                image=theme.preview(folder, PREVIEW), compound="top", width=CARD_W, height=CARD_H,
                fg_color=theme.CARD_BG, hover_color=theme.CARD_HOVER, text_color=theme.GHOST_TEXT,
                border_width=0, command=lambda f=folder: self.select(f),
            )
            card.grid(row=i // COLUMNS, column=i % COLUMNS, padx=5, pady=5)
            self.cards[folder] = card
        plus = ctk.CTkButton(
            self.grid_frame, text=tr("＋\nДобавить тему"), width=CARD_W, height=CARD_H, font=ctk.CTkFont(size=14),
            fg_color="transparent", border_width=2, border_color=theme.TILE_BORDER,
            text_color=theme.GHOST_TEXT, hover_color=theme.GHOST_HOVER, command=self.add,
        )
        plus.grid(row=len(themes) // COLUMNS, column=len(themes) % COLUMNS, padx=5, pady=5)
        self.paint_selection()

    def paint_selection(self):
        for folder, card in self.cards.items():
            if folder == self.selected:
                card.configure(border_width=3, border_color=theme.SELECT_BORDER)
            else:
                card.configure(border_width=0)

    def title_of(self, folder):
        return next((t for f, t in theme.list_themes() if f == folder), folder)

    # --- действия ---
    def select(self, folder):
        sounds.play("theme_select")
        self.selected = folder
        self.app.set_theme(folder)
        self.paint_selection()
        if folder == theme.current_name():
            self.restart_btn.configure(state="disabled")
            self.status.configure(text=tr("Эта тема уже включена."))
        else:
            self.restart_btn.configure(state="normal")
            self.status.configure(text=tr('Выбрана «{v}». Нажми «Перезапустить и применить».', v=self.title_of(folder)))

    def add(self):
        src = filedialog.askdirectory(parent=self.winfo_toplevel(), title=tr("Папка темы (в ней лежит theme.json)"))
        if not src:
            return
        name, error = theme.add_theme(src)
        if error:
            messagebox.showerror(tr("Тема"), error, parent=self.winfo_toplevel())
            return
        theme.clear_previews()
        self.render()
        self.select(name)

    def create(self):
        title = ctk.CTkInputDialog(text=tr("Название новой темы:"), title=tr("Создать тему")).get_input()
        if title is None:
            return  # закрыли окно
        name, error = theme.create_theme(title)
        if error:
            messagebox.showerror(tr("Тема"), error, parent=self.winfo_toplevel())
            return
        theme.clear_previews()
        self.render()
        self.select(name)
        self.status.configure(
            text=tr('Тема создана: themes\\{name}. Открой в ней theme.json, поменяй нужное, затем «Обновить» и «Перезапустить».', name=name))

    def refresh(self):
        theme.clear_previews()
        self.render()
        self.status.configure(text=tr("Список обновлён."))

    def restart(self):
        self.app.restart()

    def open_folder(self):
        try:
            os.makedirs(theme.THEMES_DIR, exist_ok=True)
            os.startfile(theme.THEMES_DIR)  # только Windows
        except (OSError, AttributeError) as e:
            messagebox.showerror(tr("Тема"), tr('Не удалось открыть папку:\n{THEMES_DIR}\n\n{e}', THEMES_DIR=theme.THEMES_DIR, e=e),
                                 parent=self.winfo_toplevel())