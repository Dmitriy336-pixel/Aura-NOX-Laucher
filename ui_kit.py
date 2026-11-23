"""Мелкие общие помощники для окон на PySide6: подписи, кнопки, перерисовка стиля, очистка раскладки, открыть папку."""
import os

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QPushButton

import theme


def repolish(widget):
    """Применить QSS заново после смены свойства (active, ghost, selected...)."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            clear_layout(item.layout())


def label(text, dim=False, accent=False, bold=False, size=None, wrap=True):
    lab = QLabel(text)
    lab.setWordWrap(wrap)
    if dim:
        lab.setProperty("dim", True)
    if accent:
        lab.setProperty("accent", True)
    parts = []
    if bold:
        parts.append("font-weight: bold;")
    if size:
        parts.append(f"font-size: {size}px;")
    if parts:
        lab.setStyleSheet(" ".join(parts))
    return lab


def button(text, callback=None, width=None, ghost=False, danger=False, compact=False):
    btn = QPushButton(text)
    if compact:
        btn.setProperty("compact", True)
    if width:
        btn.setFixedWidth(width)
    if ghost:
        btn.setProperty("ghost", True)
    if danger:
        btn.setProperty("danger", True)
    if callback is not None:
        btn.clicked.connect(lambda _=False: callback())
    return btn


def open_folder(path):
    """Открывает папку в проводнике (создаёт, если ещё нет). Бросает OSError."""
    os.makedirs(path, exist_ok=True)
    os.startfile(path)  # только Windows


class Switch(QCheckBox):
    """Переключатель-тумблер как у customtkinter: дорожка 36x18, круглый бегунок, подпись справа."""
    W, H, GAP = 36, 18, 8

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self):
        fm = self.fontMetrics()
        extra = self.GAP + fm.horizontalAdvance(self.text()) + 2 if self.text() else 0
        return QSize(self.W + extra, max(self.H + 4, fm.height() + 4))

    def minimumSizeHint(self):
        return self.sizeHint()

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        y = (self.height() - self.H) / 2
        on = self.isChecked()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(theme.color("button" if on else "switch_off")))
        p.drawRoundedRect(QRectF(0, y, self.W, self.H), self.H / 2, self.H / 2)
        knob = self.H - 4
        x = self.W - knob - 2 if on else 2
        p.setBrush(QColor("#ffffff"))
        p.drawEllipse(QRectF(x, y + 2, knob, knob))
        if self.text():
            p.setPen(QColor(theme.color("text")))
            p.drawText(QRectF(self.W + self.GAP, 0, self.width() - self.W - self.GAP, self.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


class Segmented(QFrame):
    """Выбор из вариантов в одной плашке (как CTkSegmentedButton): выбранный вариант цветной, остальные серые."""

    def __init__(self, options, current, on_pick, parent=None):
        super().__init__(parent)
        self.setProperty("seg", True)
        self.on_pick = on_pick  # on_pick(значение)
        self.buttons = {}
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(0)
        for value, text in options.items():
            btn = QPushButton(text)
            btn.setProperty("seg", True)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(lambda _=False, v=value: self._clicked(v))
            lay.addWidget(btn)
            self.buttons[value] = btn
        self.set(current)

    def set(self, value):
        for v, btn in self.buttons.items():
            btn.setProperty("active", v == value)
            repolish(btn)

    def _clicked(self, value):
        self.set(value)
        self.on_pick(value)
