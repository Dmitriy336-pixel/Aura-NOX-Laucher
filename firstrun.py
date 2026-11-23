"""Окно первого запуска на PySide6: выбор языка, условия использования, короткая инструкция.
Показывается один раз (пока в settings.json нет terms_seen с текущей версией условий) и до главного окна:
выбранный язык сразу попадает в настройки, и главное окно стартует уже на нём.
Тексты лежат в legal.py. Условия только показываются: принимать их кнопкой не нужно, крестик тоже закрывает окно."""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QGuiApplication, QIcon
from PySide6.QtWidgets import (QDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

import i18n
import legal
import links
import storage
import theme
from config import APP_NAME, ICON_PATH

WIDTH, HEIGHT = 660, 560
_open_windows = []  # окна, открытые из команд и настроек: держим ссылки, пока они не закрыты


def dim():
    return theme.color("text_dim")


def accent():
    return theme.color("accent")


def center(window, width, height):
    window.resize(width, height)
    screen = QGuiApplication.primaryScreen().availableGeometry()
    window.move(screen.x() + (screen.width() - width) // 2, screen.y() + (screen.height() - height) // 2)


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


def terms_box(lang, parent=None):
    """Прокручиваемый текст условий (только для чтения), адрес источника кликабельный."""
    box = links.make_browser(parent)
    font = QFont(box.font())
    font.setPixelSize(14)
    box.setFont(font)
    links.fill_text(box, legal.terms_text(lang))
    return box


def guide_widget(lang, text_width=360):
    """Прокручиваемый список «клавиши — что делают»."""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    host = QWidget()
    grid = QGridLayout(host)
    grid.setContentsMargins(8, 8, 8, 8)
    grid.setColumnStretch(1, 1)
    for row, (keys, text) in enumerate(legal.pick(legal.GUIDE, lang)):
        key_label = QLabel(keys)
        key_label.setWordWrap(True)
        key_label.setFixedWidth(190)
        key_label.setStyleSheet(f"color: {accent()}; font-size: 14px; font-weight: bold;")
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        grid.addWidget(key_label, row, 0, Qt.AlignmentFlag.AlignTop)
        grid.addWidget(text_label, row, 1, Qt.AlignmentFlag.AlignTop)
    grid.setRowStretch(len(legal.pick(legal.GUIDE, lang)), 1)
    scroll.setWidget(host)
    return scroll


def apply_icon(window):
    try:
        import os
        if os.path.exists(ICON_PATH):
            window.setWindowIcon(QIcon(ICON_PATH))
    except Exception:  # noqa: BLE001
        pass


class Wizard(QDialog):
    PAGES = ("language", "terms", "guide")

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.lang = settings.get("language", i18n.DEFAULT)
        self.page = 0
        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(520, 440)
        center(self, WIDTH, HEIGHT)
        apply_icon(self)

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 18)
        self.body = QVBoxLayout()
        self.nav = QHBoxLayout()
        root.addLayout(self.body, 1)
        root.addLayout(self.nav)
        self.show_page()

    @property
    def ui(self):
        return legal.pick(legal.UI, self.lang)

    def show_page(self):
        clear_layout(self.body)
        clear_layout(self.nav)
        getattr(self, "build_" + self.PAGES[self.page])()
        self.build_nav()

    def heading(self, text):
        label = QLabel(text)
        label.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.body.addWidget(label)
        self.body.addSpacing(8)

    # --- страницы ---
    def build_language(self):
        self.heading(self.ui["language_title"])
        hint = QLabel(self.ui["language_hint"])
        hint.setStyleSheet(f"color: {dim()};")
        self.body.addWidget(hint)
        self.body.addSpacing(12)
        for code in i18n.LANGS:
            name = i18n.language_name(code, self.lang)
            chosen = code == self.lang
            btn = QPushButton(("✓  " if chosen else "") + name)
            btn.setMinimumHeight(56)
            btn.setStyleSheet("font-size: 18px;")
            if not chosen:
                btn.setProperty("ghost", True)
            btn.clicked.connect(lambda _=False, c=code: self.pick_language(c))
            self.body.addWidget(btn)
        self.body.addStretch(1)

    def pick_language(self, code):
        self.lang = code
        self.show_page()  # страница и кнопки сразу переходят на выбранный язык

    def build_terms(self):
        self.heading(self.ui["terms_title"])
        self.body.addWidget(terms_box(self.lang), 1)

    def build_guide(self):
        self.heading(self.ui["guide_title"])
        self.body.addWidget(guide_widget(self.lang), 1)

    # --- кнопки внизу ---
    def build_nav(self):
        total = len(self.PAGES)
        if self.page > 0:
            back = QPushButton(self.ui["back"])
            back.setProperty("ghost", True)
            back.setFixedWidth(110)
            back.clicked.connect(lambda: self.go(-1))
            self.nav.addWidget(back)
        else:
            spacer = QWidget()
            spacer.setFixedWidth(110)
            self.nav.addWidget(spacer)
        step = QLabel(self.ui["step"].format(n=self.page + 1, total=total))
        step.setAlignment(Qt.AlignmentFlag.AlignCenter)
        step.setStyleSheet(f"color: {dim()};")
        self.nav.addWidget(step, 1)
        last = self.page == total - 1
        nxt = QPushButton(self.ui["start"] if last else self.ui["next"])
        nxt.setFixedWidth(130)
        nxt.clicked.connect(self.finish if last else lambda: self.go(1))
        self.nav.addWidget(nxt)

    def go(self, step):
        self.page = max(0, min(len(self.PAGES) - 1, self.page + step))
        self.show_page()

    def finish(self):
        self.settings["language"] = self.lang
        self.settings["terms_seen"] = legal.TERMS_VERSION
        try:
            storage.save_settings(self.settings)
        except OSError:
            pass  # не записалось: окно просто покажется в следующий раз
        self.accept()

    def reject(self):  # крестик и Esc: просто продолжить
        self.finish()

    def closeEvent(self, event):
        self.finish()
        event.accept()


def needed(settings):
    return settings.get("terms_seen") != legal.TERMS_VERSION


def run(settings):
    """Показывает окно первого запуска и ждёт его закрытия. Язык и отметка о показе сохраняются в settings."""
    wizard = Wizard(settings)
    wizard.exec()
    wizard.deleteLater()


class _InfoWindow(QDialog):
    """Окно «текст + кнопка Закрыть»: общая основа для условий и инструкции. Показывается сразу при создании."""

    def __init__(self, master, title_key, build_body):
        super().__init__(master)
        lang = i18n.language()
        ui = legal.pick(legal.UI, lang)
        self.setWindowTitle(ui[title_key])
        self.setMinimumSize(480, 360)
        center(self, 620, 520)
        apply_icon(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 14)
        layout.addWidget(build_body(lang), 1)
        close = QPushButton(ui["close"])
        close.setFixedWidth(110)
        close.clicked.connect(self.close)
        layout.addWidget(close, 0, Qt.AlignmentFlag.AlignHCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        _open_windows.append(self)
        self.destroyed.connect(lambda *_: _open_windows.remove(self) if self in _open_windows else None)
        self.show()
        self.raise_()
        self.activateWindow()


class TermsWindow(_InfoWindow):
    """Условия использования в любой момент (команда «условия» и вкладка «О программе»)."""

    def __init__(self, master):
        super().__init__(master, "terms_title", terms_box)


class GuideWindow(_InfoWindow):
    """Короткая инструкция в любой момент (кнопка в «О программе»)."""

    def __init__(self, master):
        super().__init__(master, "guide_title", guide_widget)
