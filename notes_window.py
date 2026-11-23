"""Окно заметок на PySide6: слева список, справа редактор.
Файлы лежат в общей папке вне проекта (см. notes_store.py).
Сохраняется само через пару мгновений после последней правки.
Раз в пару секунд окно смотрит в папку: заметки, изменённые другой программой, подхватываются сами.

Интерфейс для app.py: bring_to_front(), save_now(), use_folder(store), apply_settings(), сигнал destroyed."""
import os
import time

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtWidgets import (QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPushButton, QScrollArea, QSizePolicy, QTextEdit, QVBoxLayout, QWidget)

import dialogs
import firstrun
import sounds
import theme
from i18n import tr
from md_edit import MarkdownEdit
from notes_store import NoteStore
from ui_kit import repolish

SAVE_DELAY = 700   # мс тишины после правки, прежде чем писать на диск
POLL_DELAY = 2000  # как часто смотрим, не менялась ли папка снаружи, мс
TITLE_ROLE = Qt.ItemDataRole.UserRole
WIDE_ON = 940      # окно шире этого: включается «широкий режим» (боковая панель, просторнее список)
WIDE_OFF = 880     # и обратно в компактный, только когда стало уже этого (запас, чтобы не мигало на границе)
SIDE_NARROW, SIDE_WIDE = 190, 250


