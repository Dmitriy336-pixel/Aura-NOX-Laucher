"""Окно настроек: слева отделы, справа категории и подкатегории выбранного отдела.
Что показывать, берётся из settings_data.py. У каждого пункта есть кнопка «Сброс»,
внизу списка отделов кнопка «Сбросить всё»; заводские значения лежат в config.DEFAULT_SETTINGS."""
import os
from tooltip import Tooltip
from tkinter import messagebox

import customtkinter as ctk

from scrollfix import fix_later
import sounds
import theme
from config import DEFAULT_SETTINGS, HOTKEY_SETTINGS, ICON_PATH
from hotkey_capture import HotkeyCapture, pretty
from settings_data import SETTINGS
from about_page import AboutPage
from faq_page import FaqPage
from commands_page import CommandsPage
from color_picker import TileColorsPage
from controls_page import ShortcutsReference, TileKeysPage
from icon_tools import IconsPage
from notes_settings import NotesFolderPage
from theme_page import ThemePage
from i18n import tr

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, settings, on_change):
        super().__init__(master)
        self.settings = settings    # текущие значения (тот же словарь, что и у окна лаунчера)
        self.on_change = on_change  # on_change(ключ, новое значение)
        self.current = 0            # номер открытого отдела
        self.slider_job = None      # отложенное применение значения ползунка
        self.reset_buttons = {}     # ключ настройки -> её кнопка «Сброс»

        self.title(tr("Настройки"))
        self.geometry("900x480")
        self.minsize(520, 360)
        self.transient(master)  # окно настроек остаётся поверх основного
        if os.path.exists(ICON_PATH):
            self.after(300, lambda: self.iconbitmap(ICON_PATH))  # у окна настроек та же иконка

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # слева: список отделов
        self.nav = ctk.CTkFrame(self, width=180, corner_radius=0)
        self.nav.grid(row=0, column=0, sticky="ns")
        self.nav.grid_propagate(False)
        self.nav.grid_columnconfigure(0, weight=1)

        self.nav_buttons = []
        for i, section in enumerate(SETTINGS):
            btn = ctk.CTkButton(
                self.nav, text=section["title"], anchor="w", fg_color="transparent",
                text_color=theme.GHOST_TEXT, hover_color=theme.GHOST_HOVER,
                command=lambda idx=i: self.go(idx),
            )
            btn.grid(row=i, column=0, padx=10, pady=(10 if i == 0 else 2, 2), sticky="ew")
            self.nav_buttons.append(btn)

        # внизу списка отделов: полный сброс (пустая растягивающаяся строка прижимает кнопку вниз)
        self.nav.grid_rowconfigure(len(SETTINGS), weight=1)
        ctk.CTkButton(
            self.nav, text=tr("Сбросить всё"), fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            command=self.reset_all,
        ).grid(row=len(SETTINGS) + 1, column=0, padx=10, pady=10, sticky="ew")

        # справа: содержимое выбранного отдела
        self.content = ctk.CTkScrollableFrame(self)
        self.content.grid(row=0, column=1, sticky="nsew", padx=8, pady=8)

        self.show_section(0)
        self.after(100, self.focus)

    # --- применение и сброс ---
    def apply(self, key, value):
        """Передать новое значение лаунчеру и обновить состояние кнопок «Сброс»."""
        self.on_change(key, value)
        if self.winfo_exists():  # лаунчер мог закрыться или перезапуститься прямо при смене настройки
            self.sync_resets()

    def on_switch(self, key, value):
        """Переключатель: «выключено» звучит до применения, «включено» после (так работает и сам переключатель звуков)."""
        if value:
            self.apply(key, value)
            sounds.play("toggle_on")
        else:
            sounds.play("toggle_off")
            self.apply(key, value)

    def sync_resets(self):
        """Кнопка «Сброс» активна, только если значение отличается от заводского."""
        for key, btn in self.reset_buttons.items():
            if btn.winfo_exists():
                changed = self.settings.get(key) != DEFAULT_SETTINGS[key]
                btn.configure(state="normal" if changed else "disabled")

    def cancel_slider_job(self):
        if self.slider_job is not None:  # значение ползунка, которое ещё не успело примениться
            self.after_cancel(self.slider_job)
            self.slider_job = None

    def reset_one(self, key):
        sounds.play("click")
        self.cancel_slider_job()
        self.apply(key, DEFAULT_SETTINGS[key])
        self.refresh()  # перерисовываем, чтобы пункт показал заводское значение

    def reset_all(self):
        if not messagebox.askyesno(
            tr("Сброс настроек"), tr("Вернуть все настройки к заводским?\nПлитки не изменятся."), parent=self
        ):
            return
        sounds.play("click")
        self.cancel_slider_job()
        for key, default in DEFAULT_SETTINGS.items():
            if self.settings.get(key) != default:  # трогаем только то, что менялось
                self.apply(key, default)
        self.refresh()

    # --- отрисовка ---
    def refresh(self):
        """Перерисовать открытый отдел (например, после сброса или отката значения). Прокрутка остаётся."""
        self.show_section(self.current, keep_scroll=True)

    def go(self, index):
        """Нажатие на отдел в списке слева."""
        if index != self.current:
            sounds.play("nav")
        self.show_section(index)

    def show_section(self, index, keep_scroll=False):
        """Открыть отдел. При переходе на другой отдел прокрутка возвращается наверх."""
        self.build_section(index)
        fix_later(self.content, to_top=not keep_scroll)

    def build_section(self, index):
        self.current = index
        for i, btn in enumerate(self.nav_buttons):
            btn.configure(fg_color=theme.NAV_SELECTED if i == index else "transparent")

        for child in self.content.winfo_children():
            child.destroy()
        self.reset_buttons = {}

        section = SETTINGS[index]
        ctk.CTkLabel(
            self.content, text=section["title"], font=ctk.CTkFont(size=22, weight="bold")
        ).pack(anchor="w", padx=8, pady=(4, 12))

        if section.get("custom") == "faq":
            FaqPage(self.content).pack(fill="x", padx=8)
            return

        if section.get("custom") == "about":
            AboutPage(self.content, self.master).pack(fill="x", padx=8)
            return

        if section.get("custom") == "commands":  # отдел с собственным устройством, а не списком пунктов
            CommandsPage(self.content, self.master).pack(fill="x", padx=8)
            return

        for category in section["categories"]:
            ctk.CTkLabel(
                self.content, text=category["title"], font=ctk.CTkFont(size=16, weight="bold")
            ).pack(anchor="w", padx=8, pady=(10, 4))
            for item in category["subcategories"]:
                self.draw_item(item)

        self.sync_resets()
        
    def draw_item(self, item):
        if isinstance(item, dict) and "custom" in item:  # блок со своим устройством, а не обычный пункт
            if item["custom"] == "shortcuts":
                ShortcutsReference(self.content).pack(fill="x", padx=28)
            elif item["custom"] == "tile_keys":
                TileKeysPage(self.content, self.master).pack(fill="x", padx=28)
            elif item["custom"] == "tile_colors":
                TileColorsPage(self.content, self.master).pack(fill="x", padx=28)
            elif item["custom"] == "icons":
                IconsPage(self.content, self.master).pack(fill="x", padx=28)
            elif item["custom"] == "theme_pack":
                ThemePage(self.content, self.master).pack(fill="x", padx=28)
            elif item["custom"] == "notes_folder":
                NotesFolderPage(self.content, self.master).pack(fill="x", padx=28)
            return

        if isinstance(item, str):  # заглушка без управления
            ctk.CTkLabel(self.content, text=f"▸ {item}", text_color="gray").pack(
                anchor="w", padx=28, pady=2
            )
            return

        key = item["key"]
        kind = item["type"]
        title = item["title"]

        # у выбора и ползунка подпись стоит над элементом, у переключателя она внутри него
        title_label = None
        if kind in ("choice", "slider", "hotkey"):
            text = f"{title}: {self.settings[key]}{item.get('unit', '')}" if kind == "slider" else title
            title_label = ctk.CTkLabel(self.content, text=text)
            title_label.pack(anchor="w", padx=28, pady=(8, 0))

        # строка пункта: сам элемент, затем «?» с подсказкой (если есть), затем «Сброс»;
        # всё на одной линии, поэтому кнопки и знаки стоят точно напротив элемента
        row = ctk.CTkFrame(self.content, fg_color="transparent")
        row.pack(anchor="w", padx=28, pady=(6 if title_label is None else 2, 4))

        if kind == "switch":
            var = ctk.BooleanVar(value=self.settings[key])
            ctk.CTkSwitch(
                row, text=title, variable=var,
                command=lambda: self.on_switch(key, var.get()),
            ).pack(side="left")

        elif kind == "choice":
            options = item["options"]  # {"значение": "Подпись на кнопке"}

            def on_pick(label):
                value = next(k for k, v in options.items() if v == label)
                self.apply(key, value)
                sounds.play("option")

            seg = ctk.CTkSegmentedButton(row, values=list(options.values()), command=on_pick)
            seg.set(options[self.settings[key]])
            seg.pack(side="left")

        elif kind == "slider":
            lo, hi, step = item["min"], item["max"], item.get("step", 1)
            unit = item.get("unit", "")

            def on_slide(raw):
                value = lo + round((raw - lo) / step) * step  # прижимаем к шагу
                title_label.configure(text=f"{title}: {value}{unit}")
                self.cancel_slider_job()
                # применяем, когда ползунок остановился, а не на каждый пиксель
                self.slider_job = self.after(250, lambda: (self.apply(key, value), sounds.play("option")))

            slider = ctk.CTkSlider(
                row, from_=lo, to=hi, width=300,
                number_of_steps=(hi - lo) // step, command=on_slide,
            )
            slider.set(self.settings[key])
            slider.pack(side="left")
            
        elif kind == "hotkey":
            def on_pick(combo):
                self.apply(key, combo)
                sounds.play("hotkey_set")
                self.refresh()  # кнопка покажет новую комбинацию

            def change():
                others = [self.settings[k] for k in HOTKEY_SETTINGS if k != key]
                HotkeyCapture(self, title, self.settings[key], others, on_pick)

            ctk.CTkButton(row, text=pretty(self.settings[key]), width=170, command=change).pack(side="left")

        if item.get("hint"):
            help_label = ctk.CTkLabel(
                row, text="?", width=24, height=24, corner_radius=12,
                fg_color=theme.HELP_BADGE, text_color=theme.HELP_TEXT,
            )
            help_label.pack(side="left", padx=(14, 0))
            Tooltip(help_label, item["hint"])  # всплывает при наведении мыши

        reset_btn = ctk.CTkButton(
            row, text=tr("Сброс"), width=60, height=26, fg_color="transparent", border_width=1,
            text_color=theme.GHOST_TEXT, hover_color=theme.GHOST_HOVER,
            command=lambda: self.reset_one(key),
        )
        reset_btn.pack(side="left", padx=(14, 0))
        self.reset_buttons[key] = reset_btn