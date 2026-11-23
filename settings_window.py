"""Окно настроек на PySide6: слева отделы, справа категории и подкатегории выбранного отдела.
Что показывать, берётся из settings_data.py. У каждого пункта есть кнопка «Сброс»,
внизу списка отделов кнопка «Сбросить всё»; заводские значения лежат в config.DEFAULT_SETTINGS.
Окно не модальное: app.py создаёт его, вызывает show() и следит за сигналом destroyed."""
from PySide6.QtGui import QColor
from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtWidgets import (QCheckBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
                               QSlider, QVBoxLayout, QWidget)
from shiboken6 import isValid

import dialogs
import firstrun
import sounds
import theme
from about_page import AboutPage
from color_picker import TileColorsPage
from commands_page import CommandsPage
from config import DEFAULT_SETTINGS, HOTKEY_SETTINGS
from controls_page import ShortcutsReference, TileKeysPage
from faq_data import FAQ
from faq_page import FaqPage
from hotkey_capture import HotkeyCapture, pretty
from i18n import tr
from icons_page import IconsPage
from notes_settings import NotesFolderPage
from settings_data import SETTINGS
from theme_page import ThemePage
from ui_kit import Segmented, Switch, button, clear_layout, label, repolish

INDENT = 20  # отступ пунктов слева