class NotesWindow(QWidget):
    def __init__(self, master, store, on_folder_change, anchor=None):
        super().__init__(master, Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setProperty("window_root", True)  # фон окна из темы
        self.app = master
        self.store = store
        self.on_folder_change = on_folder_change  # on_folder_change(новая папка): запомнить в настройках
        settings = getattr(master, "settings", {})
        self.save_delay = settings.get("notes_autosave_ms", SAVE_DELAY)
        self.sort = settings.get("notes_sort", "date")
        self.current = None        # заголовок открытой заметки (= имя файла без .md)
        self.loaded_text = ""      # текст, который считаем «как на диске»
        self.loaded_mtime = None
        self.dirty = False         # есть несохранённые правки
        self.loading = False       # True, пока поля заполняем из кода, а не печатает человек
        self.filter_text = ""
        self.text_cache = {}       # заголовок -> (время файла, текст в нижнем регистре)
        self.list_signature = None
        self.tabs = []             # заголовки заметок, открытых во вкладках (вкладки видны в широком режиме)
        self.wide = False          # «широкий режим»: окно растянули, и показываются дополнительные панели

        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self.save_now)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(POLL_DELAY)
        self.poll_timer.timeout.connect(self.poll)

        self.setWindowTitle(tr("Заметки"))
        self.setMinimumSize(420, 300)
        firstrun.apply_icon(self)
        self.build_ui()
        self.apply_font(settings.get("notes_font_size", 14))
        self.place_near(anchor, 530, 400)

        for widget in (self, self.title_entry, self.text, self.search, self.list, self.tabbar.viewport()):
            widget.installEventFilter(self)

        self.show_folder()
        self.open_first()
        self.poll_timer.start()
        self.bring_to_front()

    # --- построение окна ---
    def build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        side = self.side = QFrame()
        side.setFixedWidth(SIDE_NARROW)
        side.setProperty("flat", True)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(10, 10, 10, 10)
        new_btn = QPushButton(tr("＋  Новая заметка"))
        new_btn.clicked.connect(lambda _=False: self.new_note())
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Поиск по названию и тексту"))
        self.search.textChanged.connect(self.on_search)
        self.list = QListWidget()
        self.list.itemClicked.connect(lambda item: self.select(item.data(TITLE_ROLE)))
        self.folder_label = QLabel("")
        self.folder_label.setWordWrap(True)
        self.folder_label.setProperty("dim", True)
        self.folder_label.setStyleSheet("font-size: 11px;")
        folder_btn = QPushButton(tr("Папка…"))
        folder_btn.setProperty("ghost", True)
        folder_btn.clicked.connect(lambda _=False: self.choose_folder())
        for w in (new_btn, self.search):
            side_layout.addWidget(w)
        side_layout.addWidget(self.list, 1)
        side_layout.addWidget(self.folder_label)
        side_layout.addWidget(folder_btn)
        root.addWidget(side)

        editor = QWidget()
        ed = QVBoxLayout(editor)
        ed.setContentsMargins(8, 10, 10, 10)
        self.title_entry = QLineEdit()
        self.title_entry.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.title_entry.setFixedHeight(40)
        self.title_entry.textChanged.connect(lambda _: self.on_edit())
        self.title_entry.editingFinished.connect(self.sync_title)
        self.text = MarkdownEdit()
        self.text.textChanged.connect(self.on_text_changed)
        bottom = QHBoxLayout()
        self.status = QLabel("")
        self.status.setProperty("dim", True)
        self.status.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)  # длинный текст не растягивает окно
        self.status.setMinimumWidth(0)
        self.counter = QLabel("")
        self.counter.setProperty("dim", True)
        self.pin_btn = QPushButton(tr("★ Закрепить"))
        self.pin_btn.setProperty("ghost", True)
        self.pin_btn.setFixedWidth(120)
        self.pin_btn.clicked.connect(lambda _=False: self.toggle_pin())
        self.delete_btn = QPushButton(tr("Удалить"))
        self.delete_btn.setProperty("danger", True)
        self.delete_btn.setFixedWidth(90)
        self.delete_btn.clicked.connect(lambda _=False: self.delete_note())
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.counter)
        bottom.addWidget(self.pin_btn)
        bottom.addWidget(self.delete_btn)
        self.build_tabbar()
        self.build_toolbar()
        ed.addWidget(self.tabbar)
        ed.addWidget(self.title_entry)
        ed.addWidget(self.toolbar)
        ed.addWidget(self.text, 1)
        ed.addLayout(bottom)
        root.addWidget(editor, 1)

        # дополнительная панель справа: есть только в широком режиме. Новые функции добавляются в build_extras()
        self.extras = QFrame()
        self.extras.setFixedWidth(230)
        self.extras.setProperty("flat", True)
        self.extras_layout = QVBoxLayout(self.extras)
        self.extras_layout.setContentsMargins(12, 12, 12, 12)
        self.extras_layout.setSpacing(6)
        self.build_extras(self.extras_layout)
        self.extras.hide()
        root.addWidget(self.extras)

    # --- вкладки: несколько открытых заметок (редактор один, вкладка просто переключает заметку) ---
    def build_tabbar(self):
        self.tabbar = QScrollArea()
        self.tabbar.setFrameShape(QFrame.Shape.NoFrame)
        self.tabbar.setWidgetResizable(True)
        self.tabbar.setFixedHeight(42)
        self.tabbar.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabbar.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)  # листается колесом мыши
        self.tabbar.viewport().setStyleSheet("background: transparent;")
        self.tabs_host = QWidget()
        self.tabs_host.setStyleSheet("background: transparent;")
        self.tabs_layout = QHBoxLayout(self.tabs_host)
        self.tabs_layout.setContentsMargins(0, 2, 0, 4)
        self.tabs_layout.setSpacing(4)
        self.tabbar.setWidget(self.tabs_host)
        self.tabbar.hide()

    def same(self, a, b):
        return a.lower() == b.lower()

    def tab_index(self, title):
        return next((i for i, t in enumerate(self.tabs) if self.same(t, title)), -1)

    def sync_tabs(self, notes=None):
        """Приводит вкладки в порядок: открытая заметка есть во вкладках, удалённых с диска там нет."""
        if notes is not None:
            existing = {title.lower() for title, _mtime in notes}
            self.tabs = [t for t in self.tabs if t.lower() in existing]
        if self.current is not None and self.tab_index(self.current) < 0:
            self.tabs.append(self.current)
        self.draw_tabs()

    def rename_tab(self, old, new):
        i = self.tab_index(old)
        if i >= 0:
            self.tabs[i] = new  # вкладка остаётся на своём месте

    def draw_tabs(self):
        signature = (tuple(self.tabs), self.current)
        if signature == getattr(self, "_tabs_signature", None):
            return
        self._tabs_signature = signature
        while self.tabs_layout.count():
            item = self.tabs_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        text, dim = theme.color("text"), theme.color("text_dim")
        hover = theme.color("ghost_hover")
        for title in self.tabs:
            is_current = self.current is not None and self.same(title, self.current)
            tab = QFrame()
            tab.setObjectName("ntab")
            bg = theme.color("nav_selected") if is_current else theme.color("card_bg")
            edge = f"border-bottom: 2px solid {theme.color('accent')};" if is_current else "border-bottom: 2px solid transparent;"
            tab.setStyleSheet(f"#ntab {{ background-color: {bg}; border-radius: 6px; {edge} }}")
            lay = QHBoxLayout(tab)
            lay.setContentsMargins(0, 0, 4, 0)
            lay.setSpacing(0)
            name = QPushButton(title if len(title) <= 20 else title[:19] + "…")
            name.setToolTip(title)
            name.setCursor(Qt.CursorShape.PointingHandCursor)
            name.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            name.setStyleSheet(f"QPushButton {{ background: transparent; border: none; color: {text}; padding: 5px 4px 5px 12px; "
                               f"min-height: 0; min-width: 0; font-size: 13px; "
                               f"font-weight: {'bold' if is_current else 'normal'}; }}")
            name.clicked.connect(lambda _=False, t=title: self.select(t))
            close = QPushButton("×")
            close.setFixedSize(22, 22)
            close.setCursor(Qt.CursorShape.PointingHandCursor)
            close.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            close.setToolTip(tr("Закрыть вкладку"))
            close.setStyleSheet(f"QPushButton {{ background: transparent; border: none; border-radius: 4px; color: {dim}; "
                                f"padding: 0 0 2px 0; min-height: 0; min-width: 0; font-size: 17px; }}"
                                f"QPushButton:hover {{ background-color: {hover}; color: {text}; }}")
            close.clicked.connect(lambda _=False, t=title: self.close_tab(t))
            lay.addWidget(name)
            lay.addWidget(close)
            self.tabs_layout.addWidget(tab)
        self.tabs_layout.addStretch(1)

    def close_tab(self, title):
        """Закрыть вкладку (сама заметка остаётся на диске). Последнюю вкладку не закрываем."""
        i = self.tab_index(title)
        if i < 0 or len(self.tabs) <= 1:
            return
        is_current = self.current is not None and self.same(title, self.current)
        neighbour = self.tabs[i + 1] if i + 1 < len(self.tabs) else self.tabs[i - 1]
        del self.tabs[i]
        if is_current:
            self.select(neighbour)
        self.sync_tabs()

    # --- панель форматирования (Markdown) ---
    def build_toolbar(self):
        self.toolbar = QFrame()
        lay = QHBoxLayout(self.toolbar)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        text, hover = theme.color("text"), theme.color("ghost_hover")
        style = (f"QPushButton {{ background: transparent; border: none; border-radius: 5px; color: {text}; "
                 f"padding: 0 9px; min-height: 0; min-width: 0; font-size: 13px; }}"
                 f"QPushButton:hover {{ background-color: {hover}; }}"
                 f"QPushButton:pressed {{ background-color: {theme.color('nav_selected')}; }}")
        spec = [
            ("H1", tr("Заголовок 1"), lambda: self.fmt_heading(1), "font-weight: bold;"),
            ("H2", tr("Заголовок 2"), lambda: self.fmt_heading(2), "font-weight: bold;"),
            ("H3", tr("Заголовок 3"), lambda: self.fmt_heading(3), "font-weight: bold;"),
            None,
            ("B", tr("Жирный (Ctrl+B)"), lambda: self.fmt_wrap("**", "**", tr("жирный")), "font-weight: bold;"),
            ("I", tr("Курсив (Ctrl+I)"), lambda: self.fmt_wrap("*", "*", tr("курсив")), "font-style: italic;"),
            None,
            ("•  " + tr("Список"), tr("Маркированный список"), lambda: self.fmt_lines("- "), ""),
            ("1.  " + tr("Список"), tr("Нумерованный список"), lambda: self.fmt_lines("1. ", numbered=True), ""),
            ("☑  " + tr("Задача"), tr("Чекбокс"), lambda: self.fmt_lines("- [ ] "), ""),
            None,
            (tr("Ссылка"), tr("Ссылка (Ctrl+K)"), self.fmt_link, "text-decoration: underline;"),
        ]
        for entry in spec:
            if entry is None:
                sep = QFrame()
                sep.setFixedSize(1, 18)
                sep.setStyleSheet(f"background-color: {theme.color('entry_border')};")
                lay.addSpacing(5)
                lay.addWidget(sep)
                lay.addSpacing(5)
                continue
            label, tip, action, extra = entry
            btn = QPushButton(label)
            btn.setFixedHeight(28)
            btn.setToolTip(tip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # фокус остаётся в тексте, выделение не теряется
            btn.setStyleSheet(style + (f"QPushButton {{ {extra} }}" if extra else ""))
            btn.clicked.connect(lambda _=False, a=action: a())
            lay.addWidget(btn)
        lay.addStretch(1)
        self.toolbar.hide()

    def fmt_wrap(self, before, after, placeholder):
        """Обернуть выделенное в маркеры (**жирный**); если уже обёрнуто, снять; без выделения вставить заготовку."""
        cur = self.text.textCursor()
        cur.beginEditBlock()
        selected = cur.selectedText()
        if selected.startswith(before) and selected.endswith(after) and len(selected) >= len(before) + len(after):
            cur.insertText(selected[len(before):len(selected) - len(after)])
        elif selected:
            cur.insertText(before + selected + after)
        else:
            start = cur.position() + len(before)
            cur.insertText(before + placeholder + after)
            cur.setPosition(start)
            cur.setPosition(start + len(placeholder), cur.MoveMode.KeepAnchor)
        cur.endEditBlock()
        self.text.setTextCursor(cur)
        self.text.setFocus()

    def selected_blocks(self):
        """Первый и последний номер строки (абзаца), которых касается выделение."""
        cur = self.text.textCursor()
        doc = self.text.document()
        first = doc.findBlock(cur.selectionStart()).blockNumber()
        end = cur.selectionEnd()
        last = doc.findBlock(end).blockNumber()
        if cur.hasSelection() and end > cur.selectionStart() and doc.findBlock(end).position() == end:
            last = max(first, last - 1)  # выделение кончается в самом начале строки: её не трогаем
        return first, last

    def fmt_lines(self, prefix, numbered=False):
        """Список из выбранных строк: ставит или снимает маркер (- , 1. , - [ ] ). Другой маркер заменяет."""
        import re
        marker = re.compile(r"^(\s*)(- \[[ xX]\] |[-*+] |\d+\. )")
        first, last = self.selected_blocks()
        doc = self.text.document()
        blocks = [doc.findBlockByNumber(n) for n in range(first, last + 1)]
        probe = r"^\s*\d+\. " if numbered else r"^\s*" + re.escape(prefix)
        remove = all(re.match(probe, b.text()) for b in blocks if b.text().strip()) and any(b.text().strip() for b in blocks)
        cur = self.text.textCursor()
        cur.beginEditBlock()
        number = 1
        for b in blocks:
            line = b.text()
            if not line.strip() and len(blocks) > 1:
                continue
            m = marker.match(line)
            body = line[m.end():] if m else line.lstrip()
            indent = m.group(1) if m else line[:len(line) - len(line.lstrip())]
            if remove:
                new = indent + body
            else:
                new = indent + (f"{number}. " if numbered else prefix) + body
                number += 1
            c = self.text.textCursor()
            c.setPosition(b.position())
            c.movePosition(c.MoveOperation.EndOfBlock, c.MoveMode.KeepAnchor)
            c.insertText(new)
        cur.endEditBlock()
        self.text.setFocus()

    def fmt_heading(self, level):
        """Заголовок уровня level у выбранных строк; повторное нажатие того же уровня снимает его."""
        import re
        first, last = self.selected_blocks()
        doc = self.text.document()
        blocks = [doc.findBlockByNumber(n) for n in range(first, last + 1)]
        mark = "#" * level + " "
        cur = self.text.textCursor()
        cur.beginEditBlock()
        for b in blocks:
            line = b.text()
            body = re.sub(r"^#{1,6} ", "", line)
            new = body if line.startswith(mark) else mark + body
            c = self.text.textCursor()
            c.setPosition(b.position())
            c.movePosition(c.MoveOperation.EndOfBlock, c.MoveMode.KeepAnchor)
            c.insertText(new)
        cur.endEditBlock()
        self.text.setFocus()

    def fmt_link(self):
        """[текст](адрес): выделенное становится текстом ссылки, а в адресе выделено слово «адрес», чтобы сразу вписать."""
        cur = self.text.textCursor()
        cur.beginEditBlock()
        selected = cur.selectedText() or tr("текст")
        start = cur.selectionStart()
        placeholder = "https://"
        cur.insertText(f"[{selected}]({placeholder})")
        a = start + len(selected) + 3
        cur.setPosition(a)
        cur.setPosition(a + len(placeholder), cur.MoveMode.KeepAnchor)
        cur.endEditBlock()
        self.text.setTextCursor(cur)
        self.text.setFocus()

    def build_extras(self, layout):
        """Содержимое правой панели широкого режима. Сюда в будущем кладём новые возможности заметок."""
        head = QLabel(tr("Сведения"))
        head.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(head)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        self.info.setProperty("dim", True)
        self.info.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.info)
        layout.addStretch(1)

    def update_info(self):
        """Сведения о заметке в правой панели (считаем, только когда она видна)."""
        if not self.wide:
            return
        if self.current is None:
            self.info.setText("")
            return
        text = self.text.toPlainText()
        lines = [
            tr("Слов: {v}", v=len(text.split())),
            tr("Символов: {v}", v=len(text)),
            tr("Строк: {v}", v=text.count("\n") + 1 if text else 0),
        ]
        try:
            lines.append(tr("Изменена: {v}", v=time.strftime("%d.%m.%Y %H:%M", time.localtime(self.loaded_mtime))))
        except (TypeError, ValueError, OverflowError, OSError):
            pass
        self.info.setText("\n".join(lines))

    # --- адаптация под размер окна ---
    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = event.size().width()
        if not self.wide and width >= WIDE_ON:
            self.set_wide(True)
        elif self.wide and width < WIDE_OFF:
            self.set_wide(False)

    def set_wide(self, wide):
        self.wide = wide
        self.side.setFixedWidth(SIDE_WIDE if wide else SIDE_NARROW)
        self.extras.setVisible(wide)
        self.tabbar.setVisible(wide)
        self.toolbar.setVisible(wide)
        self.update_info()

    def apply_font(self, size):
        self.text.set_base_size(size)  # размер задаёт и обычный текст, и пропорции заголовков

    # --- положение и показ окна ---
    def place_near(self, anchor, width, height):
        screen = QGuiApplication.screenAt(QPoint(*anchor)) if anchor else None
        area = (screen or QGuiApplication.primaryScreen()).availableGeometry()
        if anchor:
            x, y = anchor[0] - width - 8, anchor[1] - height // 2
        else:
            x, y = area.x() + (area.width() - width) // 2, area.y() + (area.height() - height) // 2
        x = max(area.x(), min(x, area.right() - width - 75))
        y = max(area.y(), min(y, area.bottom() - height - 60))
        self.setGeometry(x, y, width, height)

    def bring_to_front(self):
        self.setWindowState((self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        self.show()
        self.raise_()
        self.activateWindow()

    # --- клавиши: Ctrl+N / S / P и Delete (по физической клавише: работает на любой раскладке) ---
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Wheel and obj is self.tabbar.viewport():
            bar = self.tabbar.horizontalScrollBar()
            bar.setValue(bar.value() - (event.angleDelta().y() or event.angleDelta().x()))
            return True
        if event.type() == QEvent.Type.KeyPress:
            mods = event.modifiers()
            if mods & Qt.KeyboardModifier.ControlModifier and not mods & Qt.KeyboardModifier.AltModifier:
                code = event.nativeVirtualKey() or event.key()
                if code == 78:    # N
                    self.new_note()
                    return True
                if code == 83:    # S
                    sounds.play("note_save")
                    self.save_now()
                    return True
                if code == 80:    # P
                    self.toggle_pin()
                    return True
                if code == 66 and obj is self.text:    # B: жирный
                    self.fmt_wrap("**", "**", tr("жирный"))
                    return True
                if code == 73 and obj is self.text:    # I: курсив
                    self.fmt_wrap("*", "*", tr("курсив"))
                    return True
                if code == 75 and obj is self.text:    # K: ссылка
                    self.fmt_link()
                    return True
            elif event.key() == Qt.Key.Key_Delete and not isinstance(obj, (QLineEdit, QTextEdit)):
                if self.current:  # в полях ввода Delete стирает символ, а не заметку
                    self.delete_note()
                    return True
        return super().eventFilter(obj, event)

    # --- вспомогательное ---
    def set_status(self, text, error=False):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {theme.color('error')};" if error else "")

    def show_folder(self):
        # нулевая ширина после «\\»: длинный путь без пробелов переносится, а не растягивает окно
        self.folder_label.setText(tr('Папка: {folder}', folder=self.store.folder).replace("\\", "\\\u200b"))

    def set_title_quiet(self, title):
        self.loading = True
        self.title_entry.setText(title)
        self.loading = False

    def set_editable(self, editable):
        for w in (self.title_entry, self.text, self.delete_btn, self.pin_btn):
            w.setEnabled(editable)

    def update_counter(self):
        self.update_info()
        if self.current is None:
            self.counter.setText("")
            return
        text = self.text.toPlainText()
        self.counter.setText(tr('{v} сл. · {v2} симв.', v=len(text.split()), v2=len(text)))

    def fill(self, title, text):
        self.set_editable(True)
        self.loading = True
        self.title_entry.setText(title)
        self.text.setPlainText(text)
        self.text.document().clearUndoRedoStacks()
        self.loading = False
        self.update_counter()
        self.update_pin_button()

    def clear_editor(self):
        self.fill("", "")
        self.current = None
        self.loaded_text, self.loaded_mtime, self.dirty = "", None, False
        self.update_counter()
        self.update_pin_button()
        self.set_editable(False)
        self.set_status(tr("Нет заметок. Нажми «Новая заметка» (Ctrl+N)"))
        self.refresh_list(force=True)

    # --- список заметок ---
    def scan(self):
        try:
            return self.store.list_notes(self.sort)
        except OSError:
            self.set_status(tr("Папка с заметками недоступна"), error=True)
            return None

    def refresh_list(self, force=False):
        notes = self.scan()
        if notes is None:
            return None
        signature = (tuple(notes), self.filter_text, self.current, tuple(self.store.pinned()))
        self.sync_tabs(notes)
        if force or signature != self.list_signature:
            self.list_signature = signature
            self.build_list(notes)
        return notes

    def build_list(self, notes):
        self.list.clear()
        pins = {t.lower() for t in self.store.pinned()}
        shown = [title for title, _mtime in notes if self.matches(title)]
        shown.sort(key=lambda title: title.lower() not in pins)  # закреплённые сверху
        if not shown:
            item = QListWidgetItem(tr("Ничего не найдено") if self.filter_text else tr("Пока пусто"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(item)
            return
        for title in shown:
            item = QListWidgetItem(("★ " + title) if title.lower() in pins else title)
            item.setData(TITLE_ROLE, title)
            self.list.addItem(item)
            if title == self.current:
                self.list.setCurrentItem(item)

    def matches(self, title):
        """Подходит ли заметка под поиск: совпадение в названии или в тексте."""
        query = self.filter_text
        if not query or query in title.lower():
            return True
        mtime = self.store.mtime(title)
        cached = self.text_cache.get(title)
        if cached is None or cached[0] != mtime:
            try:
                cached = (mtime, self.store.read(title)[0].lower())
            except OSError:
                return False
            self.text_cache[title] = cached
        return query in cached[1]

    def toggle_pin(self):
        if self.current is None:
            return
        pin = not self.store.is_pinned(self.current)
        try:
            self.store.set_pinned(self.current, pin)
        except OSError as e:
            self.set_status(tr('Не удалось закрепить: {e}', e=e), error=True)
            return
        sounds.play("note_pin" if pin else "note_unpin")
        self.update_pin_button()
        self.refresh_list(force=True)

    def update_pin_button(self):
        pinned = self.current is not None and self.store.is_pinned(self.current)
        self.pin_btn.setText(tr("★ Открепить") if pinned else tr("★ Закрепить"))

    def on_search(self, *_):
        self.filter_text = self.search.text().strip().lower()
        self.refresh_list(force=True)

    # --- открыть, создать, удалить ---
    def select(self, title):
        if not title or title == self.current:
            return
        if self.save_now():
            sounds.play("note_select")
            self.load(title)

    def load(self, title):
        try:
            text, mtime = self.store.read(title)
        except OSError:
            self.refresh_list(force=True)
            return False
        self.current = title
        self.loaded_text, self.loaded_mtime = text, mtime
        self.dirty = False
        self.fill(title, text)
        self.set_status("")
        self.refresh_list(force=True)
        return True

    def open_first(self):
        notes = self.refresh_list(force=True)
        if notes:
            self.load(notes[0][0])
        elif notes is not None:
            self.clear_editor()

    def new_note(self):
        if not self.save_now():
            return
        title = self.store.unique_title(tr("Новая заметка"))
        try:
            self.store.write(title, "")
        except OSError as e:
            dialogs.error(self, tr("Заметки"), tr('Не удалось создать заметку:\n{e}', e=e))
            return
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.filter_text = ""
        sounds.play("note_new")
        if self.load(title):
            self.title_entry.setFocus()
            self.title_entry.selectAll()

    def delete_note(self):
        if self.current is None:
            return
        if not dialogs.ask(self, tr("Удалить заметку"),
                           tr('Удалить «{current}»?\nФайл будет удалён с диска.', current=self.current)):
            return
        self.save_timer.stop()
        try:
            self.store.delete(self.current)
        except FileNotFoundError:
            pass
        except OSError as e:
            dialogs.error(self, tr("Заметки"), tr('Не удалось удалить:\n{e}', e=e))
            return
        sounds.play("note_delete")
        self.dirty = False
        self.current = None
        self.open_first()

    # --- правка и сохранение ---
    def on_text_changed(self):
        if not self.loading:
            self.on_edit()
        self.update_counter()

    def on_edit(self):
        if self.loading or self.current is None:
            return
        self.dirty = True
        self.set_status(tr("Изменено… (сохранение...)"))
        self.save_timer.start(self.save_delay)

    def sync_title(self):
        if self.save_now() and self.current:
            self.set_title_quiet(self.current)

    def save_now(self):
        self.save_timer.stop()
        if not self.dirty or self.current is None:
            return True

        store, old = self.store, self.current
        text = self.text.toPlainText()
        wanted = self.title_entry.text()
        new = store.unique_title(wanted, own=old) if wanted.strip() else old

        conflict = False
        disk_mtime = store.mtime(old)
        if disk_mtime is not None and disk_mtime != self.loaded_mtime:
            try:
                conflict = store.read(old)[0] != self.loaded_text
            except OSError:
                pass
        try:
            if conflict:
                new = store.unique_title(tr('{new} (конфликт)', new=new))
            elif new != old and disk_mtime is not None:
                store.rename(old, new)
                self.rename_tab(old, new)
            self.loaded_mtime = store.write(new, text)
        except OSError as e:
            self.set_status(tr('Не удалось сохранить: {e}', e=e), error=True)
            return False

        self.current = new
        self.loaded_text = text
        self.dirty = False
        self.update_info()
        if conflict:
            self.set_title_quiet(new)
            self.set_status(tr('Файл изменили снаружи: версия сохранена как «{new}»', new=new), error=True)
        else:
            self.set_status(tr('Сохранено {v}', v=time.strftime('%H:%M:%S')))
        self.refresh_list(force=True)
        return True

    # --- слежение за папкой ---
    def poll(self):
        notes = self.refresh_list()
        if notes is not None and self.current is not None and not self.dirty:
            mtimes = {title.lower(): mtime for title, mtime in notes}
            disk_mtime = mtimes.get(self.current.lower())
            if disk_mtime is None:
                self.open_first()
            elif disk_mtime != self.loaded_mtime:
                self.reload_current()

    def reload_current(self):
        try:
            text, mtime = self.store.read(self.current)
        except OSError:
            return
        if text != self.loaded_text:
            position = self.text.textCursor().position()
            self.fill(self.current, text)
            cursor = self.text.textCursor()
            cursor.setPosition(min(position, len(text)))
            self.text.setTextCursor(cursor)
            self.set_status(tr("Обновлено из файла"))
        self.loaded_text, self.loaded_mtime = text, mtime

    # --- папка, настройки и закрытие ---
    def choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, tr("Папка для заметок"), self.store.folder)
        if not folder:
            return
        folder = os.path.normpath(folder)
        if os.path.normcase(folder) == os.path.normcase(self.store.folder):
            return
        if not self.save_now():
            return
        try:
            store = NoteStore(folder)
        except OSError as e:
            dialogs.error(self, tr("Заметки"), tr('Не удалось открыть папку:\n{e}', e=e))
            return
        self.store = store
        self.text_cache.clear()
        self.on_folder_change(store.folder)
        self.current = None
        self.show_folder()
        self.open_first()
        self.set_status(tr("Папка изменена."))

    def apply_settings(self):
        """Подхватывает настройки заметок, изменённые в окне настроек, без перезапуска."""
        settings = getattr(self.app, "settings", {})
        self.save_delay = settings.get("notes_autosave_ms", SAVE_DELAY)
        self.apply_font(settings.get("notes_font_size", 14))
        sort = settings.get("notes_sort", "date")
        if sort != self.sort:
            self.sort = sort
            self.refresh_list(force=True)

    def use_folder(self, store):
        """Переключает окно на другую папку заметок (когда её сменили в настройках)."""
        if not self.save_now():
            return
        self.store = store
        self.text_cache.clear()
        self.current = None
        self.show_folder()
        self.open_first()

    def closeEvent(self, event):
        self.poll_timer.stop()
        if not self.save_now() and not dialogs.ask(
                self, tr("Заметки"), tr("Не удалось сохранить последние правки. Закрыть всё равно?")):
            self.poll_timer.start()
            event.ignore()
            return
        sounds.play("notes_close")
        event.accept()
