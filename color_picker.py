"""Цвет плиток: окно выбора цвета для одной плитки и блок «Цвета плиток» в настройках."""
import tkinter as tk
from tkinter import colorchooser, messagebox

import customtkinter as ctk

import sounds
import theme
from config import COLORS, TILE_PALETTE
from i18n import tr

DIM = theme.DIM
PER_ROW = 7  # цветов палитры в строке
PALETTE = theme.TILE_COLORS + TILE_PALETTE[len(COLORS):]  # цвета плиток из темы и дополнительные


class ColorPicker(ctk.CTkToplevel):
    """Палитра: нажал на цвет, и плитка перекрашена. «Другой цвет…» открывает системный выбор."""

    def __init__(self, master, name, current, on_pick):
        super().__init__(master)
        self.on_pick = on_pick  # on_pick("#rrggbb")
        self.current = (current or "").lower()

        self.title(tr("Цвет плитки"))
        self.resizable(False, False)
        self.transient(master)
        width, height = 380, 250
        x = master.winfo_rootx() + max(0, (master.winfo_width() - width) // 2)
        y = master.winfo_rooty() + max(0, (master.winfo_height() - height) // 3)
        self.geometry(f"{width}x{height}+{x}+{y}")

        ctk.CTkLabel(self, text=name, wraplength=340, font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(16, 8))
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack()
        for i, color in enumerate(PALETTE):
            ctk.CTkButton(
                grid, text="", width=40, height=40, fg_color=color, hover_color=color,
                border_width=3 if color.lower() == self.current else 0, border_color=theme.SELECT_BORDER,
                command=lambda c=color: self.pick(c),
            ).grid(row=i // PER_ROW, column=i % PER_ROW, padx=4, pady=4)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(pady=14)
        ctk.CTkButton(buttons, text=tr("Другой цвет…"), width=130, command=self.custom).pack(side="left", padx=6)
        ctk.CTkButton(
            buttons, text=tr("Отмена"), width=90, fg_color="transparent", border_width=1,
            text_color=theme.GHOST_TEXT, hover_color=theme.GHOST_HOVER, command=self.destroy,
        ).pack(side="left", padx=6)

        self.bind("<Escape>", lambda e: self.destroy())
        self.after(150, self.start_listening)

    def start_listening(self):
        try:
            self.grab_set()  # пока окно открыто, остальные не отвечают
        except tk.TclError:
            pass
        self.focus_force()

    def pick(self, color):
        sounds.play("color_set")
        self.destroy()
        self.on_pick(color)

    def custom(self):
        chosen = colorchooser.askcolor(color=self.current or None, parent=self, title=tr("Цвет плитки"))[1]
        if chosen:
            self.pick(chosen)


class TileColorsPage(ctk.CTkFrame):
    """Блок настроек: перекрасить сразу все плитки. Цвет одной плитки: правый клик по ней, «Цвет…»."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        ctk.CTkLabel(
            self, anchor="w", justify="left", wraplength=480, text_color=DIM,
            text=tr("Цвет одной плитки: правый клик по ней, пункт «Цвет…». Цвет плитки не меняется "
                 "при перетаскивании. Новые плитки получают цвета палитры по кругу."),
        ).pack(fill="x", padx=8, pady=(0, 8))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", padx=8)
        ctk.CTkButton(row, text=tr("Палитра по порядку"), width=170, command=self.by_palette).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text=tr("Один цвет для всех…"), width=170, command=self.one_color).pack(side="left")

    def confirm(self):
        return messagebox.askyesno(
            tr("Цвета плиток"), tr("Все плитки будут перекрашены, прежние цвета пропадут.\nПродолжить?"),
            parent=self.winfo_toplevel())

    def by_palette(self):
        if self.confirm():
            self.app.recolor_tiles(None)

    def one_color(self):
        chosen = colorchooser.askcolor(parent=self.winfo_toplevel(), title=tr("Цвет для всех плиток"))[1]
        if chosen and self.confirm():
            self.app.recolor_tiles(chosen)
