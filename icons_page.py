"""Блок «Иконки плиток» в настройках (PySide6). Раньше был IconsPage внутри icon_tools.py,
patch_icon_tools.py его вырезал: теперь он живёт здесь."""
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

import dialogs
from i18n import tr
from icon_tools import ICON_PACK_DIR
from ui_kit import button, label, open_folder


class IconsPage(QWidget):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(label(
            tr("Иконка подбирается так: сначала из папки готовых иконок, потом из самой программы. "
               "Готовая иконка это файл с именем программы: obs.png подойдёт к obs64.exe. "
               "Одной плитке можно подобрать иконку правым кликом: «Подобрать иконку»."), dim=True))
        row = QHBoxLayout()
        row.addWidget(button(tr("Подобрать плиткам без иконки"), self.fill_missing, width=270))
        row.addWidget(button(tr("Папка готовых иконок"), self.open_pack, width=210))
        row.addStretch(1)
        root.addLayout(row)
        self.status = label("", dim=True)
        root.addWidget(self.status)

    def fill_missing(self):
        done, total = self.app.fill_missing_icons()
        if total == 0:
            self.status.setText(tr("У всех плиток уже есть иконки."))
        else:
            self.status.setText(tr('Подобрано иконок: {done} из {total}.', done=done, total=total))

    def open_pack(self):
        try:
            open_folder(ICON_PACK_DIR)
        except (OSError, AttributeError) as e:
            dialogs.error(self.window(), tr("Иконки"),
                          tr('Не удалось открыть папку:\n{ICON_PACK_DIR}\n\n{e}', ICON_PACK_DIR=ICON_PACK_DIR, e=e))