class SettingsWindow(QDialog):
    def __init__(self, master, settings, on_change):
        super().__init__(master)
        self.settings = settings    # текущие значения (тот же словарь, что и у лаунчера)
        self.on_change = on_change  # on_change(ключ, новое значение)
        self.current = 0
        self.reset_buttons = {}     # ключ настройки -> её кнопка «Сброс»
        self.box = None
        self.opened_blocks = set()  # названия сворачиваемых блоков, которые пользователь раскрыл
        self.closed_blocks = set()  # и свёрнул (для блоков, которые по умолчанию раскрыты)
        self._pending = None        # (ключ, значение) ползунка, которое ещё не применили
        self.anchors = {}           # id пункта/категории -> виджет, к которому прокручивает поиск
        self.faq_page = None
        self.hits = []              # найденные поиском места, hit_pos — на каком из них мы сейчас
        self.hit_pos = 0
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.run_search)
        self.slider_timer = QTimer(self)
        self.slider_timer.setSingleShot(True)
        self.slider_timer.timeout.connect(self.flush_slider)

        self.setWindowTitle(tr("Настройки"))
        self.resize(900, 480)
        self.setMinimumSize(520, 360)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        firstrun.apply_icon(self)

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # слева: список отделов
        nav = QFrame()
        nav.setFixedWidth(180)
        nav.setProperty("flat", True)
        nav_layout = QVBoxLayout(nav)
        nav_layout.setContentsMargins(10, 10, 10, 10)
        nav_layout.setSpacing(2)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Поиск по настройкам"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _=None: self.search_timer.start(250))
        self.search.installEventFilter(self)  # Enter / стрелки: перейти к следующему найденному месту
        nav_layout.addWidget(self.search)
        self.search_status = label("", dim=True, size=11)
        self.search_status.setContentsMargins(4, 0, 0, 4)
        nav_layout.addWidget(self.search_status)
        self.nav_buttons = []
        for i, section in enumerate(SETTINGS):
            btn = QPushButton(section["title"])
            btn.setProperty("nav", True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _=False, idx=i: self.go(idx))
            nav_layout.addWidget(btn)
            self.nav_buttons.append(btn)
        nav_layout.addStretch(1)
        nav_layout.addWidget(button(tr("Сбросить всё"), self.reset_all, danger=True))
        root.addWidget(nav)

        # справа: содержимое выбранного отдела
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        root.addWidget(self.scroll, 1)

        self.show_section(0)

    # --- применение и сброс ---
    def apply(self, key, value):
        """Передать новое значение лаунчеру и обновить состояние кнопок «Сброс»."""
        self.on_change(key, value)
        if isValid(self):  # лаунчер мог закрыться или перезапуститься прямо при смене настройки
            self.sync_resets()

    def on_switch(self, key, value):
        """«Выключено» звучит до применения, «включено» после (так работает и сам переключатель звуков)."""
        if value:
            self.apply(key, value)
            sounds.play("toggle_on")
        else:
            sounds.play("toggle_off")
            self.apply(key, value)

    def sync_resets(self):
        """Кнопка «Сброс» активна, только если значение отличается от заводского."""
        for key, btn in self.reset_buttons.items():
            try:
                btn.setEnabled(self.settings.get(key) != DEFAULT_SETTINGS[key])
            except RuntimeError:
                pass  # кнопку уже убрали при перерисовке

    def flush_slider(self):
        if self._pending is not None:
            key, value = self._pending
            self._pending = None
            self.apply(key, value)
            sounds.play("option")

    def cancel_slider_job(self):
        self.slider_timer.stop()
        self._pending = None

    def reset_one(self, key):
        sounds.play("click")
        self.cancel_slider_job()
        self.apply(key, DEFAULT_SETTINGS[key])
        if isValid(self):
            self.refresh()  # пункт покажет заводское значение

    def reset_all(self):
        if not dialogs.ask(self, tr("Сброс настроек"), tr("Вернуть все настройки к заводским?\nПлитки не изменятся.")):
            return
        sounds.play("click")
        self.cancel_slider_job()
        for key, default in DEFAULT_SETTINGS.items():
            if self.settings.get(key) != default:  # трогаем только то, что менялось
                self.apply(key, default)
                if not isValid(self):
                    return
        self.refresh()

    # --- отрисовка ---
    def refresh(self):
        """Перерисовать открытый отдел (после сброса или отката значения). Прокрутка остаётся."""
        self.show_section(self.current, keep_scroll=True)

    def go(self, index):
        if index != self.current:
            sounds.play("nav")
        self.show_section(index)

    def show_section(self, index, keep_scroll=False, target=None):
        bar = self.scroll.verticalScrollBar()
        position = bar.value() if keep_scroll else 0
        self.build_section(index)
        QTimer.singleShot(0, lambda: isValid(bar) and bar.setValue(position))
        if target is not None:
            QTimer.singleShot(40, lambda: isValid(self) and self.scroll_to(target))

    def build_section(self, index):
        self.current = index
        for i, btn in enumerate(self.nav_buttons):
            btn.setProperty("selected", i == index)
            repolish(btn)
        self.reset_buttons = {}
        self.anchors = {}
        self.faq_page = None

        host = QWidget()
        self.box = QVBoxLayout(host)
        self.box.setContentsMargins(16, 10, 16, 16)
        self.box.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(host)  # прежнее содержимое уничтожается

        section = SETTINGS[index]
        self.box.addWidget(label(section["title"], bold=True, size=22))
        custom = section.get("custom")
        if custom == "faq":
            self.faq_page = FaqPage()
            self.box.addWidget(self.faq_page)
        elif custom == "about":
            self.box.addWidget(AboutPage(host, self.parent()))
        elif custom == "commands":
            self.box.addWidget(CommandsPage(host, self.parent()))
        else:
            for category in section["categories"]:
                self.draw_category(category)
            self.sync_resets()

    def draw_category(self, category, size=16):
        if "categories" in category:  # сворачиваемый блок вложенных категорий
            self.draw_block(category)
            return
        head = label(category["title"], bold=True, size=size)
        head.setContentsMargins(0, 10, 0, 2)
        self.box.addWidget(head)
        self.anchors[id(category)] = head
        for item in category["subcategories"]:
            self.draw_item(item)

    def draw_block(self, block):
        """Заголовок-кнопка и под ним вложенные категории; клик по заголовку сворачивает и раскрывает."""
        title = block["title"]
        opened = title in self.opened_blocks or (not block.get("collapsed") and title not in self.closed_blocks)
        outer = self.box
        content = QWidget()
        self.box = QVBoxLayout(content)  # вложенные пункты рисуются в свою колонку
        self.box.setContentsMargins(0, 0, 0, 0)
        for category in block["categories"]:
            self.draw_category(category, size=14)
        self.box = outer
        content.setVisible(opened)

        def arrow(is_open):
            return f"{'▾' if is_open else '▸'} {title}"

        def toggle():
            now_open = not content.isVisible()
            content.setVisible(now_open)
            head_btn.setText(arrow(now_open))
            (self.opened_blocks if now_open else self.closed_blocks).add(title)
            (self.closed_blocks if now_open else self.opened_blocks).discard(title)
            sounds.play("nav")

        head_btn = button(arrow(opened), toggle, ghost=True, compact=True)
        head_wrap = QWidget()
        lay = QHBoxLayout(head_wrap)
        lay.setContentsMargins(0, 14, 0, 2)
        lay.addWidget(head_btn)
        lay.addStretch(1)
        self.box.addWidget(head_wrap)
        self.box.addWidget(content)
        self.anchors[id(block)] = head_wrap

    def indented(self, widget):
        """Кладёт виджет в основную колонку с отступом слева."""
        wrap = QWidget()
        lay = QHBoxLayout(wrap)
        lay.setContentsMargins(INDENT, 2, 0, 2)
        lay.addWidget(widget)
        lay.addStretch(0)
        self.box.addWidget(wrap)

    def draw_item(self, item):
        if isinstance(item, dict) and "custom" in item:  # блок со своим устройством, а не обычный пункт
            page = {
                "shortcuts": lambda: ShortcutsReference(),
                "tile_keys": lambda: TileKeysPage(None, self.parent()),
                "tile_colors": lambda: TileColorsPage(None, self.parent()),
                "icons": lambda: IconsPage(None, self.parent()),
                "theme_pack": lambda: ThemePage(None, self.parent()),
                "notes_folder": lambda: NotesFolderPage(None, self.parent()),
            }.get(item["custom"])
            if page:
                widget = page()
                wrap = QWidget()
                lay = QVBoxLayout(wrap)
                lay.setContentsMargins(INDENT, 0, 0, 0)
                lay.addWidget(widget)
                self.box.addWidget(wrap)
            return
        if isinstance(item, str):  # заглушка без управления
            self.indented(label(f"▸ {item}", dim=True))
            return

        key, kind, title = item["key"], item["type"], item["title"]
        title_label = None
        if kind in ("choice", "slider", "hotkey"):
            text = f"{title}: {self.settings[key]}{item.get('unit', '')}" if kind == "slider" else title
            title_label = label(text, wrap=False)
            title_label.setContentsMargins(INDENT, 8, 0, 0)
            self.box.addWidget(title_label)

        # строка пункта: элемент, «?» с подсказкой (если есть), «Сброс»
        row_host = QWidget()
        row = QHBoxLayout(row_host)
        row.setContentsMargins(INDENT, 2, 0, 4)
        row.setSpacing(10)

        if kind == "switch":
            box = Switch(title)
            box.setChecked(bool(self.settings[key]))
            box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            box.clicked.connect(lambda _=False, b=box: self.on_switch(key, b.isChecked()))
            row.addWidget(box)
        elif kind == "choice":
            row.addWidget(self.make_choice(key, item["options"]))
        elif kind == "slider":
            row.addWidget(self.make_slider(item, key, title, title_label))
        elif kind == "hotkey":
            row.addWidget(self.make_hotkey(key, title))

        if item.get("hint"):
            help_label = QLabel("?")
            help_label.setFixedSize(24, 24)
            help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            help_label.setStyleSheet(f"background-color: {theme.color('help_badge')}; "
                                     f"color: {theme.color('help_text')}; border-radius: 12px; font-weight: bold;")
            help_label.setToolTip(item["hint"])
            row.addWidget(help_label)

        reset_btn = button(tr("Сброс"), lambda: self.reset_one(key), width=64, ghost=True, compact=True)
        reset_btn.setFixedHeight(26)
        row.addWidget(reset_btn)
        row.addStretch(1)
        self.reset_buttons[key] = reset_btn
        self.box.addWidget(row_host)
        self.anchors[id(item)] = title_label or row_host

    # --- элементы ---
    def make_choice(self, key, options):
        def pick(value):
            self.apply(key, value)
            if isValid(seg):
                seg.set(self.settings[key])  # если лаунчер не принял значение, вернётся прежнее
                sounds.play("option")

        seg = Segmented(options, self.settings[key], pick)
        return seg

    def make_slider(self, item, key, title, title_label):
        lo, hi, step = item["min"], item["max"], item.get("step", 1)
        unit = item.get("unit", "")
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, (hi - lo) // step)
        slider.setValue(round((self.settings[key] - lo) / step))
        slider.setFixedWidth(300)
        slider.setFixedHeight(20)
        slider.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        def changed(position):
            value = lo + position * step
            title_label.setText(f"{title}: {value}{unit}")
            self._pending = (key, value)
            self.slider_timer.start(250)  # применяем, когда ползунок остановился, а не на каждый пиксель

        slider.valueChanged.connect(changed)
        return slider

    def make_hotkey(self, key, title):
        btn = QPushButton(pretty(self.settings[key]))
        btn.setFixedWidth(180)

        def on_pick(combo):
            self.apply(key, combo)
            if isValid(self):
                sounds.play("hotkey_set")
                self.refresh()  # кнопка покажет новую комбинацию

        def change():
            others = [self.settings[k] for k in HOTKEY_SETTINGS if k != key]
            HotkeyCapture(self, title, self.settings[key], others, on_pick).open()

        btn.clicked.connect(lambda _=False: change())
        return btn

    # --- поиск по настройкам ---
    def search_index(self):
        """Все места, где можно что-то найти: [{section, anchor, blocks, title, cat, extra, faq}]."""
        entries = []

        def walk(si, categories, blocks, section_title):
            for cat in categories:
                if "categories" in cat:  # сворачиваемый блок
                    entries.append({"section": si, "anchor": id(cat), "blocks": blocks, "title": cat["title"],
                                    "cat": section_title, "extra": ""})
                    walk(si, cat["categories"], blocks + [cat["title"]], section_title)
                    continue
                entries.append({"section": si, "anchor": id(cat), "blocks": blocks, "title": cat["title"],
                                "cat": section_title, "extra": ""})
                for item in cat["subcategories"]:
                    if isinstance(item, str):
                        entries.append({"section": si, "anchor": id(cat), "blocks": blocks, "title": item,
                                        "cat": cat["title"], "extra": section_title})
                    elif "custom" not in item:
                        extra = " ".join([item.get("hint", ""), section_title] + [str(v) for v in item.get("options", {}).values()])
                        entries.append({"section": si, "anchor": id(item), "blocks": blocks, "title": item["title"],
                                        "cat": cat["title"], "extra": extra})

        for si, section in enumerate(SETTINGS):
            entries.append({"section": si, "anchor": None, "blocks": [], "title": section["title"], "cat": "", "extra": ""})
            walk(si, section.get("categories", []), [], section["title"])
            if section.get("custom") == "faq":
                for question, answer in FAQ:
                    entries.append({"section": si, "anchor": None, "blocks": [], "title": question,
                                    "cat": section["title"], "extra": answer, "faq": True})
        return entries

    def run_search(self):
        # слова длиннее 4 букв ищем без двух последних: «быстрая клавиша» найдёт «быстрые клавиши»
        words = [w if len(w) < 5 else w[:-2] for w in self.search.text().casefold().split()]
        self.hits, self.hit_pos = [], 0
        if not words:
            self.search_status.setText("")
            return
        scored = []
        for order, e in enumerate(self.search_index()):
            title, cat, extra = e["title"].casefold(), e["cat"].casefold(), e["extra"].casefold()
            if all(w in title for w in words):
                score = 3
            elif all(w in title + " " + cat for w in words):
                score = 2
            elif all(w in title + " " + cat + " " + extra for w in words):
                score = 1
            else:
                continue
            scored.append((-score, order, e))
        self.hits = [e for _, _, e in sorted(scored, key=lambda t: (t[0], t[1]))]
        self.goto_hit()

    def goto_hit(self):
        if not self.hits:
            self.search_status.setText(tr("Ничего не найдено"))
            return
        e = self.hits[self.hit_pos]
        self.search_status.setText(tr("{i} из {n}  (Enter: дальше)", i=self.hit_pos + 1, n=len(self.hits)))
        for title in e["blocks"]:  # раскрываем свёрнутые блоки, в которых лежит найденное
            self.opened_blocks.add(title)
            self.closed_blocks.discard(title)
        sounds.play("nav")
        self.show_section(e["section"], target=e["anchor"])
        if e.get("faq") and self.faq_page is not None:
            self.faq_page.search.setText(self.search.text())  # покажет подходящие вопросы с открытыми ответами

    def step_hit(self, delta):
        if self.hits:
            self.hit_pos = (self.hit_pos + delta) % len(self.hits)
            self.goto_hit()

    def eventFilter(self, obj, event):
        if obj is self.search and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Down):
                pending = self.search_timer.isActive()  # текст ещё не искали: сначала ищем
                self.search_timer.stop()
                if pending or not self.hits:
                    self.run_search()
                else:
                    self.step_hit(1)
                return True
            if key == Qt.Key.Key_Up:
                self.step_hit(-1)
                return True
            if key == Qt.Key.Key_Escape and self.search.text():
                self.search.clear()
                return True
        return super().eventFilter(obj, event)

    def scroll_to(self, anchor_id):
        """Прокручивает правую часть к найденному пункту и ненадолго подсвечивает его."""
        host = self.scroll.widget()
        if host is None:
            return
        host.layout().activate()
        widget = self.anchors.get(anchor_id)
        bar = self.scroll.verticalScrollBar()
        if widget is None or not isValid(widget):
            bar.setValue(0)
            return
        bar.setValue(max(0, widget.mapTo(host, QPoint(0, 0)).y() - 48))
        self.flash(widget)

    def flash(self, widget):
        c = QColor(theme.color("select_border"))
        widget.setObjectName("searchhit")
        widget.setStyleSheet(f"#searchhit {{ background-color: rgba({c.red()}, {c.green()}, {c.blue()}, 70); "
                             f"border-radius: 6px; }}")

        def clear():
            if isValid(widget):
                widget.setStyleSheet("")
        QTimer.singleShot(1600, clear)

    def closeEvent(self, event):
        self.flush_slider()  # не теряем значение, которое двигали за мгновение до закрытия
        super().closeEvent(event)
