"""Главное окно: собирает части вместе и решает, что делать при действиях."""
import ctypes
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

import autostart
import launchers
import powerplan
import sounds
import storage
import icon_tools
import theme
import tile_icons

from command_bar import CommandBar
from builtin_commands import build_registry
from color_picker import ColorPicker
from config import APP_NAME, ICON_PATH, QUICK_KEYS
from hotkey import HotkeyListener
from controls_page import assign_key, redistribute
from notes_store import NoteStore, default_dir
from notes_window import NotesWindow
from settings_window import SettingsWindow
from sidebar import Sidebar
from tile_grid import TileGrid
from i18n import tr

# тема оформления включается до создания любых окон
theme.apply(storage.load_settings().get("theme_name", theme.DEFAULT_NAME))
COLORS = theme.TILE_COLORS  # цвета плиток по кругу берутся из темы

# какая настройка какую кнопку правой панели показывает
SIDEBAR_BUTTONS = {"show_notes_btn": "notes", "show_lock_btn": "lock", "show_perf_btn": "perf"}


class App(ctk.CTk):
    def __init__(self, start_hidden=False):
        super().__init__()
        self.title(APP_NAME)
        self.settings = storage.load_settings()
        sounds.init(self.settings)  # тот же словарь: переключатель и громкость действуют сразу
        sounds.hook_messagebox()
        self.bind_all("<ButtonPress-1>", self.on_any_click, add="+")  # CustomTkinter запускает кнопку при нажатии, а не при отпускании
        ctk.set_appearance_mode(self.settings.get("theme_mode", "dark"))  # тёмная, светлая или как в Windows
        theme.apply()  # цвета кнопок и переключателей: до создания окон
        
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        scale = min(100, max(40, self.settings["window_scale"])) / 100
        self.win_w, win_h = int(sw * scale), int(sh * scale)
        self.geometry(f"{self.win_w}x{win_h}+{(sw - self.win_w) // 2}+{(sh - win_h) // 2}")
        self.minsize(400, 300)
        
            # CustomTkinter сам ставит свою иконку через ~200 мс, поэтому ставим нашу чуть позже
        self.after(300, self.apply_icon)  

        self.tiles = storage.load_tiles()
        changed = False
        for i, tile in enumerate(self.tiles):  # выдаём быстрые клавиши и цвета плиткам, у которых их ещё нет
            if tile.get("key") is None:  # "" значит, что клавишу убрали намеренно
                tile["key"] = self.free_key()
                changed = True
            if not tile.get("color"):  # цвет хранится у плитки, поэтому при перетаскивании она его не теряет
                tile["color"] = COLORS[i % len(COLORS)]
                changed = True
        if changed:
            storage.save_tiles(self.tiles)

        self.selected = 0  # позиция выбранной плитки: 0 = "+", 1.. = плитки
        self.zone = "grid"      # где рамка выбора: "grid" (плитки) или "sidebar" (правая панель)
        self.sidebar_index = 0  # выбранная кнопка на панели
        self.resize_job = None
        self.render_job = None  # отложенная перерисовка плиток
        self.settings_window = None
        self.notes_window = None
        
        # поток горячей клавиши зовёт нас из другого потока, поэтому передаём вызов через after
        self.hotkey = HotkeyListener(lambda name: self.after(0, self.on_hotkey, name))
        self.registry = build_registry(self)  # команды командной строки
        self.command_bar = None               # сама панель создаётся при первом вызове

        # две колонки: сетка плиток | узкая правая панель
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(
            self, on_settings=self.open_settings, on_command=self.toggle_command_bar,
            on_perf=self.toggle_performance, on_notes=self.open_notes, on_lock=self.toggle_tile_lock,
            width=self.settings["sidebar_width"],
        )
        self.sidebar.set_lock_active(self.tiles_locked())
        for setting, name in SIDEBAR_BUTTONS.items():  # какие кнопки панели показывать
            self.sidebar.set_button_visible(name, self.settings[setting])
        self.sidebar.set_perf_active(self.performance_is_on())  # кнопка сразу показывает текущее состояние
        self.sidebar.grid(row=0, column=1, sticky="ns")

        self.tile_grid = TileGrid(
            self, on_add=self.add_tile, on_run=self.run_tile, on_menu=self.show_menu,
            on_move=self.move_tile, can_drag=lambda: not self.tiles_locked(),
        )
        self.tile_grid.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)

        self.bind("<Configure>", self.on_resize)
        self.bind("<Left>", lambda e: self.on_arrow(-1, 0))
        self.bind("<Right>", lambda e: self.on_arrow(1, 0))
        self.bind("<Up>", lambda e: self.on_arrow(0, -1))
        self.bind("<Down>", lambda e: self.on_arrow(0, 1))
        for name, dx, dy in (("Left", -1, 0), ("Right", 1, 0), ("Up", 0, -1), ("Down", 0, 1)):
            self.bind(f"<Control-{name}>", lambda e, dx=dx, dy=dy: self.on_ctrl_arrow(dx, dy))
        self.bind("<Tab>", self.on_tab)
        self.bind("<Return>", lambda e: self.activate_selected())
        self.bind("<Key>", self.on_key)
        self.bind("<Delete>", lambda e: self.open_delete_menu())
        self.bind("<F2>", lambda e: self.open_settings())
        self.bind("<Control-Key>", self.on_ctrl_key)
        self.protocol("WM_DELETE_WINDOW", self.on_close)  # что делать при нажатии крестика

        self.render()
        self.apply_hotkeys()
        if start_hidden and self.settings["background_mode"]:
            self.withdraw()

    def apply_icon(self):
        try:
            self.iconbitmap(ICON_PATH)
        except tk.TclError:
            pass  # нет иконки или она не читается: окно просто останется без неё

    # --- отрисовка и изменение размера ---
    def render(self):
        grid_width = self.win_w - self.settings["sidebar_width"]
        selected = self.selected if self.zone == "grid" else None  # рамка только в активной зоне
        self.tile_grid.render(self.tiles, grid_width, selected, self.settings)

    def on_resize(self, event):
        if event.widget is not self:   # <Configure> приходит и от вложенных виджетов
            return
        if event.width == self.win_w:
            return
        self.win_w = event.width
        if self.resize_job:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(80, self.render)  # перерисовываем, когда перестали тянуть

    # --- плитки ---
    def add_tile(self):
        path = filedialog.askopenfilename(
            title=tr("Выбери программу"),
            filetypes=[(tr("Программы и ярлыки"), "*.exe *.lnk *.bat"), (tr("Все файлы"), "*.*")],
        )
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0]
        tile = {"type": "app", "name": name, "target": path, "key": self.free_key(),
                "color": COLORS[len(self.tiles) % len(COLORS)]}
        if self.settings.get("auto_icons", True):
            icon = icon_tools.auto_icon(tile)  # из папки готовых иконок или из самой программы
            if icon:
                tile["icon"] = icon
        self.tiles.append(tile)
        storage.save_tiles(self.tiles)
        sounds.play("tile_add")
        self.selected = len(self.tiles)
        self.render()
        
    def add_tile_path(self, path):
        """Плитка для готового пути (из командной строки). Возвращает название плитки."""
        clean = path.rstrip("\\/")
        name = os.path.basename(clean) if os.path.isdir(path) else os.path.splitext(os.path.basename(clean))[0]
        tile = {"type": "app", "name": name or path, "target": path, "key": self.free_key(),
                "color": COLORS[len(self.tiles) % len(COLORS)]}
        if self.settings.get("auto_icons", True):
            icon = icon_tools.auto_icon(tile)
            if icon:
                tile["icon"] = icon
        self.tiles.append(tile)
        storage.save_tiles(self.tiles)
        sounds.play("tile_add")
        self.render()
        return tile["name"]

    def run_tile(self, tile):
        sounds.play("launch")  # сразу при нажатии, а не после запуска
        try:
            launchers.launch(tile)
        except OSError as e:
            sounds.play("error")
            messagebox.showerror(tr("Не удалось запустить"), str(e))
        except KeyError:
            sounds.play("error")
            messagebox.showerror(tr("Не удалось запустить"), tr('Неизвестный тип плитки: {v}', v=tile.get('type')))
        else:
            self.finish_launch()

    def delete_tile(self, index):
        if self.settings.get("confirm_delete", True) and not messagebox.askyesno(
                tr("Удалить плитку"), tr('Удалить плитку «{name}»?', name=self.tiles[index]['name']), parent=self):
            return
        icon = self.tiles[index].get("icon")
        del self.tiles[index]
        sounds.play("tile_delete")
        tile_icons.remove_if_unused(icon, self.tiles)  # файл иконки больше не нужен
        storage.save_tiles(self.tiles)
        self.selected = min(self.selected, len(self.tiles))
        self.render()

    def change_icon(self, index):
        path = filedialog.askopenfilename(
            title=tr("Выбери картинку для плитки"), parent=self,
            filetypes=[(tr("Картинки"), "*.png *.jpg *.jpeg *.ico *.bmp *.gif *.webp"), (tr("Все файлы"), "*.*")],
        )
        if not path:
            return
        try:
            name = tile_icons.import_icon(path)
        except OSError as e:
            messagebox.showerror(tr("Не удалось открыть картинку"), str(e), parent=self)
            return
        old = self.tiles[index].get("icon")
        self.tiles[index]["icon"] = name
        tile_icons.remove_if_unused(old, self.tiles)  # прежняя иконка больше не нужна
        storage.save_tiles(self.tiles)
        self.render()

    def clear_icon(self, index):
        old = self.tiles[index].pop("icon", None)
        tile_icons.remove_if_unused(old, self.tiles)
        storage.save_tiles(self.tiles)
        self.render()

    def set_tile_key(self, index, key):
        """Быстрая клавиша плитки; "" убирает её. Если клавишу занимала другая плитка, они меняются."""
        assign_key(self.tiles, index, key)
        storage.save_tiles(self.tiles)
        self.render_later()

    def reset_tile_keys(self):
        """Раздать клавиши всем плиткам заново по порядку."""
        redistribute(self.tiles, QUICK_KEYS)
        storage.save_tiles(self.tiles)
        self.render_later()

    def render_later(self):
        """Перерисовывает плитки не сразу, а когда правки прекратятся: серия правок даёт одну перерисовку."""
        if self.render_job:
            self.after_cancel(self.render_job)
        self.render_job = self.after(800, self.run_render_job)

    def run_render_job(self):
        self.render_job = None
        self.render()

    # --- перетаскивание плиток ---
    def tiles_locked(self):
        return bool(self.settings.get("tiles_locked", False))

    def toggle_tile_lock(self):
        locked = not self.tiles_locked()
        self.settings["tiles_locked"] = locked
        storage.save_settings(self.settings)
        self.sidebar.set_lock_active(locked)
        sounds.play("lock_on" if locked else "lock_off")

    def move_tile(self, src, dst):
        """Перетащили: плитка с места src встаёт на место dst, остальные сдвигаются."""
        tile = self.tiles.pop(src)
        self.tiles.insert(dst, tile)
        sounds.play("tile_move")
        storage.save_tiles(self.tiles)
        self.selected = dst + 1  # выбор остаётся на перенесённой плитке (позиция 0 это «+»)
        self.render()

    def on_ctrl_arrow(self, dx, dy):
        """Ctrl+стрелки: передвинуть выбранную плитку на соседнее место."""
        if self.zone == "grid" and self.selected > 0 and not self.tiles_locked():
            src = self.selected - 1
            dst = src + dx + dy * self.settings["columns"]
            if 0 <= dst < len(self.tiles):
                self.move_tile(src, dst)
        return "break"

    # --- автоматические иконки ---
    def auto_icon_for(self, index):
        """Подобрать иконку одной плитке (пункт меню). Прежняя иконка заменяется."""
        tile = self.tiles[index]
        name = icon_tools.auto_icon(tile)
        if name is None:
            messagebox.showinfo(
                tr("Иконка"), tr("Подходящей иконки нет ни в папке готовых иконок, ни в самой программе."), parent=self)
            return
        old = tile.get("icon")
        tile["icon"] = name
        tile_icons.remove_if_unused(old, self.tiles)
        storage.save_tiles(self.tiles)
        self.render()

    def fill_missing_icons(self):
        """Подбирает иконки плиткам без иконки. Возвращает (подобрано, было без иконки)."""
        missing = [t for t in self.tiles if not t.get("icon") and t.get("target")]
        done = 0
        for tile in missing:
            name = icon_tools.auto_icon(tile)
            if name:
                tile["icon"] = name
                done += 1
        if done:
            storage.save_tiles(self.tiles)
            self.render()
        return done, len(missing)

    # --- цвета плиток ---
    def pick_color(self, index):
        tile = self.tiles[index]
        ColorPicker(self, tile["name"], tile.get("color"), lambda color: self.set_tile_color(index, color))

    def set_tile_color(self, index, color):
        self.tiles[index]["color"] = color
        storage.save_tiles(self.tiles)
        self.render()

    def recolor_tiles(self, color=None):
        """Перекрасить все плитки: одним цветом или палитрой по порядку (color=None)."""
        for i, tile in enumerate(self.tiles):
            tile["color"] = color or COLORS[i % len(COLORS)]
        storage.save_tiles(self.tiles)
        self.render()

    # --- клавиатура ---
    def move_selection(self, delta):
        last = len(self.tiles)  # позиции: 0 = "+", 1..last = плитки
        new = max(0, min(last, self.selected + delta))
        if new != self.selected:
            sounds.play("select")
        self.selected = new
        self.tile_grid.select(self.selected)
    
    def on_tab(self, event):
        """Tab переносит рамку выбора между плитками и правой панелью."""
        sounds.play("select")
        if self.zone == "grid":
            self.zone = "sidebar"
            self.tile_grid.select(None)  # снимаем рамку с плиток
            self.sidebar.select(self.sidebar_index)
        else:
            self.zone = "grid"
            self.sidebar.select(None)
            self.tile_grid.select(self.selected)
        return "break"  # не даём Tk перебирать виджеты по Tab

    def on_arrow(self, dx, dy):
        """Стрелки: в сетке двигают выбор по плиткам, на панели ходят вверх и вниз."""
        if self.zone == "grid":
            self.move_selection(dx + dy * self.settings["columns"])
        elif dx < 0:       # на панели стрелка влево возвращает к плиткам
            self.on_tab(None)
        elif dy:
            self.move_sidebar(dy)

    def move_sidebar(self, dy):
        last = len(self.sidebar.buttons) - 1
        new = max(0, min(last, self.sidebar_index + dy))
        if new != self.sidebar_index:
            sounds.play("select")
        self.sidebar_index = new
        self.sidebar.select(self.sidebar_index)

    def activate_selected(self):
        if self.zone == "sidebar":
            self.sidebar.press(self.sidebar_index)
        elif self.selected == 0:
            self.add_tile()
        else:
            self.run_tile(self.tiles[self.selected - 1])

    def free_key(self):
        """Первая клавиша из QUICK_KEYS, которую ещё не занимает ни одна плитка."""
        used = {tile.get("key") for tile in self.tiles}
        for key in QUICK_KEYS:
            if key not in used:
                return key
        return None

    def on_key(self, event):
        # keycode = код физической клавиши: цифры 48-57, буквы 65-90 (не зависит от раскладки)
        code = event.keycode
        if 48 <= code <= 57 or 65 <= code <= 90:
            key = chr(code).lower()
            for tile in self.tiles:
                if tile.get("key") == key:
                    self.run_tile(tile)
                    return

    def on_ctrl_key(self, event):
        # keycode 81 = физическая клавиша Q, на любой раскладке
        if event.keycode == 81:
            self.quit_app()

    # --- меню плитки ---
    def show_menu(self, event, index):
        self.open_menu(event.x_root, event.y_root, index)

    def open_delete_menu(self):
        if self.zone != "grid" or self.selected == 0:
            return  # меню только у плиток, у "+" и у панели его нет
        btn = self.tile_grid.buttons[self.selected]
        x = btn.winfo_rootx() + btn.winfo_width() // 2
        y = btn.winfo_rooty() + btn.winfo_height() // 2
        self.open_menu(x, y, self.selected - 1)

    def open_menu(self, x, y, index):
        menu = tk.Menu(self, tearoff=0)
                # «Удалить» первым: привычное Delete, вниз, Enter по-прежнему удаляет плитку
        menu.add_command(label=tr("Удалить"), command=lambda: self.delete_tile(index))
        menu.add_command(label=tr("Цвет…"), command=lambda: self.pick_color(index))
        if self.tiles[index].get("target"):
            menu.add_command(label=tr("Подобрать иконку"), command=lambda: self.auto_icon_for(index))
        menu.add_command(label=tr("Сменить иконку…"), command=lambda: self.change_icon(index))
        if self.tiles[index].get("icon"):
            menu.add_command(label=tr("Убрать иконку"), command=lambda: self.clear_icon(index))
        sounds.play("menu_open")  # до показа: tk_popup ждёт закрытия меню
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # --- фоновый режим и окно ---
    def apply_hotkeys(self):
        """Включает горячие клавиши, которые сейчас нужны по настройкам."""
        wanted = {}
        if self.settings["background_mode"]:
            wanted["summon"] = self.settings["hotkey_summon"]    # вызов лаунчера из фона
        if self.settings["command_line"]:
            wanted["command"] = self.settings["hotkey_command"]  # вызов командной строки
        if self.settings.get("notes_hotkey", True):
            wanted["notes"] = self.settings["hotkey_notes"]      # открыть заметки
        failed = self.hotkey.start(wanted)

        if "summon" in failed:
            # без горячей клавиши из фона не вернуться, поэтому режим не включаем
            messagebox.showwarning(
                tr("Горячая клавиша"),
                tr('Не удалось занять {hotkey_summon}: комбинацию уже использует другая программа.', hotkey_summon=self.settings['hotkey_summon']),
            )
            self.settings["background_mode"] = False
        if "command" in failed:
            messagebox.showwarning(
                tr("Горячая клавиша"),
                tr('Не удалось занять {hotkey_command}: комбинацию уже использует другая программа.', hotkey_command=self.settings['hotkey_command']),
            )
            self.settings["command_line"] = False
        if "notes" in failed:
            messagebox.showwarning(
                tr("Горячая клавиша"),
                tr('Не удалось занять {hotkey_notes}: комбинацию уже использует другая программа.', hotkey_notes=self.settings['hotkey_notes']),
            )
            self.settings["notes_hotkey"] = False
        if failed:
            storage.save_settings(self.settings)
            self.refresh_settings_window()

        # кнопка командной строки на панели есть, только пока строка включена
        self.sidebar.set_command_visible(self.settings["command_line"])
        self.sidebar_index = 0
        if self.zone == "sidebar":
            self.sidebar.select(self.sidebar_index)

    def on_hotkey(self, name):
        if name == "summon":
            self.toggle_window()
        elif name == "command":
            self.toggle_command_bar()
        elif name == "notes":
            self.open_notes()

    def toggle_command_bar(self):
        if self.command_bar is None or not self.command_bar.winfo_exists():
            self.command_bar = CommandBar(self, self.registry)
            self.track_visible(self.command_bar, self.sidebar.command_btn)
        if self.command_bar.winfo_viewable():
            self.command_bar.close()
        else:
            sounds.play("command")
            self.command_bar.open()

    def reload_commands(self):
        """Пересобрать список команд (после изменения своих команд в настройках)."""
        self.registry = build_registry(self)
        if self.command_bar is not None and self.command_bar.winfo_exists():
            self.command_bar.registry = self.registry

    # --- режим высокой производительности ---
    def performance_is_on(self):
        scheme = self.settings.get("perf_scheme", "")
        return bool(scheme) and powerplan.active_scheme() == scheme

    def toggle_performance(self, want=None):
        """Включить (True), выключить (False) или переключить (None) режим высокой производительности.
        Меняет схему электропитания Windows и помнит прежнюю, чтобы вернуть её при выключении.
        Возвращает (текст, ошибка)."""
        is_on = self.performance_is_on()
        if want is None:
            want = not is_on
        if want == is_on:
            return (tr("Режим высокой производительности уже включён") if want
                    else tr("Режим высокой производительности уже выключен")), False

        if want:
            previous = powerplan.active_scheme()
            scheme = powerplan.enable_performance(self.settings.get("perf_scheme") or None)
            if scheme is None:
                message = tr("Не удалось включить: в системе недоступна схема высокой производительности")
                messagebox.showwarning(tr("Режим производительности"), message, parent=self)
                return message, True
            if previous == scheme:  # высокая производительность уже стояла, возвращаться будем к обычной
                previous = powerplan.BALANCED
            self.settings["perf_prev"] = previous or powerplan.BALANCED
            self.settings["perf_scheme"] = scheme
            text = tr("Режим высокой производительности включён")
        else:
            powerplan.set_active(self.settings.get("perf_prev") or powerplan.BALANCED)
            text = tr("Режим высокой производительности выключен, схема питания возвращена")
        storage.save_settings(self.settings)
        self.sidebar.set_perf_active(want)
        sounds.play("perf_on" if want else "perf_off")
        return text, False

    def hide_window(self):
        """Спрятать лаунчер: в фоновом режиме совсем, иначе свернуть."""
        if self.settings["background_mode"]:
            self.go_background()
        else:
            self.iconify()

    def go_background(self):
        sounds.play("window_hide")
        self.withdraw()  # окно пропадает и с экрана, и с панели задач

    def show_window(self):
        sounds.play("window_show")
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)  # на мгновение поверх всех окон, чтобы точно появиться
        self.after(100, lambda: self.attributes("-topmost", False))
        self.focus_force()

    def toggle_window(self):
        """Горячая клавиша: если лаунчер на виду и активен, прячем, иначе показываем."""
        if self.state() == "normal" and self.focus_displayof() is not None:
            self.go_background()
        else:
            self.show_window()

    def finish_launch(self):
        """Что делать с лаунчером после запуска программы (настройка after_launch)."""
        action = self.settings["after_launch"]
        if action == "close":
            self.quit_app()
        elif action == "background" and self.settings["background_mode"]:
            self.go_background()
        else:
            self.iconify()  # свернуть

    def on_close(self):
        """Крестик: в фоновом режиме прячемся, иначе выходим."""
        if self.settings["background_mode"]:
            self.go_background()
        else:
            self.quit_app()

    def on_any_click(self, event):
        """Звук нажатия на любую кнопку в дополнительных окнах (в главном у плиток и панели свои звуки)."""
        try:
            widget = event.widget
            if isinstance(widget, str) or widget.winfo_toplevel() is self:
                return
            late = 0
            try:
                late = (ctypes.windll.kernel32.GetTickCount() - event.time) & 0xFFFFFFFF
                if late > 300:   # обработчик кнопки ждал окно с вопросом: звук после него был бы запоздалым
                    return
            except (AttributeError, OSError):
                pass
            pressed_at = time.monotonic() - late / 1000
            while widget is not None:
                if isinstance(widget, ctk.CTkButton):
                    if str(widget.cget("state")) != "disabled":
                        self.after(70, lambda: sounds.auto_click(pressed_at))  # к этому моменту своё событие кнопки уже сыграло
                    return
                widget = getattr(widget, "master", None)
        except (tk.TclError, KeyError):
            pass

    def quit_app(self):
        if self.notes_window is not None and self.notes_window.winfo_exists():
            self.notes_window.save_now()  # не теряем то, что набрано в последние мгновения
        self.hotkey.stop()
        try:
            for job in self.tk.call("after", "info"):  # отложенные вызовы виджетов иначе падают после закрытия
                self.after_cancel(job)
        except tk.TclError:
            pass
        try:
            self.destroy()
        except tk.TclError:
            pass  # виджет уже разбирался
        try:
            self.quit()  # если destroy споткнулся, главный цикл иначе остался бы жить невидимым процессом
        except tk.TclError:
            pass

    # --- подсветка кнопок панели ---
    def light_button(self, button, on):
        try:
            if self.sidebar.winfo_exists():
                self.sidebar.set_button_active(button, on)
        except tk.TclError:
            pass  # программа закрывается, панели уже нет

    def track_open(self, window, button):
        """Кнопка горит, пока окно открыто (его создают и потом уничтожают)."""
        self.light_button(button, True)
        window.bind("<Destroy>", lambda e: e.widget is window and self.light_button(button, False), add="+")

    def track_visible(self, window, button):
        """Кнопка горит, пока окно показано на экране (его прячут и показывают заново)."""
        window.bind("<Map>", lambda e: e.widget is window and self.light_button(button, True), add="+")
        window.bind("<Unmap>", lambda e: e.widget is window and self.light_button(button, False), add="+")

    # --- заметки ---
    def open_notes(self):
        # если окно заметок уже открыто, не создаём второе, а выводим то же
        if self.notes_window is not None and self.notes_window.winfo_exists():
            self.notes_window.bring_to_front()
            return
        folder = self.settings.get("notes_dir") or default_dir()
        try:
            store = NoteStore(folder)
        except OSError as e:
            messagebox.showerror(tr("Заметки"), tr('Не удалось открыть папку заметок:\n{folder}\n\n{e}', folder=folder, e=e), parent=self)
            return
        # окно встаёт слева от кнопки заметок; если главное окно не на виду, по центру экрана
        anchor = None
        if self.winfo_viewable():
            btn = self.sidebar.notes_btn
            anchor = (btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height() // 2)
        sounds.play("notes_open")  # до создания окна: оно собирается заметное время
        self.notes_window = NotesWindow(self, store, self.set_notes_dir, anchor)
        self.track_open(self.notes_window, self.sidebar.notes_btn)

    def set_notes_dir(self, folder):
        self.settings["notes_dir"] = folder
        storage.save_settings(self.settings)

    def change_notes_dir(self, folder):
        """Папка заметок сменена в настройках (None = по умолчанию): запомнить и переключить открытое окно заметок."""
        try:
            store = NoteStore(folder or default_dir())
        except OSError as e:
            messagebox.showerror(tr("Заметки"), tr('Не удалось открыть папку заметок:\n{e}', e=e), parent=self)
            return False
        if folder is None:
            self.settings.pop("notes_dir", None)
            storage.save_settings(self.settings)
        else:
            self.set_notes_dir(store.folder)
        if self.notes_window is not None and self.notes_window.winfo_exists():
            self.notes_window.use_folder(store)
        return True

    def refresh_notes_window(self):
        """Размер шрифта, автосохранение и порядок заметок подхватываются открытым окном сразу."""
        if self.notes_window is not None and self.notes_window.winfo_exists():
            self.notes_window.apply_settings()

    # --- настройки ---
    def set_theme(self, name):
        """Запомнить выбранную тему (папку в themes). Включится после перезапуска."""
        self.settings["theme_name"] = name
        storage.save_settings(self.settings)

    def restart(self):
        """Запустить лаунчер заново и закрыть этот экземпляр (так включается выбранная тема)."""
        if getattr(sys, "frozen", False):
            args = [sys.executable]
        else:
            args = [sys.executable, os.path.abspath(sys.argv[0])]
        args += [a for a in sys.argv[1:] if a not in ("--restart", "--background")] + ["--restart"]
        env = {k: v for k, v in os.environ.items() if k not in ("TCL_LIBRARY", "TK_LIBRARY")}
        try:
            subprocess.Popen(args, env=env, close_fds=True)
        except OSError as e:
            messagebox.showerror(tr("Перезапуск"), tr('Не удалось перезапустить:\n{e}', e=e), parent=self)
            return
        self.withdraw()  # окно сразу пропадает, а закрываем чуть позже: нельзя ломать кнопку, чей обработчик ещё выполняется
        self.after(150, self.quit_app)

    def restore_windows(self):
        """После смены темы CustomTkinter на миг прячет окна, чтобы перекрасить заголовок, и дочернее окно
        (настройки, заметки) может остаться спрятанным. Возвращаем такие окна на место."""
        for window in (self.settings_window, self.notes_window):
            try:
                if window is not None and window.winfo_exists() and window.state() == "withdrawn":
                    window.deiconify()
                    window.lift()
            except tk.TclError:
                pass

    def open_settings(self):
        # если окно настроек уже открыто, не создаём второе, а выводим то же
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.deiconify()  # если окно спряталось, вернуть его
            self.settings_window.lift()
            self.settings_window.focus_force()
            return
        self.settings_window = SettingsWindow(self, self.settings, self.on_setting_changed)
        self.track_open(self.settings_window, self.sidebar.settings_btn)
        sounds.play("settings_open")
        window = self.settings_window
        window.bind("<Destroy>", lambda e: e.widget is window and sounds.play("settings_close"), add="+")

    def refresh_settings_window(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.refresh()

    def on_setting_changed(self, key, value):
        self.settings[key] = value
        storage.save_settings(self.settings)
        if key == "autostart":
            try:
                autostart.set_autostart(value)
            except OSError as e:
                messagebox.showerror(tr("Автозапуск"), str(e))
                self.settings["autostart"] = not value  # откатываем переключатель
                storage.save_settings(self.settings)
                self.refresh_settings_window()
        elif key in ("background_mode", "command_line", "hotkey_summon", "hotkey_command", "notes_hotkey", "hotkey_notes"):
            self.apply_hotkeys()
        elif key in ("columns", "max_tile_size", "tile_icon_size", "tile_label", "tile_show_key"):
            self.render()
        elif key in ("notes_font_size", "notes_autosave_ms", "notes_sort"):
            self.refresh_notes_window()
        elif key == "language":
            if messagebox.askyesno(
                    "Language / Язык / Мова",
                    "Restart now to apply the language?\nПерезапустить сейчас, чтобы применить язык?\n"
                    "Перезапустити зараз, щоб застосувати мову?",
                    parent=self.settings_window or self):
                # не сразу: окно настроек ещё дорабатывает это нажатие и не должно оказаться уже уничтоженным
                self.after(150, self.restart)
        elif key == "theme_mode":
            ctk.set_appearance_mode(value)  # меняется сразу, без перезапуска
            for delay in (150, 400, 900):  # CustomTkinter на миг прячет окна: возвращаем спрятанные
                self.after(delay, self.restore_windows)
        elif key in SIDEBAR_BUTTONS:
            self.sidebar.set_button_visible(SIDEBAR_BUTTONS[key], value)
            self.sidebar_index = min(self.sidebar_index, len(self.sidebar.buttons) - 1)
            if self.zone == "sidebar":
                self.sidebar.select(self.sidebar_index)
        elif key == "sidebar_width":
            self.sidebar.configure(width=value)
            self.render()