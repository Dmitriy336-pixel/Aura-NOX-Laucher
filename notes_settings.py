"""Блок «Хранение» в разделе «Заметки» настроек (PySide6): где лежат заметки, смена папки с переносом, открыть папку."""
import os

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QVBoxLayout, QWidget

import dialogs
from i18n import tr
from notes_store import NoteStore, default_dir
from ui_kit import button, label, open_folder


class NotesFolderPage(QWidget):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(label(
            tr("Заметки это обычные файлы .md в одной папке: их можно открыть и в других программах. "
               "При смене папки лаунчер предложит скопировать в неё уже существующие заметки."), dim=True))
        self.path_label = label("")
        root.addWidget(self.path_label)
        row = QHBoxLayout()
        row.addWidget(button(tr("Выбрать папку…"), self.choose, width=160))
        row.addWidget(button(tr("Открыть"), self.open_folder, width=110))
        row.addWidget(button(tr("По умолчанию"), self.reset, width=140))
        row.addStretch(1)
        root.addLayout(row)
        self.show_path()

    def current(self):
        return self.app.settings.get("notes_dir") or default_dir()

    def show_path(self):
        self.path_label.setText(self.current())

    def switch_to(self, folder):
        """Меняет папку; если в прежней есть заметки, предлагает скопировать их в новую."""
        top = self.window()
        old = self.current()
        if folder is not None and os.path.normcase(os.path.abspath(folder)) == os.path.normcase(os.path.abspath(old)):
            return
        target = folder if folder is not None else default_dir()
        try:
            old_notes = NoteStore(old).list_notes()
        except OSError:
            old_notes = []
        if old_notes and dialogs.ask(
                top, tr("Заметки"),
                tr('Скопировать заметки ({v}) из прежней папки в новую?\nОдноимённые заметки в новой папке не будут перезаписаны.',
                   v=len(old_notes))):
            try:
                copied, skipped = NoteStore(old).copy_notes_to(target)
            except OSError as e:
                dialogs.error(top, tr("Заметки"), tr('Не удалось скопировать:\n{e}', e=e))
                return
            if skipped:
                dialogs.info(top, tr("Заметки"),
                             tr('Скопировано: {copied}. Пропущено одноимённых: {skipped}.',
                                copied=copied, skipped=skipped))
        if self.app.change_notes_dir(folder):
            self.show_path()

    def choose(self):
        folder = QFileDialog.getExistingDirectory(self.window(), tr("Папка для заметок"), self.current())
        if folder:
            self.switch_to(os.path.normpath(folder))

    def reset(self):
        self.switch_to(None)

    def open_folder(self):
        try:
            open_folder(self.current())
        except (OSError, AttributeError) as e:
            dialogs.error(self.window(), tr("Заметки"), tr('Не удалось открыть папку:\n{v}\n\n{e}', v=self.current(), e=e))
