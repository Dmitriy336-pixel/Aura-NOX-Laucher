"""Окно первого запуска: выбор языка, условия использования, короткая инструкция.
Показывается один раз (пока в settings.json нет terms_seen с текущей версией условий) и до главного окна:
выбранный язык сразу попадает в настройки, и главное окно стартует уже на нём.
Тексты лежат в legal.py. Условия только показываются: принимать их кнопкой не нужно, крестик тоже закрывает окно."""
import os

import customtkinter as ctk

import i18n
import legal
import links
import storage
from config import APP_NAME, ICON_PATH

WIDTH, HEIGHT = 660, 560
DIM = ("gray35", "gray65")
ACCENT = ("#1f538d", "#6aa9ff")


def center(window, width, height):
    scale = window.winfo_fpixels("1i") / 96
    w, h = int(width * scale), int(height * scale)
    x = (window.winfo_screenwidth() - w) // 2
    y = (window.winfo_screenheight() - h) // 2
    window.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")


def set_icon(window):
    if os.path.exists(ICON_PATH):
        def apply():
            try:
                window.iconbitmap(ICON_PATH)
            except Exception:
                pass
        window.after(300, apply)  # CustomTkinter ставит свою иконку позже, поэтому ставим нашу чуть позже


def terms_box(master, lang, height=None):
    """Прокручиваемый текст условий (только для чтения)."""
    box = ctk.CTkTextbox(master, wrap="word", font=ctk.CTkFont(size=14), height=height or 300)
    links.fill_text(box, legal.terms_text(lang))  # адрес источника кликабельный
    return box


class Wizard(ctk.CTk):
    PAGES = ("language", "terms", "guide")

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.lang = settings.get("language", i18n.DEFAULT)
        self.page = 0
        self.title(APP_NAME)
        center(self, WIDTH, HEIGHT)
        self.minsize(520, 440)
        set_icon(self)
        self.protocol("WM_DELETE_WINDOW", self.finish)  # крестик: просто продолжить

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.grid(row=0, column=0, sticky="nsew", padx=24, pady=(20, 8))
        self.nav = ctk.CTkFrame(self, fg_color="transparent")
        self.nav.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 18))
        self.nav.grid_columnconfigure(1, weight=1)
        self.show()

    @property
    def ui(self):
        return legal.pick(legal.UI, self.lang)

    def show(self):
        for frame in (self.body, self.nav):
            for child in frame.winfo_children():
                child.destroy()
        getattr(self, "build_" + self.PAGES[self.page])()
        self.build_nav()

    def heading(self, text):
        ctk.CTkLabel(self.body, text=text, font=ctk.CTkFont(size=22, weight="bold"), anchor="w").pack(
            fill="x", pady=(0, 10))

    # --- страницы ---
    def build_language(self):
        self.heading(self.ui["language_title"])
        ctk.CTkLabel(self.body, text=self.ui["language_hint"], text_color=DIM, anchor="w").pack(fill="x", pady=(0, 16))
        for code in i18n.LANGS:
            name = i18n.language_name(code, self.lang)
            chosen = code == self.lang
            ctk.CTkButton(
                self.body, text=("✓  " if chosen else "") + name, height=56, font=ctk.CTkFont(size=18),
                fg_color=None if chosen else "transparent", border_width=2,
                text_color=None if chosen else ("gray10", "gray90"),
                command=lambda c=code: self.pick_language(c),
            ).pack(fill="x", pady=5)

    def pick_language(self, code):
        self.lang = code
        self.show()  # страница и кнопки сразу переходят на выбранный язык

    def build_terms(self):
        self.heading(self.ui["terms_title"])
        terms_box(self.body, self.lang).pack(fill="both", expand=True)

    def build_guide(self):
        self.heading(self.ui["guide_title"])
        box = ctk.CTkScrollableFrame(self.body, corner_radius=8)
        box.pack(fill="both", expand=True)
        box.grid_columnconfigure(1, weight=1)
        for row, (keys, text) in enumerate(legal.pick(legal.GUIDE, self.lang)):
            ctk.CTkLabel(
                box, text=keys, text_color=ACCENT, anchor="nw", justify="left", width=190, wraplength=185,
                font=ctk.CTkFont(size=14, weight="bold"),
            ).grid(row=row, column=0, sticky="nw", padx=(8, 8), pady=5)
            ctk.CTkLabel(
                box, text=text, anchor="w", justify="left", wraplength=360,
            ).grid(row=row, column=1, sticky="w", padx=(0, 8), pady=5)

    # --- кнопки внизу ---
    def build_nav(self):
        total = len(self.PAGES)
        ctk.CTkLabel(
            self.nav, text=self.ui["step"].format(n=self.page + 1, total=total), text_color=DIM,
        ).grid(row=0, column=1)
        if self.page > 0:
            ctk.CTkButton(
                self.nav, text=self.ui["back"], width=110, fg_color="transparent", border_width=1,
                text_color=("gray10", "gray90"), command=lambda: self.go(-1),
            ).grid(row=0, column=0, sticky="w")
        last = self.page == total - 1
        ctk.CTkButton(
            self.nav, text=self.ui["start"] if last else self.ui["next"], width=130,
            command=self.finish if last else lambda: self.go(1),
        ).grid(row=0, column=2, sticky="e")

    def go(self, step):
        self.page = max(0, min(len(self.PAGES) - 1, self.page + step))
        self.show()

    def finish(self):
        self.settings["language"] = self.lang
        self.settings["terms_seen"] = legal.TERMS_VERSION
        try:
            storage.save_settings(self.settings)
        except OSError:
            pass  # не записалось: окно просто покажется в следующий раз
        self.quit()


