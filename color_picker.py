# color_picker.py
"""Цвет плиток: окно выбора цвета для одной плитки и блок «Цвета плиток» в настройках (PySide6)."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QColorDialog, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

import dialogs
import sounds
import theme
from config import COLORS, TILE_PALETTE
from i18n import tr

PER_ROW = 7  # цветов палитры в строке


def palette():
    """Цвета плиток из темы и дополнительные."""
    return list(theme.CURRENT_TILE_COLORS) + TILE_PALETTE[len(COLORS):]


class ColorPicker(QDialog):
    """Палитра: нажал на цвет, и плитка перекрашена. «Другой цвет…» открывает системный выбор."""

    def __init__(self, master, name, current, on_pick):
        super().__init__(master)
        self.on_pick = on_pick  # on_pick("#rrggbb")
        self.current = (current or "").lower()

        self.setWindowTitle(tr("Цвет плитки"))
        self.setModal(True)
        self.setFixedSize(380, 250)

        layout = QVBoxLayout(self)
        title = QLabel(name)
        title.setWordWrap(True)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setSpacing(8)
        for i, color in enumerate(palette()):
            btn = QPushButton()
            btn.setFixedSize(40, 40)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            border = f"3px solid {theme.color('select_border')}" if color.lower() == self.current else "none"
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color}; border: {border}; }}"
                f"QPushButton:hover {{ background-color: {QColor(color).lighter(115).name()}; }}")
            btn.clicked.connect(lambda _=False, c=color: self.pick(c))
            grid.addWidget(btn, i // PER_ROW, i % PER_ROW)
        layout.addWidget(grid_host, 0, Qt.AlignmentFlag.AlignHCenter)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        other = QPushButton(tr("Другой цвет…"))
        other.clicked.connect(self.custom)
        cancel = QPushButton(tr("Отмена"))
        cancel.setProperty("ghost", True)
        cancel.clicked.connect(self.reject)
        buttons.addWidget(other)
        buttons.addWidget(cancel)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    def pick(self, color):
        sounds.play("color_set")
        self.accept()
        self.on_pick(color)

    def custom(self):
        chosen = QColorDialog.getColor(QColor(self.current) if self.current else QColor("#2d6a4f"),
                                       self, tr("Цвет плитки"))
        if chosen.isValid():
            self.pick(chosen.name())


class TileColorsPage(QWidget):
    """Блок настроек: перекрасить сразу все плитки. Цвет одной плитки: правый клик по ней, «Цвет…»."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        hint = QLabel(tr("Цвет одной плитки: правый клик по ней, пункт «Цвет…». Цвет плитки не меняется "
                         "при перетаскивании. Новые плитки получают цвета палитры по кругу, а после «Одного цвета для всех» "
                         "этот цвет, пока не нажмёшь «Палитра по порядку». При смене темы лаунчер спросит, "
                         "перекрасить ли плитки."))
        hint.setWordWrap(True)
        hint.setProperty("dim", True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        by_palette = QPushButton(tr("Палитра по порядку"))
        by_palette.clicked.connect(self.by_palette)
        one = QPushButton(tr("Один цвет для всех…"))
        one.clicked.connect(self.one_color)
        row.addWidget(by_palette)
        row.addWidget(one)
        row.addStretch(1)
        layout.addLayout(row)

    def confirm(self):
        return dialogs.ask(self.window(), tr("Цвета плиток"),
                           tr("Все плитки будут перекрашены, прежние цвета пропадут.\nПродолжить?"))

    def by_palette(self):
        if self.confirm():
            self.app.recolor_tiles(None)

    def one_color(self):
        chosen = QColorDialog.getColor(QColor("#2d6a4f"), self.window(), tr("Цвет для всех плиток"))
        if chosen.isValid() and self.confirm():
            self.app.recolor_tiles(chosen.name())
