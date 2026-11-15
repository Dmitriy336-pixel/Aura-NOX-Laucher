"""Подсказка при наведении: маленькое окошко без рамки рядом с виджетом."""
import tkinter as tk

import theme


class Tooltip:
    def __init__(self, widget, text, wraplength=320, delay=250, side="right"):
        self.widget = widget
        self.side = side      # "right" или "left": с какой стороны от виджета показывать
        self.text = text
        self.wraplength = wraplength
        self.delay = delay    # через сколько миллисекунд после наведения показывать
        self.window = None
        self.job = None
        widget.bind("<Enter>", self.schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def schedule(self, event=None):
        self.cancel()
        self.job = self.widget.after(self.delay, self.show)

    def cancel(self):
        if self.job is not None:
            try:
                self.widget.after_cancel(self.job)
            except tk.TclError:
                pass
            self.job = None

    def show(self):
        self.job = None
        if self.window is not None or not self.widget.winfo_exists():
            return
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)  # без рамки и заголовка
        self.window.attributes("-topmost", True)
        tk.Label(
            self.window, text=self.text, justify="left", wraplength=self.wraplength,
            background=theme.pick(theme.TOOLTIP_BG), foreground=theme.pick(theme.TOOLTIP_TEXT), relief="solid", borderwidth=1,
            padx=8, pady=6,
        ).pack()
        self.window.update_idletasks()  # теперь известна ширина окошка
        if self.side == "left":
            x = self.widget.winfo_rootx() - self.window.winfo_reqwidth() - 8
        else:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() + 8
        self.window.wm_geometry(f"+{x}+{self.widget.winfo_rooty()}")

    def hide(self, event=None):
        self.cancel()
        if self.window is not None:
            try:
                self.window.destroy()
            except tk.TclError:
                pass
            self.window = None