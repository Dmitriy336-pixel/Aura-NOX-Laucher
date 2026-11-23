"""Командная строка на PySide6: тонкая панель без рамки с полем ввода у нижнего края экрана.
Над полем появляются подсказки (пока печатаешь), список команд и ответы.
Окно верхнего уровня без родителя: оно должно открываться горячей клавишей, даже когда лаунчер свёрнут или спрятан."""
from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QCursor, QFont
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget)

import i18n
import sounds
import storage
import theme
import winapi
from commands import Paged, Reply
from screen_blur import DEFAULTS as BLUR_DEFAULTS, BlurBackdrop
from sidebar import SideButton
from config import HISTORY_FILE, SCREENSHOT_DELAY_MS
from i18n import tr

HINT = tr("Введи команду. «помощь» — список команд")
FOOTER = tr("Tab — подставить   ·   Up Arrow | Down Arrow — выбрать   ·   Enter — выполнить")
MAX_SUGGESTIONS = 6
MAX_ARG_ITEMS = 8   # сколько подсказок по аргументам показывать сразу
BAR_MARGIN = 12     # зазор между строкой и панелью задач, px
BTN_SIZE = 34       # кнопки справа от поля ввода, высота как у поля
SHOT_TIP = tr("Снимок экрана")  # подпись при наведении, как у плиток
KEYBOARD_TIP = tr("Экранная клавиатура")
KEYBOARD_POLLS = 20  # сколько раз (раз в 100 мс) ждать окно клавиатуры, чтобы поднять строку над ним


def font_px(px, bold=False):
    font = QFont()
    font.setPixelSize(px)
    font.setBold(bold)
    return font


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()


