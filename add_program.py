"""Окно «Добавить программу». Вводишь название, список сразу сужается (ярлыки из «Пуска» и программы из реестра).
Не нашлось: кнопка «Искать на диске» обходит папки с программами. Остался и обычный выбор файла: кнопка «Обзор…».
Выбранные программы лежат в dialog.chosen как список пар (название, путь)."""
import os
import threading

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QDialog, QFileDialog, QHBoxLayout, QLineEdit,
                               QListWidget, QListWidgetItem, QPushButton, QVBoxLayout)

import programs
from i18n import tr
from ui_kit import button, label


def pick_program_file(parent):
    """Обычный выбор файла программы. Возвращает путь или пустую строку, если отменили."""
    path, _ = QFileDialog.getOpenFileName(
        parent, tr("Выбери программу"), "",
        f"{tr('Программы и ярлыки')} (*.exe *.lnk *.bat);;{tr('Все файлы')} (*.*)")
    return os.path.normpath(path) if path else ""


class _Bridge(QObject):
    """Передаёт результаты из потока поиска в окно: сигналы сами переходят в главный поток."""
    found = Signal(object)
    done = Signal()


class AddProgramDialog(QDialog):
    def __init__(self, parent, existing_targets):
        super().__init__(parent)
        self.setWindowTitle(tr("Добавить программу"))
        self.resize(560, 520)
        self.chosen = []
        self.existing = {os.path.normcase(os.path.normpath(p)) for p in existing_targets if p}
        self.installed = programs.scan()  # быстро: ярлыки и реестр
        self.from_disk = []               # найденное кнопкой «Искать на диске»
        self.cancel = threading.Event()   # останавливает поиск на диске, когда окно закрыто
        self.searching = False
        self.bridge = _Bridge()
        self.bridge.found.connect(self.on_found)
        self.bridge.done.connect(self.on_done)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        self.entry = QLineEdit()
        self.entry.setPlaceholderText(tr("Начни вводить название программы"))
        self.entry.textChanged.connect(self.refill)
        self.entry.returnPressed.connect(self.accept_selected)
        self.entry.installEventFilter(self)  # стрелки вверх и вниз двигают выбор в списке прямо из поля
        layout.addWidget(self.entry)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # несколько сразу: Ctrl, Shift
        self.list.itemDoubleClicked.connect(lambda _item: self.accept_selected())
        self.list.itemSelectionChanged.connect(self.show_path)
        layout.addWidget(self.list, 1)

        self.status = label("", dim=True)
        layout.addWidget(self.status)

        row = QHBoxLayout()
        self.disk_btn = button(tr("Искать на диске"), self.search_disk, ghost=True)
        row.addWidget(self.disk_btn)
        row.addWidget(button(tr("Обзор…"), self.browse, ghost=True))
        row.addStretch(1)
        row.addWidget(button(tr("Отмена"), self.reject, ghost=True))
        row.addWidget(button(tr("Добавить"), self.accept_selected))
        layout.addLayout(row)
        for btn in self.findChildren(QPushButton):
            btn.setAutoDefault(False)  # Enter обрабатывает поле ввода, а не случайная кнопка

        self.refill()
        self.entry.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.entry and event.type() == QEvent.Type.KeyPress \
                and event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            QApplication.sendEvent(self.list, event)
            return True
        return super().eventFilter(obj, event)

    # --- список ---
    def refill(self, *_):
        query = self.entry.text()
        shown = programs.search(self.installed + self.from_disk, query)
        self.list.clear()
        for prog in shown:
            exists = os.path.normcase(os.path.normpath(prog.path)) in self.existing
            item = QListWidgetItem(prog.name + (tr(" (уже в плитках)") if exists else ""))
            item.setData(Qt.ItemDataRole.UserRole, (prog.name, prog.path))
            item.setToolTip(prog.path)
            self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)  # Enter сразу добавит лучшее совпадение
            self.show_path()
        elif query.strip():
            self.status.setText(tr("Ничего не найдено. Попробуй «Искать на диске» или «Обзор…»"))
        else:
            self.status.setText("")

    def show_path(self):
        item = self.list.currentItem()
        if item is not None:
            self.status.setText(item.data(Qt.ItemDataRole.UserRole)[1])

    # --- результат ---
    def accept_selected(self):
        if self.chosen:
            return  # Enter мог сработать дважды
        items = self.list.selectedItems() or ([self.list.currentItem()] if self.list.currentItem() else [])
        self.chosen = [tuple(item.data(Qt.ItemDataRole.UserRole)) for item in items]
        if self.chosen:
            self.accept()

    def browse(self):
        path = pick_program_file(self)
        if path:
            self.chosen = [(os.path.splitext(os.path.basename(path))[0], path)]
            self.accept()

    def done(self, result):
        self.cancel.set()  # поиск на диске остановится сам
        super().done(result)

    # --- поиск на диске ---
    def search_disk(self):
        query = self.entry.text().strip()
        if not query:
            self.status.setText(tr("Введи название программы, чтобы искать на диске"))
            return
        if self.searching:
            return
        self.searching = True
        self.found_count = 0
        self.disk_btn.setEnabled(False)
        self.status.setText(tr("Ищу на диске…"))
        threading.Thread(target=self.run_disk, args=(query,), daemon=True).start()

    def run_disk(self, query):
        try:
            for prog in programs.walk_disk(query, self.cancel):
                self.bridge.found.emit(prog)
        finally:
            self.bridge.done.emit()

    def on_found(self, prog):
        known = {p.path.lower() for p in self.installed + self.from_disk}
        if prog.path.lower() in known:
            return
        self.from_disk.append(prog)
        self.found_count += 1
        self.refill()

    def on_done(self):
        self.searching = False
        self.disk_btn.setEnabled(True)
        self.status.setText(tr("Поиск на диске завершён, найдено: {n}", n=self.found_count))