def needed(settings):
    return settings.get("terms_seen") != legal.TERMS_VERSION


def run(settings):
    """Показывает окно первого запуска и ждёт его закрытия. Язык и отметка о показе сохраняются в settings."""
    wizard = Wizard(settings)
    wizard.mainloop()
    try:
        wizard.withdraw()
        for job in wizard.tk.call("after", "info"):  # иначе отложенные вызовы CustomTkinter падают после закрытия
            wizard.after_cancel(job)
    except Exception:
        pass
    try:
        wizard.destroy()
    except Exception:
        pass
    import tkinter
    tkinter._default_root = None  # если destroy споткнулся, старое окно осталось бы корневым и картинки создавались бы в нём


class TermsWindow(ctk.CTkToplevel):
    """Условия использования в любой момент (команда «условия»; позже и вкладка «О программе»)."""

    def __init__(self, master):
        super().__init__(master)
        lang = i18n.language()
        ui = legal.pick(legal.UI, lang)
        self.title(ui["terms_title"])
        center(self, 620, 520)
        self.minsize(480, 360)
        set_icon(self)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        terms_box(self, lang).grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))
        ctk.CTkButton(self, text=ui["close"], width=110, command=self.destroy).grid(row=1, column=0, pady=(0, 14))
        self.after(100, self.focus)


class GuideWindow(ctk.CTkToplevel):
    """Короткая инструкция в любой момент (кнопка в «О программе»)."""

    def __init__(self, master):
        super().__init__(master)
        lang = i18n.language()
        ui = legal.pick(legal.UI, lang)
        self.title(ui["guide_title"])
        center(self, 620, 520)
        self.minsize(480, 360)
        set_icon(self)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        box = ctk.CTkScrollableFrame(self, corner_radius=8)
        box.grid(row=0, column=0, sticky="nsew", padx=16, pady=(16, 8))
        box.grid_columnconfigure(1, weight=1)
        for row, (keys, text) in enumerate(legal.pick(legal.GUIDE, lang)):
            ctk.CTkLabel(
                box, text=keys, text_color=ACCENT, anchor="nw", justify="left", width=190, wraplength=185,
                font=ctk.CTkFont(size=14, weight="bold"),
            ).grid(row=row, column=0, sticky="nw", padx=(8, 8), pady=5)
            ctk.CTkLabel(box, text=text, anchor="w", justify="left", wraplength=330).grid(
                row=row, column=1, sticky="w", padx=(0, 8), pady=5)
        ctk.CTkButton(self, text=ui["close"], width=110, command=self.destroy).grid(row=1, column=0, pady=(0, 14))
        self.after(100, self.focus)