class InfoPanel(QFrame):
    """Панель над строкой: заголовок, строки с разделителями и подпись внизу."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("cmdinfo")
        self.wrap = 500  # перенос длинных строк, px
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(0, 4, 0, 4)
        self.box.setSpacing(0)
        self.apply_colors()

    def apply_colors(self):
        self.setStyleSheet(
            f"#cmdinfo {{ background-color: {theme.color('cmd_panel_bg')}; border-radius: 10px; }}")

    def clear(self):
        self.apply_colors()
        clear_layout(self.box)

    def label(self, text, color, size, bold=False, wrap=False):
        label = QLabel(text)
        label.setFont(font_px(size, bold))
        label.setStyleSheet(f"color: {color};")
        label.setWordWrap(wrap)
        return label

    def header(self, text):
        label = self.label(text.upper(), theme.color("text_dim"), 11, bold=True)
        label.setContentsMargins(14, 6, 14, 2)
        self.box.addWidget(label)

    def divider(self):
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {theme.color('cmd_line')}; margin: 0px 12px;")
        self.box.addWidget(line)

    def row(self, names, description, selected=False, matched=None):
        """Строка команды: название, остальные варианты написания, описание."""
        main = matched or names[0]
        if matched is None and i18n.language() != "ru":
            main = next((n for n in names if n.isascii()), main)  # английский интерфейс: английское имя первым
        aliases = ", ".join(n for n in names if n != main)
        frame = QFrame()
        frame.setObjectName("cmdrow")
        bg = theme.color("select_bg") if selected else "transparent"
        frame.setStyleSheet(f"#cmdrow {{ background-color: {bg}; border-radius: 6px; }}")
        row = QHBoxLayout(frame)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(6)
        name = self.label(main, theme.color("accent"), 14, bold=True)
        name.setMinimumWidth(100)
        row.addWidget(name)
        if aliases:
            alias = self.label(aliases, theme.color("text_dim"), 12)
            alias.setMinimumWidth(90)
            row.addWidget(alias)
        desc = self.label(description, theme.color("text_dim"), 13, wrap=True)
        desc.setMaximumWidth(self.wrap)
        row.addWidget(desc, 1)
        wrapper = QWidget()
        wrapper_layout = QHBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(6, 1, 6, 1)
        wrapper_layout.addWidget(frame)
        wrapper.setStyleSheet("background: transparent;")
        self.box.addWidget(wrapper)

    def message(self, text, error=False):
        label = self.label(text, theme.color("error") if error else theme.color("text_dim"), 13, wrap=True)
        label.setContentsMargins(14, 8, 14, 8)
        self.box.addWidget(label)

    def footer(self, text):
        label = self.label(text, theme.color("text_dim"), 11)
        label.setContentsMargins(14, 3, 14, 7)
        self.box.addWidget(label)


class BarEntry(QLineEdit):
    """Поле ввода: Tab, стрелки и PgUp/PgDn нужны панели, а не стандартному поведению поля."""

    def __init__(self, bar):
        super().__init__()
        self.bar = bar

    def event(self, e):
        if e.type() == QEvent.Type.KeyPress and e.key() == Qt.Key.Key_Tab:
            self.bar.complete()
            return True
        return super().event(e)

    def keyPressEvent(self, e):
        key = e.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.bar.run()
        elif key == Qt.Key.Key_Up:
            self.bar.move_sel(-1)
        elif key == Qt.Key.Key_Down:
            self.bar.move_sel(1)
        elif key == Qt.Key.Key_PageUp:
            self.bar.turn_page(-1)
        elif key == Qt.Key.Key_PageDown:
            self.bar.turn_page(1)
        elif key == Qt.Key.Key_Escape:
            self.bar.escape()
        else:
            if e.text() and e.text().isprintable():
                sounds.play("type")
            super().keyPressEvent(e)


class CommandBar(QWidget):
    visibility_changed = Signal(bool)  # панель показана или спрятана (кнопка на боковой панели горит, пока она открыта)

    def __init__(self, registry):
        super().__init__(None)
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
        self.w = self.x0 = self.bottom = 0
        self.blur_enabled = True  # размывать экран под строкой (настройка command_blur)
        self.blur_strength = BLUR_DEFAULTS["strength"]  # сила размытия, %
        self.blur_dim = BLUR_DEFAULTS["dim"]            # затемнение фона, %
        self.blur_fade = BLUR_DEFAULTS["fade_ms"]       # время появления фона, мс
        self.backdrop = None      # окно с размытым снимком экрана, создаётся при первом открытии
        self.home_bottom = 0      # нижний край строки без экранной клавиатуры (её появление поднимает строку)
        self.skin_key = None      # (тема, режим), для которых оформлены кнопки справа от поля

        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)  # прозрачные углы вокруг скруглённой панели

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # скруглённая тонкая рамка вокруг всего содержимого
        self.box = QFrame()
        self.box.setObjectName("cmdbox")
        outer.addWidget(self.box)
        self.box_layout = QVBoxLayout(self.box)
        self.box_layout.setContentsMargins(8, 8, 8, 7)
        self.box_layout.setSpacing(6)

        self.info = InfoPanel()
        self.entry = BarEntry(self)
        self.entry.setFixedHeight(34)
        self.entry.setFont(font_px(15))
        self.entry.textChanged.connect(self.on_text)
        self.shot_btn = SideButton("✂", 17, size=BTN_SIZE)
        self.kbd_btn = SideButton("⌨", 19, size=BTN_SIZE)
        self.shot_btn.setToolTip(SHOT_TIP)
        self.kbd_btn.setToolTip(KEYBOARD_TIP)
        self.shot_btn.clicked.connect(self.screenshot)
        self.kbd_btn.clicked.connect(self.show_keyboard)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.entry, 1)
        row.addWidget(self.shot_btn)
        row.addWidget(self.kbd_btn)
        self.box_layout.addWidget(self.info)
        self.box_layout.addLayout(row)
        self.apply_colors()

    def apply_colors(self):
        self.box.setStyleSheet(
            f"#cmdbox {{ background-color: {theme.color('cmd_box_bg')}; border: 1px solid {theme.color('cmd_line')};"
            f" border-radius: 14px; }}")
        self.apply_button_skins()

    # --- открыть и закрыть ---
    def open_bar(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        area = screen.availableGeometry()  # без панели задач: строка встаёт прямо над ней
        self.w = max(580, min(800, int(area.width() * 0.35) + 25))
        self.x0 = area.x() + (area.width() - self.w) // 2
        self.bottom = area.y() + area.height() - BAR_MARGIN
        self.home_bottom = self.bottom
        self.info.wrap = self.w - 360
        self.apply_colors()
        self.set_text("")
        self.paged = None
        self.suggestions = []
        self.arg_items = []
        self.hist_pos = None
        self.show_message(HINT)
        self.show_backdrop(screen)  # до show(): иначе сама строка попадёт на снимок экрана
        self.show()
        self.raise_()
        self.activateWindow()
        self.entry.setFocus()
        QTimer.singleShot(0, self.entry.setFocus)

    def apply_blur_settings(self, settings):
        self.blur_enabled = settings.get("command_blur", True)
        self.blur_strength = settings.get("command_blur_strength", BLUR_DEFAULTS["strength"])
        self.blur_dim = settings.get("command_blur_dim", BLUR_DEFAULTS["dim"])
        self.blur_fade = settings.get("command_blur_fade", BLUR_DEFAULTS["fade_ms"])

    def show_backdrop(self, screen):
        if not self.blur_enabled:
            return
        if self.backdrop is None:
            self.backdrop = BlurBackdrop()
            self.backdrop.clicked.connect(self.close_bar)  # клик мимо строки закрывает её
        self.backdrop.show_over(screen, self.blur_strength, self.blur_dim, self.blur_fade)

    # --- кнопки справа от поля ---
    def apply_button_skins(self):
        """Оформление кнопок из темы (как у кнопок боковой панели); заново только при смене темы или режима."""
        key = (theme.current_name(), theme.current_mode())
        if key == self.skin_key:
            return
        self.skin_key = key
        self.shot_btn.apply_texture("screenshot")
        self.kbd_btn.apply_texture("keyboard")

    def screenshot(self):
        """Спрятать строку вместе с размытием и запустить вырезку экрана (Win+Shift+S).
        Пауза нужна, чтобы размытие успело пропасть и не попало на снимок."""
        self.close_bar()
        QTimer.singleShot(SCREENSHOT_DELAY_MS, lambda: winapi.send_combo("win", "shift", "s"))

    def show_keyboard(self):
        """Показать экранную клавиатуру Windows. Строка остаётся открытой и поднимается над клавиатурой."""
        winapi.open_keyboard()
        self.poll_keyboard(KEYBOARD_POLLS)

    def poll_keyboard(self, tries):
        if not self.isVisible():
            return
        gap = winapi.window_top_gap(winapi.KEYBOARD_CLASS)  # физические px от верха клавиатуры до низа монитора
        if gap is not None:
            screen = self.screen()
            edge = screen.geometry().y() + screen.geometry().height()
            self.bottom = min(self.home_bottom, edge - round(gap / screen.devicePixelRatio()) - BAR_MARGIN)
            self.fit()
            self.raise_()
            self.activateWindow()
            self.entry.setFocus()
        elif tries > 0:
            QTimer.singleShot(100, lambda: self.poll_keyboard(tries - 1))

    def escape(self):
        sounds.play("command_close")
        self.close_bar()

    def close_bar(self):
        self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.visibility_changed.emit(True)

    def hideEvent(self, event):
        super().hideEvent(event)
        if self.backdrop is not None:
            self.backdrop.hide_backdrop()
        self.visibility_changed.emit(False)

    def event(self, e):
        if e.type() == QEvent.Type.WindowDeactivate:
            QTimer.singleShot(150, self.close_if_unfocused)
        return super().event(e)

    def close_if_unfocused(self):
        if self.isVisible() and not self.isActiveWindow():
            if winapi.foreground_class() == winapi.KEYBOARD_CLASS:  # фокус ушёл на экранную клавиатуру: возвращаем строке
                self.activateWindow()
                self.entry.setFocus()
                return
            self.close_bar()

    # --- размер и положение ---
    def present(self):
        self.fit()
        QTimer.singleShot(0, self.fit)  # второй проход, когда Qt уже посчитал переносы строк

    def fit(self):
        """Подгоняем высоту под содержимое, нижний край (поле ввода) остаётся на месте.
        Высота считается для заданной ширины: строки с переносом иначе сжимаются."""
        self.setFixedWidth(self.w)
        lay = self.layout()
        self.box_layout.activate()
        lay.activate()
        height = lay.totalHeightForWidth(self.w) if lay.hasHeightForWidth() else lay.sizeHint().height()
        height = max(height, lay.totalMinimumSize().height())
        self.setFixedHeight(height)
        self.move(self.x0, self.bottom - height)

    def set_text(self, text):
        self.quiet = True
        self.entry.setText(text)
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
        raw = self.entry.text()
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

    def move_sel(self, step):
        if self.hist_pos is not None or (not self.arg_items and not self.suggestions and not self.entry.text().strip()):
            self.walk_history(step)
        elif self.arg_items:
            self.sel = (self.sel + step) % len(self.arg_items)
            sounds.play("cmd_move")
            self.show_arg_items()
        elif self.suggestions:
            self.sel = (self.sel + step) % len(self.suggestions)
            sounds.play("cmd_move")
            self.show_suggestions()

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
        self.entry.end(False)
        self.show_message(tr("История: ↑ раньше, ↓ позже. Enter — выполнить, или правь текст"))

    def remember(self, text):
        text = text.strip()
        if text and (not self.history or self.history[-1] != text):
            self.history.append(text)
            del self.history[:-50]
            self.save_history()
        self.hist_pos = None

    def load_history(self):
        import json
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

    def complete(self):
        """Tab: подставить выбранную подсказку в поле."""
        if self.arg_items or self.suggestions:
            sounds.play("cmd_complete")
        if self.arg_items:
            insert = self.arg_items[self.sel][0]
            self.set_text(f"{self.arg_word} {insert}")
            self.entry.end(False)
            self.on_text()
        elif self.suggestions:
            _cmd, name = self.suggestions[self.sel]
            self.set_text(name + " ")
            self.entry.end(False)
            self.on_text()

    # --- выполнение ---
    def run(self):
        text = self.entry.text()
        if self.arg_items:  # если показан список вариантов, выполняем выбранный
            text = f"{self.arg_word} {self.arg_items[self.sel][0]}"
        if not text.strip():
            return
        result = self.registry.run(text)
        if isinstance(result, str):
            result = Reply(result)
        if not (isinstance(result, Reply) and result.error):
            self.remember(text)
        self.suggestions = []
        self.arg_items = []
        if result is None:
            sounds.play("command_ok")
            self.close_bar()
        elif isinstance(result, Paged):
            self.paged = result
            self.page = result.page
            self.set_text("")
            self.show_page()
        else:
            if result.error:
                sounds.play("error")
            self.show_message(result.text, error=result.error)  # текст остаётся в поле

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
