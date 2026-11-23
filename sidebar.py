# sidebar.py
"""Правая узкая панель на PySide6. Кнопки управляются мышью и клавиатурой (Tab, стрелки, Enter).
Состояние «включена» задаётся свойством active (стиль QPushButton[active="true"] лежит в theme.py).
Если в теме есть texture_button.png, кнопка целиком становится картинкой (textures.py); иначе, если есть
sidebar_<имя>.png, значок-картинка лежит на цветной кнопке; ничего нет: цветная кнопка с символом."""

from PySide6.QtCore import Qt
from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QFont, QIcon, QPainter
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout

import sounds
import textures
import theme
from i18n import tr

MIN_WIDTH = 64  # кнопка 44 px + по 10 px отступа с каждой стороны
LOCK_ON_TEXT = tr("Плитки закреплены: перетаскивание выключено.\nНажми, чтобы включить")
LOCK_OFF_TEXT = tr("Плитки можно перетаскивать, чтобы менять местами.\nНажми, чтобы закрепить")


class SideButton(QPushButton):
    def __init__(self, text, font_size, parent=None, size=44):
        super().__init__(text, parent)
        self.px = size     # сторона кнопки: 44 на панели, меньше в командной строке
        self.glyph = text
        self.skin = None   # оформление с текстурой (если тема его даёт)
        self.state = {"active": False, "selected": False, "hover": False}
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # фокус клавиатуры всегда у главного окна
        self.setProperty("side", True)              # без внутренних отступов кнопки: значок помещается в 44 px
        font = QFont(theme.ICON_FONT if text != ">_" else self.font().family())
        font.setPixelSize(font_size)
        if text == ">_":
            font.setBold(True)
        self.setFont(font)

    def enterEvent(self, event):
        sounds.play("hover")
        self.set_state(hover=True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.set_state(hover=False)
        super().leaveEvent(event)

    def set_state(self, **changes):
        if all(self.state[key] == value for key, value in changes.items()):
            return
        self.state.update(changes)
        if self.skin is not None:
            self.draw()

    def draw(self):
        """Перерисовать кнопку с текстурой: картинка по состоянию (включена важнее наведения)."""
        self.update()

    def paintEvent(self, event):
        if self.skin is None:
            super().paintEvent(event)
            return
        state = self.state
        kind = "active" if state["active"] else ("hover" if state["hover"] else "normal")
        pixmap = self.skin.image(kind, state["selected"])
        if pixmap is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        shown = self.skin.shown
        offset = (self.width() - shown) // 2  # отступ от края (shapes.texture_inset), картинка по центру
        p.drawPixmap(QRect(offset, offset, shown, shown), pixmap)

    def apply_texture(self, name):
        """Оформление из выбранной темы (см. описание модуля)."""
        self.skin = textures.skin(name, self.glyph, self.px)
        if self.skin is not None:
            self.setText("")
            self.setStyleSheet("QPushButton { background: transparent; border: none; }")
            self.draw()
            return
        self.setStyleSheet("")
        pixmap = theme.image("sidebar_" + name, 30)
        if pixmap is not None:
            self.setText("")
            self.setIcon(QIcon(pixmap))
            self.setIconSize(QSize(30, 30))


class Sidebar(QFrame):
    def __init__(self, parent, on_settings, on_command, on_perf, on_notes, on_lock, width):
        super().__init__(parent)
        self.setFixedWidth(max(width, MIN_WIDTH))
        self.setStyleSheet(f"Sidebar {{ background-color: {theme.color('panel_bg')}; border-radius: 0px; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 10, 0, 10)
        layout.setSpacing(10)
        layout.addStretch(1)  # пустое место сверху прижимает кнопки вниз

        self.command_btn = SideButton(">_", 16, self)
        self.notes_btn = SideButton("✎", 22, self)
        self.lock_btn = SideButton("⇅", 22, self)
        self.perf_btn = SideButton("⚡", 20, self)
        self.settings_btn = SideButton("⚙", 22, self)
        callbacks = {
            "command": on_command, "notes": on_notes, "lock": on_lock,
            "perf": on_perf, "settings": on_settings,
        }
        # Кнопки сверху вниз по именам; спрятать можно любую, кроме настроек
        self.named = {
            "command": self.command_btn, "notes": self.notes_btn, "lock": self.lock_btn,
            "perf": self.perf_btn, "settings": self.settings_btn,
        }
        for name, btn in self.named.items():
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            btn.clicked.connect(lambda _checked=False, f=callbacks[name]: f())
        self.lock_btn.setToolTip(LOCK_OFF_TEXT)

        self.visible = {name: True for name in self.named}
        self.buttons = list(self.named.values())  # видимые кнопки по порядку: по ним ходят стрелками
        self.apply_textures()

    def apply_textures(self):
        """Заново подобрать оформление кнопок (при старте и после смены светлой/тёмной темы)."""
        for name, btn in self.named.items():
            btn.apply_texture(name)
        self.setStyleSheet(f"Sidebar {{ background-color: {theme.color('panel_bg')}; border-radius: 0px; }}")

    def set_width(self, width):
        self.setFixedWidth(max(width, MIN_WIDTH))

    def set_button_visible(self, name, visible):
        """Показать или спрятать кнопку панели: "command", "notes", "lock" или "perf"."""
        self.visible[name] = visible
        self.named[name].setVisible(visible)
        self.buttons = [btn for key, btn in self.named.items() if self.visible[key]]

    def set_command_visible(self, visible):
        """Кнопка командной строки есть, только пока строка включена."""
        self.set_button_visible("command", visible)

    def _repolish(self, button):
        style = button.style()
        style.unpolish(button)
        style.polish(button)
        button.update()

    def set_button_active(self, button, is_active):
        """Подсветка кнопки, пока её функция включена (цвет «active» темы)."""
        button.setProperty("active", bool(is_active))
        button.set_state(active=bool(is_active))
        self._repolish(button)

    def set_perf_active(self, is_active):
        self.set_button_active(self.perf_btn, is_active)

    def set_lock_active(self, locked):
        """Подсветка кнопки блокировки и текст её подсказки."""
        self.set_button_active(self.lock_btn, locked)
        self.lock_btn.setToolTip(LOCK_ON_TEXT if locked else LOCK_OFF_TEXT)

    def select(self, index):
        """Рамка выбора вокруг кнопки номер index; None снимает рамку."""
        if index is not None:
            index = min(index, len(self.buttons) - 1)  # кнопок могло стать меньше
        light = theme.current_mode() == "light"
        for i, btn in enumerate(self.buttons):
            if btn.skin is not None:
                btn.set_state(selected=(i == index))  # у кнопки с текстурой рамка нарисована в самой картинке
            elif i == index:
                width = 4 if light else 3  # на светлой теме толще
                btn.setStyleSheet(f"border: {width}px solid {theme.color('select_border')};")
            else:
                btn.setStyleSheet("")

    def press(self, index):
        self.buttons[min(index, len(self.buttons) - 1)].click()
