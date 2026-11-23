"""Страница «Команды» в настройках (PySide6): список своих команд и окно создания и правки."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QPlainTextEdit,
                               QPushButton, QVBoxLayout, QWidget)

import dialogs
import theme
import user_commands as uc
from i18n import tr
from ui_kit import Segmented, button, clear_layout, label

HINTS = {
    "open": tr("Один путь или адрес сайта. {} подставит текст, введённый после команды."),
    "set": tr("По одному пути или адресу в строке: всё откроется по очереди."),
    "shell": tr("Команда командной строки Windows, выполняется без окна. {} подставит текст после команды."),
}


class CommandsPage(QWidget):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(label(
            tr("Свои команды для командной строки: открывают программы, папки и сайты или "
               "выполняют команды. Пример: команда «ютуб» с адресом "
               "https://www.youtube.com/results?search_query={} ищет на YouTube то, что напишешь дальше."), dim=True))
        root.addWidget(button(tr("Новая команда"), self.add, width=170), 0, Qt.AlignmentFlag.AlignLeft)
        self.list = QVBoxLayout()
        root.addLayout(self.list)
        self.render()

    def render(self):
        clear_layout(self.list)
        entries = uc.load()
        if not entries:
            self.list.addWidget(label(tr("Пока нет своих команд."), dim=True))
        for index, entry in enumerate(entries):
            card = QFrame()
            card.setProperty("card", True)
            grid = QGridLayout(card)
            grid.setColumnStretch(0, 1)
            grid.addWidget(label(", ".join(entry["names"]), accent=True, bold=True, size=14), 0, 0)
            grid.addWidget(label(f'{uc.ACTIONS.get(entry["action"], "?")}: {uc.summary(entry)}', dim=True), 1, 0)
            grid.addWidget(button(tr("Изменить"), lambda i=index: self.edit(i), width=90), 0, 1, 2, 1)
            grid.addWidget(button(tr("Удалить"), lambda i=index: self.delete(i), width=90, danger=True), 0, 2, 2, 1)
            self.list.addWidget(card)

    def add(self):
        CommandEditor(self.window(), self.app, None, self.saved).open()

    def edit(self, index):
        CommandEditor(self.window(), self.app, index, self.saved).open()

    def delete(self, index):
        entries = uc.load()
        names = ", ".join(entries[index]["names"])
        if not dialogs.ask(self.window(), tr("Удаление команды"), tr('Удалить команду «{names}»?', names=names)):
            return
        del entries[index]
        uc.save(entries)
        self.saved()

    def saved(self):
        self.app.reload_commands()  # командная строка сразу узнаёт об изменениях
        self.render()


class CommandEditor(QDialog):
    def __init__(self, master, app, index, on_saved):
        super().__init__(master)
        self.app, self.index, self.on_saved = app, index, on_saved
        entries = uc.load()
        entry = entries[index] if index is not None else {"names": [], "description": "", "action": "open", "target": ""}
        self.other_names = {n for i, e in enumerate(entries) if i != index for n in e["names"]}
        self.action_key = entry["action"] if entry["action"] in uc.ACTIONS else "open"

        self.setWindowTitle(tr("Новая команда") if index is None else tr("Правка команды"))
        self.resize(540, 520)
        self.setMinimumSize(480, 480)
        self.setModal(True)

        root = QVBoxLayout(self)
        root.addWidget(label(tr("Названия через запятую (можно русские и английские)")))
        self.names = QLineEdit(", ".join(entry["names"]))
        self.names.setPlaceholderText(tr("например: ютуб, yt"))
        root.addWidget(self.names)
        root.addWidget(label(tr("Описание (необязательно, видно в «помощь»)")))
        self.description = QLineEdit(entry.get("description", ""))
        root.addWidget(self.description)

        root.addWidget(label(tr("Что делает")))
        self.kind_seg = Segmented(uc.ACTIONS, self.action_key, self.kind_changed)
        seg = QHBoxLayout()
        seg.addWidget(self.kind_seg)
        seg.addStretch(1)
        root.addLayout(seg)
        self.hint = label("", dim=True)
        root.addWidget(self.hint)
        self.target = QPlainTextEdit(entry["target"])
        self.target.setFixedHeight(100)
        root.addWidget(self.target)

        self.pick_row = QWidget()
        pr = QHBoxLayout(self.pick_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.addWidget(button(tr("Выбрать файл…"), self.pick_file, width=150))
        pr.addWidget(button(tr("Выбрать папку…"), self.pick_folder, width=150))
        pr.addStretch(1)
        root.addWidget(self.pick_row)

        self.error = label("")
        self.error.setStyleSheet(f"color: {theme.color('error')};")
        root.addWidget(self.error)
        root.addStretch(1)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(button(tr("Отмена"), self.reject, width=100, ghost=True))
        buttons.addWidget(button(tr("Сохранить"), self.save, width=120))
        root.addLayout(buttons)
        self.kind_changed(self.action_key)
        self.names.setFocus()

    def action(self):
        return self.action_key

    def kind_changed(self, key):
        self.action_key = key
        self.kind_seg.set(key)
        self.hint.setText(HINTS[key])
        self.pick_row.setVisible(key != "shell")

    def add_path(self, path):
        text = self.target.toPlainText().strip()
        if self.action() == "set" and text:
            self.target.appendPlainText(path)  # в наборе каждая запись с новой строки
        else:
            self.target.setPlainText(path)

    def pick_file(self):
        path, _ = QFileDialog.getOpenFileName(self, tr("Выбери программу или файл"))
        if path:
            self.add_path(path.replace("/", "\\"))

    def pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, tr("Выбери папку"))
        if path:
            self.add_path(path.replace("/", "\\"))

    def save(self):
        entry = {
            "names": uc.parse_names(self.names.text()),
            "description": self.description.text().strip(),
            "action": self.action(),
            "target": self.target.toPlainText().strip(),
        }
        problem = uc.validate(entry, self.other_names, self.app.registry.builtin_names)
        if problem:
            self.error.setText(problem)
            return
        entries = uc.load()
        if self.index is None:
            entries.append(entry)
        else:
            entries[self.index] = entry
        uc.save(entries)
        self.accept()
        self.on_saved()
