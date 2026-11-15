"""Раздел «О программе» в настройках: кто автор, версия, условия, где лежат данные, из чего собрана программа,
и сведения для сообщения об ошибке (их можно скопировать одной кнопкой)."""
import os
import platform
import sys
import tkinter as tk
import webbrowser

import customtkinter as ctk
from PIL import Image

import firstrun
import i18n
import legal
import links
import sounds
import theme
from config import APP_NAME, BASE_DIR, ICON_PATH, VERSION
from i18n import tr
from notes_store import default_dir

DIM = theme.DIM
ACCENT = theme.ACCENT

# сторонние компоненты: (название, лицензия)
COMPONENTS = [("Python", "PSF"), ("CustomTkinter", "MIT"), ("Pillow", "HPND")]

# материалы других авторов, которых лицензия требует указывать: (что, название, автор, сайт автора, лицензия, ссылка на неё)
CREDITS = [
    ("Звуковые эффекты интерфейса", "Universal UI Soundpack", "Nathan Gibson",
     "https://nathangibson.myportfolio.com", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
]


def version_of(module_name):
    try:
        module = __import__(module_name)
        return getattr(module, "__version__", "")
    except ImportError:
        return ""


def open_folder(path):
    """Открывает папку в проводнике (создаёт её, если ещё нет)."""
    try:
        os.makedirs(path, exist_ok=True)
        os.startfile(path)
    except OSError:
        pass


class AboutPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        lang = i18n.language()
        self.build_header(lang)
        self.section(tr("О программе"))
        self.text(tr("Лаунчер для Windows: плитки программ, командная строка, заметки, темы и звуки."))
        self.section(tr("Условия"))
        self.text(tr("Программа бесплатна. Продавать её и просить за неё донаты нельзя. Менять и раздавать можно "
                     "бесплатно. Оригинал только от автора: за версии из других источников и за добавленный в них "
                     "код автор не отвечает."))
        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.pack(anchor="w", padx=8, pady=(6, 0))
        ctk.CTkButton(buttons, text=tr("Условия использования"), width=190,
                      command=lambda: firstrun.TermsWindow(self.winfo_toplevel())).pack(side="left", padx=(0, 8))
        ctk.CTkButton(buttons, text=tr("Как пользоваться"), width=150,
                      command=lambda: firstrun.GuideWindow(self.winfo_toplevel())).pack(side="left")
        self.build_folders()
        self.build_components()
        self.build_system()

    # --- блоки ---
    def build_header(self, lang):
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=8, pady=(0, 6))
        try:
            image = ctk.CTkImage(Image.open(ICON_PATH), size=(64, 64))
            ctk.CTkLabel(head, text="", image=image).pack(side="left", padx=(0, 14))
        except Exception:
            pass  # нет иконки или файл не читается: заголовок остаётся без картинки
        info = ctk.CTkFrame(head, fg_color="transparent")
        info.pack(side="left")
        ctk.CTkLabel(info, text=APP_NAME, font=ctk.CTkFont(size=24, weight="bold"), anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=tr("Версия {version}", version=VERSION), text_color=DIM, anchor="w").pack(anchor="w")
        ctk.CTkLabel(
            info, text=tr("Автор: {author}", author=legal.pick(legal.AUTHOR, lang)), text_color=DIM, anchor="w",
        ).pack(anchor="w")
        links.linked_label(
            info, tr("Официальный источник: {source}", source=legal.pick(legal.SOURCE, lang)), text_color=DIM,
        ).pack(anchor="w")

    def section(self, title):
        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=16, weight="bold"), anchor="w").pack(
            anchor="w", padx=8, pady=(16, 4))

    def text(self, text):
        ctk.CTkLabel(self, text=text, text_color=DIM, anchor="w", justify="left", wraplength=480).pack(
            anchor="w", padx=8)

    def build_folders(self):
        self.section(tr("Где лежат данные"))
        notes = self.app.settings.get("notes_dir") or default_dir()
        rows = [
            (tr("Лаунчер, плитки и настройки"), BASE_DIR),
            (tr("Заметки"), notes),
            (tr("Темы"), theme.THEMES_DIR),
            (tr("Звуки"), sounds.SOUNDS_DIR),
        ]
        for title, path in rows:
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(fill="x", padx=8, pady=2)
            row.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(row, text=title, anchor="w", width=170).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(row, text=path, text_color=DIM, anchor="w", justify="left", wraplength=210).grid(
                row=0, column=1, sticky="w", padx=(6, 6))
            ctk.CTkButton(row, text=tr("Открыть"), width=80, height=26,
                          command=lambda p=path: open_folder(p)).grid(row=0, column=2)

    def build_components(self):
        self.section(tr("Из чего сделано"))
        self.text(tr("Программа использует сторонние компоненты со своими лицензиями. Темы, звуки и иконки, "
                     "которые вы добавляете, остаются собственностью их авторов."))
        versions = {"Python": platform.python_version(), "CustomTkinter": version_of("customtkinter"),
                    "Pillow": version_of("PIL")}
        for name, licence in COMPONENTS:
            version = versions.get(name, "")
            ctk.CTkLabel(
                self, text=f"•  {name} {version}  ({licence})".replace("  (", " (").replace("  ", " "),
                text_color=ACCENT, anchor="w",
            ).pack(anchor="w", padx=16, pady=1)
        for what, title, author, site, licence, licence_url in CREDITS:
            ctk.CTkLabel(self, text=f"{tr(what)}: {title}", anchor="w", justify="left", wraplength=480).pack(
                anchor="w", padx=16, pady=(8, 0))
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.pack(anchor="w", padx=16, pady=(0, 2))
            ctk.CTkLabel(row, text=f"{tr('Автор')}: {author}  ({licence})", text_color=ACCENT, anchor="w").pack(
                side="left", padx=(0, 10))
            ctk.CTkButton(row, text=tr("Сайт автора"), width=100, height=26,
                          command=lambda u=site: webbrowser.open(u)).pack(side="left", padx=(0, 6))
            ctk.CTkButton(row, text=tr("Лицензия"), width=90, height=26,
                          command=lambda u=licence_url: webbrowser.open(u)).pack(side="left")

    def system_info(self):
        return "\n".join([
            f"{APP_NAME} {VERSION}",
            f"Python {platform.python_version()} ({platform.architecture()[0]})",
            f"CustomTkinter {version_of('customtkinter')}, Pillow {version_of('PIL')}",
            f"Windows: {platform.platform()}",
            f"Language: {i18n.language()}",
            f"Theme: {self.app.settings.get('theme_name', 'default')} ({self.app.settings.get('theme_mode', 'dark')})",
            f"Frozen exe: {bool(getattr(sys, 'frozen', False))}",
        ])

    def build_system(self):
        self.section(tr("Сведения для сообщения об ошибке"))
        self.text(tr("Если что-то не работает, скопируйте это и приложите к сообщению."))
        box = ctk.CTkTextbox(self, height=130, wrap="none")
        box.pack(fill="x", padx=8, pady=(6, 4))
        box.insert("1.0", self.system_info())
        box.configure(state="disabled")
        self.copy_btn = ctk.CTkButton(self, text=tr("Скопировать"), width=130, command=self.copy)
        self.copy_btn.pack(anchor="w", padx=8, pady=(0, 8))

    def copy(self):
        try:
            self.clipboard_clear()
            self.clipboard_append(self.system_info())
            sounds.play("copied")
            self.copy_btn.configure(text=tr("Скопировано"))
            self.after(1500, lambda: self.copy_btn.winfo_exists() and self.copy_btn.configure(text=tr("Скопировать")))
        except tk.TclError:
            pass
