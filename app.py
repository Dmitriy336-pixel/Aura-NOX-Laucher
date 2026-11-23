# app.py
"""Главное окно на PySide6: собирает части вместе и решает, что делать при действиях.

Совместимость с остальным кодом (команды, path_nav и т.п. писались под tkinter):
  app.after(ms, fn)                 -> QTimer.singleShot
  app.clipboard_clear/append(text)  -> буфер обмена Qt
Окна настроек и заметок подключаются лениво (импорт внутри методов): пока они не перенесены, остальное работает."""
import os
import subprocess
import sys
import time

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (QAbstractButton, QApplication, QFileDialog, QHBoxLayout, QMainWindow,
                               QMenu, QVBoxLayout, QWidget)
from shiboken6 import isValid

import autostart
import dialogs
import icon_tools
import launchers
import powerplan
import sounds
import storage
import theme
import tile_icons
from builtin_commands import build_registry
from color_picker import ColorPicker
from config import APP_NAME, QUICK_KEYS
from tile_keys import assign_key, redistribute
from hotkey import HotkeyListener
from i18n import tr
from notes_store import NoteStore, default_dir
from sidebar import Sidebar
from tile_grid import TileGrid, special_count

# какая настройка какую кнопку правой панели показывает
SIDEBAR_BUTTONS = {"show_notes_btn": "notes", "show_lock_btn": "lock", "show_perf_btn": "perf"}

KEY_LEFT, KEY_UP, KEY_RIGHT, KEY_DOWN = (Qt.Key.Key_Left, Qt.Key.Key_Up, Qt.Key.Key_Right, Qt.Key.Key_Down)


def alive(widget):
    """Окно существует (не None и не уничтожено на стороне Qt)."""
    return widget is not None and isValid(widget)


def palette():
    """Цвета плиток по кругу берутся из текущей темы."""
    return theme.CURRENT_TILE_COLORS


class ClickSounds(QObject):
    """Звук нажатия на любую кнопку в дополнительных окнах (в главном у плиток и панели свои звуки)."""

    def __init__(self, main):
        super().__init__(main)
        self.main = main

    def eventFilter(self, obj, event):
        if (event.type() == QEvent.Type.MouseButtonPress and isinstance(obj, QAbstractButton)
                and event.button() == Qt.MouseButton.LeftButton and obj.isEnabled()):
            try:
                if obj.window() is not self.main:
                    pressed_at = time.monotonic()
                    # к этому моменту своё событие кнопки уже сыграло
                    QTimer.singleShot(70, lambda: sounds.auto_click(pressed_at))
            except RuntimeError:
                pass
        return False


