"""Раздел «Темы» в настройках (PySide6): карточки тем (картинка и название), добавление и создание темы,
перезапуск для применения."""
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QFileDialog, QGridLayout, QHBoxLayout, QInputDialog, QToolButton, QVBoxLayout, QWidget)

import dialogs
import sounds
import theme
import theme_tools
from i18n import tr
from ui_kit import button, clear_layout, label, open_folder

COLUMNS = 3
CARD_W, CARD_H = 140, 160
PREVIEW = 96


def short(title, limit=17):
    return title if len(title) <= limit else title[:limit - 1] + "…"


class ThemePage(QWidget):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        known = {folder for folder, _ in theme.list_themes()}
        self.selected = app.settings.get("theme_name", theme.DEFAULT_NAME)
        if self.selected not in known:
            self.selected = theme.DEFAULT_NAME  # выбранную тему удалили
        self.cards = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(label(
            tr("Нажми на карточку, чтобы выбрать тему. «✓» отмечает ту, что включена сейчас. "
               "Новая тема это папка в «themes»: скопируй её туда, добавь кнопкой «＋» или создай свою "
               "(получится копия с полным списком цветов, шрифтов и скруглений, останется поправить нужное). "
               "Выбранная тема применяется после перезапуска."), dim=True))
        self.grid = QGridLayout()
        self.grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        root.addLayout(self.grid)

        self.restart_btn = button(tr("Перезапустить и применить"), self.app.restart_with_theme, width=260)
        self.restart_btn.setEnabled(False)
        root.addWidget(self.restart_btn, 0, Qt.AlignmentFlag.AlignLeft)
        row = QHBoxLayout()
        row.addWidget(button(tr("Создать свою"), self.create, width=140))
        row.addWidget(button(tr("Папка тем"), self.open_folder, width=120))
        row.addWidget(button(tr("Обновить"), self.refresh, width=110))
        row.addStretch(1)
        root.addLayout(row)
        self.status = label("", dim=True)
        root.addWidget(self.status)
        self.render()

    # --- карточки ---
    def card(self, text, pixmap=None):
        btn = QToolButton()
        btn.setFixedSize(CARD_W, CARD_H)
        btn.setText(text)
        if pixmap is not None:
            btn.setIcon(QIcon(pixmap))
            btn.setIconSize(QSize(PREVIEW, PREVIEW))
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        else:
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        return btn

    def render(self):
        clear_layout(self.grid)
        self.cards = {}
        active = theme.current_name()
        themes = theme.list_themes()
        for i, (folder, title) in enumerate(themes):
            btn = self.card(("✓ " if folder == active else "") + short(title), theme_tools.preview(folder, PREVIEW))
            btn.clicked.connect(lambda _=False, f=folder: self.select(f))
            self.grid.addWidget(btn, i // COLUMNS, i % COLUMNS)
            self.cards[folder] = btn
        plus = self.card(tr("＋\nДобавить тему"))
        plus.setStyleSheet(f"QToolButton {{ border: 2px solid {theme.color('tile_border')}; "
                           f"background: transparent; font-size: 14px; }}")
        plus.clicked.connect(self.add)
        self.grid.addWidget(plus, len(themes) // COLUMNS, len(themes) % COLUMNS)
        self.paint_selection()

    def paint_selection(self):
        base = (f"QToolButton {{ background-color: {theme.color('card_bg')}; color: {theme.color('ghost_text')}; "
                f"border-radius: 6px; border: {{w}}px solid {{c}}; }}"
                f"QToolButton:hover {{ background-color: {theme.color('card_hover')}; }}")
        for folder, btn in self.cards.items():
            if folder == self.selected:
                btn.setStyleSheet(base.replace("{w}", "3").replace("{c}", theme.color("select_border")))
            else:
                btn.setStyleSheet(base.replace("{w}", "0").replace("{c}", "transparent"))

    def title_of(self, folder):
        return next((t for f, t in theme.list_themes() if f == folder), folder)

    # --- действия ---
    def select(self, folder):
        sounds.play("theme_select")
        self.selected = folder
        self.app.set_theme(folder)
        self.paint_selection()
        if folder == theme.current_name():
            self.restart_btn.setEnabled(False)
            self.status.setText(tr("Эта тема уже включена."))
        else:
            self.restart_btn.setEnabled(True)
            self.status.setText(tr('Выбрана «{v}». Нажми «Перезапустить и применить».', v=self.title_of(folder)))

    def add(self):
        src = QFileDialog.getExistingDirectory(self.window(), tr("Папка темы (в ней лежит theme.json)"))
        if not src:
            return
        name, error = theme_tools.add_theme(src)
        if error:
            dialogs.error(self.window(), tr("Тема"), error)
            return
        theme_tools.clear_previews()
        self.render()
        self.select(name)

    def create(self):
        title, ok = QInputDialog.getText(self.window(), tr("Создать тему"), tr("Название новой темы:"))
        if not ok:
            return
        name, error = theme_tools.create_theme(title)
        if error:
            dialogs.error(self.window(), tr("Тема"), error)
            return
        theme_tools.clear_previews()
        self.render()
        self.select(name)
        self.status.setText(tr(
            'Тема создана: themes\\{name}. Открой в ней theme.json, поменяй нужное, затем «Обновить» и «Перезапустить».',
            name=name))

    def refresh(self):
        theme_tools.clear_previews()
        self.render()
        self.status.setText(tr("Список обновлён."))

    def open_folder(self):
        try:
            open_folder(theme.THEMES_DIR)
        except (OSError, AttributeError) as e:
            dialogs.error(self.window(), tr("Тема"),
                          tr('Не удалось открыть папку:\n{THEMES_DIR}\n\n{e}', THEMES_DIR=theme.THEMES_DIR, e=e))