class App(QMainWindow):
    hotkey_signal = Signal(str)   # горячая клавиша приходит из другого потока: сигнал переносит вызов в главный
    show_requested = Signal()     # то же для сигнала от второго экземпляра

    def __init__(self, settings=None, start_hidden=False):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.settings = settings if settings is not None else storage.load_settings()
        sounds.init(self.settings)  # тот же словарь: переключатель и громкость действуют сразу
        qapp = QApplication.instance()
        qapp.setQuitOnLastWindowClosed(False)  # в фоновом режиме главное окно спрятано, а процесс живёт
        self._click_sounds = ClickSounds(self)
        qapp.installEventFilter(self._click_sounds)

        screen = QApplication.primaryScreen().geometry()
        sw, sh = screen.width(), screen.height()
        scale = min(100, max(40, self.settings["window_scale"])) / 100
        self.win_w, win_h = int(sw * scale), int(sh * scale)
        self.resize(self.win_w, win_h)
        self.move(screen.x() + (sw - self.win_w) // 2, screen.y() + (sh - win_h) // 2)
        self.setMinimumSize(400, 300)

        self.tiles = storage.load_tiles()
        changed = False
        for i, tile in enumerate(self.tiles):  # выдаём быстрые клавиши и цвета плиткам, у которых их ещё нет
            if tile.get("key") is None:  # "" значит, что клавишу убрали намеренно
                tile["key"] = self.free_key()
                changed = True
            if not tile.get("color"):  # цвет хранится у плитки, поэтому при перетаскивании она его не теряет
                tile["color"] = palette()[i % len(palette())]
                changed = True
        if changed:
            storage.save_tiles(self.tiles)

        self.selected = 0       # позиция выбранной плитки: 0 = "+", 1 = поиск (если не объединён с «+»), дальше плитки
        self.zone = "grid"      # где рамка выбора: "grid" (плитки) или "sidebar" (правая панель)
        self.sidebar_index = 0  # выбранная кнопка на панели
        self.settings_window = None
        self.notes_window = None
        self.command_bar = None  # сама панель создаётся при первом вызове

        self.resize_timer = QTimer(self)
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.render)
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(self.render)

        # поток горячих клавиш зовёт нас из другого потока: сигнал доставит вызов в главный
        self.hotkey_signal.connect(self.on_hotkey)
        self.show_requested.connect(self.show_window)
        self.hotkey = HotkeyListener(lambda name: self.hotkey_signal.emit(name))
        self.registry = build_registry(self)  # команды командной строки

        # две колонки: сетка плиток | узкая правая панель
        central = QWidget()
        self.setCentralWidget(central)
        row = QHBoxLayout(central)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        self.sidebar = Sidebar(
            central, on_settings=self.open_settings, on_command=self.toggle_command_bar,
            on_perf=self.toggle_performance, on_notes=self.open_notes, on_lock=self.toggle_tile_lock,
            width=self.settings["sidebar_width"],
        )
        self.sidebar.set_lock_active(self.tiles_locked())
        for setting, name in SIDEBAR_BUTTONS.items():  # какие кнопки панели показывать
            self.sidebar.set_button_visible(name, self.settings[setting])
        self.sidebar.set_perf_active(self.performance_is_on())  # кнопка сразу показывает текущее состояние

        self.tile_grid = TileGrid(
            None, on_add=self.add_tile, on_run=self.run_tile, on_menu=self.show_menu,
            on_move=self.move_tile, can_drag=lambda: not self.tiles_locked(), on_search=self.search_tile,
        )
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(self.tile_grid)
        row.addWidget(left, 1)
        row.addWidget(self.sidebar)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.render()
        self.apply_hotkeys()
        if start_hidden and self.settings["background_mode"]:
            self.hide()
        else:
            self.show()
            self.setFocus()

    # --- совместимость с кодом, написанным под tkinter ---
    def after(self, ms, fn):
        QTimer.singleShot(ms, fn)

    def clipboard_clear(self):
        QApplication.clipboard().clear()

    def clipboard_append(self, text):
        QApplication.clipboard().setText(text)

    # --- отрисовка и изменение размера ---
    def render(self):
        self.selected = max(0, min(self.selected, self.last_pos()))  # служебных плиток могло стать меньше/больше
        grid_width = self.win_w - self.settings["sidebar_width"]
        selected = self.selected if self.zone == "grid" else None  # рамка только в активной зоне
        self.tile_grid.render(self.tiles, grid_width, selected, self.settings)

    def render_later(self):
        """Перерисовывает плитки не сразу, а когда правки прекратятся: серия правок даёт одну перерисовку."""
        self.render_timer.start(800)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.width() == self.win_w:
            return
        self.win_w = self.width()
        self.resize_timer.start(80)  # перерисовываем, когда перестали тянуть

    # --- плитки ---
    def new_tile(self, name, path):
        tile = {"type": "app", "name": name, "target": path, "key": self.free_key(),
                "color": self.settings.get("tile_fill_color") or palette()[len(self.tiles) % len(palette())]}
        if self.settings.get("auto_icons", True):
            icon = icon_tools.auto_icon(tile)  # из папки готовых иконок или из самой программы
            if icon:
                tile["icon"] = icon
        self.tiles.append(tile)
        storage.save_tiles(self.tiles)
        sounds.play("tile_add")
        return tile

    def specials(self):
        """Число служебных плиток: «+» и (если поиск не объединён с «+») плитка поиска."""
        return special_count(self.settings)

    def last_pos(self):
        """Позиция последней плитки: служебные плитки идут первыми, потом обычные."""
        return len(self.tiles) + self.specials() - 1

    def add_tile(self):
        """«+»: выбор файла или, если так выбрано в настройках (add_tile_mode), окно поиска программ."""
        if self.settings.get("add_tile_mode", "file") == "search":
            self.search_tile()
            return
        from add_program import pick_program_file
        path = pick_program_file(self)
        self.add_chosen([(os.path.splitext(os.path.basename(path))[0], path)] if path else [])

    def search_tile(self):
        """Плитка с лупой: окно поиска по установленным программам (там же есть «Обзор…»)."""
        from add_program import AddProgramDialog
        dialog = AddProgramDialog(self, [t.get("target") for t in self.tiles])
        self.add_chosen(dialog.chosen if dialog.exec() else [])

    def add_chosen(self, chosen):
        """Плитки для выбранных программ [(название, путь)]; выбор встаёт на последнюю добавленную."""
        if not chosen:
            return
        for name, path in chosen:
            self.new_tile(name, os.path.normpath(path))
        self.selected = self.last_pos()
        self.render()

    def add_tile_path(self, path):
        """Плитка для готового пути (из командной строки). Возвращает название плитки."""
        clean = path.rstrip("\\/")
        name = os.path.basename(clean) if os.path.isdir(path) else os.path.splitext(os.path.basename(clean))[0]
        tile = self.new_tile(name or path, path)
        self.render()
        return tile["name"]

    def run_tile(self, tile):
        sounds.play("launch")  # сразу при нажатии, а не после запуска
        try:
            launchers.launch(tile)
        except OSError as e:
            dialogs.error(self, tr("Не удалось запустить"), str(e))
        except KeyError:
            dialogs.error(self, tr("Не удалось запустить"),
                          tr('Неизвестный тип плитки: {v}', v=tile.get('type')))
        else:
            self.finish_launch()

    def delete_tile(self, index):
        if self.settings.get("confirm_delete", True) and not dialogs.ask(
                self, tr("Удалить плитку"), tr('Удалить плитку «{name}»?', name=self.tiles[index]['name'])):
            return
        icon = self.tiles[index].get("icon")
        del self.tiles[index]
        sounds.play("tile_delete")
        tile_icons.remove_if_unused(icon, self.tiles)  # файл иконки больше не нужен
        storage.save_tiles(self.tiles)
        self.selected = min(self.selected, self.last_pos())
        self.render()

    def change_icon(self, index):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Выбери картинку для плитки"), "",
            f"{tr('Картинки')} (*.png *.jpg *.jpeg *.ico *.bmp *.gif *.webp);;{tr('Все файлы')} (*.*)")
        if not path:
            return
        try:
            name = tile_icons.import_icon(path)
        except OSError as e:
            dialogs.error(self, tr("Не удалось открыть картинку"), str(e))
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
        self.selected = dst + self.specials()  # выбор остаётся на перенесённой плитке
        self.render()

    def on_ctrl_arrow(self, dx, dy):
        """Ctrl+стрелки: передвинуть выбранную плитку на соседнее место."""
        if self.zone == "grid" and self.selected >= self.specials() and not self.tiles_locked():
            src = self.selected - self.specials()
            dst = src + dx + dy * self.settings["columns"]
            if 0 <= dst < len(self.tiles):
                self.move_tile(src, dst)

    # --- автоматические иконки ---
    def auto_icon_for(self, index):
        """Подобрать иконку одной плитке (пункт меню). Прежняя иконка заменяется."""
        tile = self.tiles[index]
        name = icon_tools.auto_icon(tile)
        if name is None:
            dialogs.info(self, tr("Иконка"),
                         tr("Подходящей иконки нет ни в папке готовых иконок, ни в самой программе."))
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
        picker = ColorPicker(self, tile["name"], tile.get("color"), lambda color: self.set_tile_color(index, color))
        picker.open()

    def set_tile_color(self, index, color):
        self.tiles[index]["color"] = color
        storage.save_tiles(self.tiles)
        self.render()

    def recolor_tiles(self, color=None):
        """Перекрасить все плитки: одним цветом или палитрой по порядку (color=None)."""
        for i, tile in enumerate(self.tiles):
            tile["color"] = color or palette()[i % len(palette())]
        storage.save_tiles(self.tiles)
        # «один цвет для всех» запоминаем: новые плитки получают его, а не цвет из палитры темы
        self.settings["tile_fill_color"] = color
        storage.save_settings(self.settings)
        self.render()

    def restart_with_theme(self):
        """Перезапуск для новой темы; если тема сменилась, спрашиваем про перекраску плиток под её палитру."""
        name = self.settings.get("theme_name", "default")
        if self.tiles and name != theme.current_name() and dialogs.ask(
                self.settings_window if alive(self.settings_window) else self, tr("Новая тема"),
                tr("Перекрасить все плитки цветами из новой темы?\nЕсли «Нет», плитки останутся как есть.")):
            colors = theme.load(name)[2]
            for i, tile in enumerate(self.tiles):
                tile["color"] = colors[i % len(colors)]
            storage.save_tiles(self.tiles)
            self.settings["tile_fill_color"] = None  # теперь цвета снова по палитре (новой) темы
            storage.save_settings(self.settings)
        self.restart()

    # --- клавиатура ---
    def event(self, e):
        # Tab Qt по умолчанию отдаёт на перебор виджетов; нам он нужен для переноса рамки выбора
        if e.type() == QEvent.Type.KeyPress and e.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            self.on_tab()
            return True
        return super().event(e)

    def keyPressEvent(self, event):
        key = event.key()
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        # код физической клавиши (Windows: VK): цифры 48-57, буквы 65-90, не зависит от раскладки
        code = event.nativeVirtualKey() or key
        arrows = {KEY_LEFT: (-1, 0), KEY_RIGHT: (1, 0), KEY_UP: (0, -1), KEY_DOWN: (0, 1)}
        if ctrl:
            if key in arrows:
                self.on_ctrl_arrow(*arrows[key])
            elif code == 81:  # Q
                self.quit_app()
            return
        if key in arrows:
            self.on_arrow(*arrows[key])
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.activate_selected()
        elif key == Qt.Key.Key_Delete:
            self.open_delete_menu()
        elif key == Qt.Key.Key_F2:
            self.open_settings()
        elif 48 <= code <= 57 or 65 <= code <= 90:
            char = chr(code).lower()
            for tile in self.tiles:
                if tile.get("key") == char:
                    self.run_tile(tile)
                    return
        else:
            super().keyPressEvent(event)

    def move_selection(self, delta):
        new = max(0, min(self.last_pos(), self.selected + delta))  # позиции: 0 = "+", 1 = поиск, дальше плитки
        if new != self.selected:
            sounds.play("select")
        self.selected = new
        self.tile_grid.select(self.selected)

    def on_tab(self):
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

    def on_arrow(self, dx, dy):
        """Стрелки: в сетке двигают выбор по плиткам, на панели ходят вверх и вниз."""
        if self.zone == "grid":
            self.move_selection(dx + dy * self.settings["columns"])
        elif dx < 0:       # на панели стрелка влево возвращает к плиткам
            self.on_tab()
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
        elif self.selected == 1 and self.specials() > 1:
            self.search_tile()
        else:
            self.run_tile(self.tiles[self.selected - self.specials()])

    def free_key(self):
        """Первая клавиша из QUICK_KEYS, которую ещё не занимает ни одна плитка."""
        used = {tile.get("key") for tile in self.tiles}
        for key in QUICK_KEYS:
            if key not in used:
                return key
        return None

    # --- меню плитки ---
    def show_menu(self, pos, index):
        self.open_menu(pos.x(), pos.y(), index)

    def open_delete_menu(self):
        if self.zone != "grid" or self.selected < self.specials():
            return  # меню только у плиток, у служебных плиток и у панели его нет
        btn = self.tile_grid.buttons[self.selected]
        center = btn.mapToGlobal(QPoint(btn.width() // 2, btn.size_px // 2))
        self.open_menu(center.x(), center.y(), self.selected - self.specials())

    def open_menu(self, x, y, index):
        menu = QMenu(self)
        # «Удалить» первым: привычное Delete, вниз, Enter по-прежнему удаляет плитку
        menu.addAction(tr("Удалить"), lambda: self.delete_tile(index))
        menu.addAction(tr("Цвет…"), lambda: self.pick_color(index))
        if self.tiles[index].get("target"):
            menu.addAction(tr("Подобрать иконку"), lambda: self.auto_icon_for(index))
        menu.addAction(tr("Сменить иконку…"), lambda: self.change_icon(index))
        if self.tiles[index].get("icon"):
            menu.addAction(tr("Убрать иконку"), lambda: self.clear_icon(index))
        sounds.play("menu_open")  # до показа: exec ждёт закрытия меню
        menu.exec(QPoint(x, y))

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

        title = tr("Горячая клавиша")
        if "summon" in failed:
            # без горячей клавиши из фона не вернуться, поэтому режим не включаем
            dialogs.warning(self, title, tr(
                'Не удалось занять {hotkey_summon}: комбинацию уже использует другая программа.',
                hotkey_summon=self.settings['hotkey_summon']))
            self.settings["background_mode"] = False
        if "command" in failed:
            dialogs.warning(self, title, tr(
                'Не удалось занять {hotkey_command}: комбинацию уже использует другая программа.',
                hotkey_command=self.settings['hotkey_command']))
            self.settings["command_line"] = False
        if "notes" in failed:
            dialogs.warning(self, title, tr(
                'Не удалось занять {hotkey_notes}: комбинацию уже использует другая программа.',
                hotkey_notes=self.settings['hotkey_notes']))
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
        from command_bar import CommandBar
        if self.command_bar is None:
            self.command_bar = CommandBar(self.registry)
            self.command_bar.apply_blur_settings(self.settings)
            self.command_bar.visibility_changed.connect(
                lambda shown: self.light_button(self.sidebar.command_btn, shown))
        if self.command_bar.isVisible():
            self.command_bar.close_bar()
        else:
            sounds.play("command")
            self.command_bar.open_bar()

    def reload_commands(self):
        """Пересобрать список команд (после изменения своих команд в настройках)."""
        self.registry = build_registry(self)
        if self.command_bar is not None:
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
                dialogs.warning(self, tr("Режим производительности"), message)
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
            self.showMinimized()

    def go_background(self):
        sounds.play("window_hide")
        self.hide()  # окно пропадает и с экрана, и с панели задач

    def show_window(self):
        sounds.play("window_show")
        self.setWindowState((self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def show_window_from_signal(self):
        """Зовётся из потока второго экземпляра (single_instance.listen): сигнал перенесёт вызов в главный поток."""
        self.show_requested.emit()

    def toggle_window(self):
        """Горячая клавиша: если лаунчер на виду и активен, прячем, иначе показываем."""
        if self.isVisible() and not self.isMinimized() and self.isActiveWindow():
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
            self.showMinimized()

    def closeEvent(self, event):
        """Крестик: в фоновом режиме прячемся, иначе выходим."""
        if self.settings["background_mode"]:
            event.ignore()
            self.go_background()
        else:
            event.accept()
            self.quit_app()

    def quit_app(self):
        if alive(self.notes_window):
            self.notes_window.save_now()  # не теряем то, что набрано в последние мгновения
        self.hotkey.stop()
        if alive(self.command_bar):
            self.command_bar.hide()
        QApplication.instance().quit()

    # --- подсветка кнопок панели ---
    def light_button(self, button, on):
        try:
            self.sidebar.set_button_active(button, on)
        except RuntimeError:
            pass  # программа закрывается, панели уже нет

    def track_open(self, window, button):
        """Кнопка горит, пока окно открыто (его создают и потом уничтожают)."""
        self.light_button(button, True)
        window.destroyed.connect(lambda *_: self.light_button(button, False))

    # --- заметки ---
    def open_notes(self):
        from notes_window import NotesWindow
        # если окно заметок уже открыто, не создаём второе, а выводим то же
        if alive(self.notes_window):
            self.notes_window.bring_to_front()
            return
        folder = self.settings.get("notes_dir") or default_dir()
        try:
            store = NoteStore(folder)
        except OSError as e:
            dialogs.error(self, tr("Заметки"), tr('Не удалось открыть папку заметок:\n{folder}\n\n{e}', folder=folder, e=e))
            return
        # окно встаёт слева от кнопки заметок; если главное окно не на виду, по центру экрана
        anchor = None
        if self.isVisible() and not self.isMinimized():
            btn = self.sidebar.notes_btn
            point = btn.mapToGlobal(QPoint(0, btn.height() // 2))
            anchor = (point.x(), point.y())
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
            dialogs.error(self, tr("Заметки"), tr('Не удалось открыть папку заметок:\n{e}', e=e))
            return False
        if folder is None:
            self.settings.pop("notes_dir", None)
            storage.save_settings(self.settings)
        else:
            self.set_notes_dir(store.folder)
        if alive(self.notes_window):
            self.notes_window.use_folder(store)
        return True

    def refresh_notes_window(self):
        """Размер шрифта, автосохранение и порядок заметок подхватываются открытым окном сразу."""
        if alive(self.notes_window):
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
            dialogs.error(self, tr("Перезапуск"), tr('Не удалось перезапустить:\n{e}', e=e))
            return
        self.hide()  # окно сразу пропадает, а закрываем чуть позже: обработчик кнопки ещё выполняется
        QTimer.singleShot(150, self.quit_app)

    def open_settings(self):
        from settings_window import SettingsWindow
        # если окно настроек уже открыто, не создаём второе, а выводим то же
        if alive(self.settings_window):
            self.settings_window.show()
            self.settings_window.raise_()
            self.settings_window.activateWindow()
            return
        self.settings_window = SettingsWindow(self, self.settings, self.on_setting_changed)
        self.settings_window.show()  # окно не модальное и само не появляется: без show() оно открывалось только со второго нажатия
        self.track_open(self.settings_window, self.sidebar.settings_btn)
        sounds.play("settings_open")
        self.settings_window.destroyed.connect(lambda *_: sounds.play("settings_close"))

    def refresh_settings_window(self):
        if alive(self.settings_window):
            self.settings_window.refresh()

    def on_setting_changed(self, key, value):
        self.settings[key] = value
        storage.save_settings(self.settings)
        if key == "autostart":
            try:
                autostart.set_autostart(value)
            except OSError as e:
                dialogs.error(self, tr("Автозапуск"), str(e))
                self.settings["autostart"] = not value  # откатываем переключатель
                storage.save_settings(self.settings)
                self.refresh_settings_window()
        elif key in ("background_mode", "command_line", "hotkey_summon", "hotkey_command",
                     "notes_hotkey", "hotkey_notes"):
            self.apply_hotkeys()
        elif key in ("command_blur", "command_blur_strength", "command_blur_dim", "command_blur_fade"):
            if self.command_bar is not None:
                self.command_bar.apply_blur_settings(self.settings)
        elif key in ("columns", "max_tile_size", "tile_icon_size", "tile_label", "tile_show_key"):
            self.render()
        elif key == "add_tile_mode":
            # плитка поиска появляется/пропадает: номера позиций сдвигаются, выбор держим на той же плитке
            old = special_count({"add_tile_mode": "file" if value == "search" else "search"})
            if self.selected >= old:
                self.selected += self.specials() - old
            else:
                self.selected = min(self.selected, self.specials() - 1)
            self.render()
        elif key in ("notes_font_size", "notes_autosave_ms", "notes_sort"):
            self.refresh_notes_window()
        elif key == "language":
            if dialogs.ask(
                    self.settings_window if alive(self.settings_window) else self,
                    "Language / Язык / Мова",
                    "Restart now to apply the language?\nПерезапустить сейчас, чтобы применить язык?\n"
                    "Перезапустити зараз, щоб застосувати мову?"):
                # не сразу: окно настроек ещё дорабатывает это нажатие и не должно оказаться уже уничтоженным
                QTimer.singleShot(150, self.restart)
        elif key == "theme_mode":
            theme.apply(mode=value)  # QSS пересобирается и применяется сразу, без перезапуска
            self.render()
            self.sidebar.apply_textures()
            if self.zone == "sidebar":
                self.sidebar.select(self.sidebar_index)
            self.refresh_settings_window()
        elif key in SIDEBAR_BUTTONS:
            self.sidebar.set_button_visible(SIDEBAR_BUTTONS[key], value)
            self.sidebar_index = min(self.sidebar_index, len(self.sidebar.buttons) - 1)
            if self.zone == "sidebar":
                self.sidebar.select(self.sidebar_index)
        elif key == "sidebar_width":
            self.sidebar.set_width(value)
            self.render()
