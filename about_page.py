"""Раздел «О программе» в настройках (PySide6): автор, версия, условия, где лежат данные, из чего собрана программа
и сведения для сообщения об ошибке (копируются одной кнопкой)."""
import os
import platform
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QHBoxLayout, QPlainTextEdit, QVBoxLayout, QWidget
from shiboken6 import isValid

import firstrun
import i18n
import legal
import links
import sounds
import theme
from config import APP_NAME, BASE_DIR, ICON_PATH, VERSION
from i18n import tr
from notes_store import default_dir
from ui_kit import button, label, open_folder

# сторонние компоненты: (название, лицензия, имя модуля для версии)
COMPONENTS = [("Python", "PSF", None), ("PySide6 (Qt)", "LGPL", "PySide6"), ("Pillow", "HPND", "PIL")]

# материалы других авторов, которых лицензия требует указывать
CREDITS = [
    ("Звуковые эффекты интерфейса", "Universal UI Soundpack", "Nathan Gibson",
     "https://nathangibson.myportfolio.com", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
]


def version_of(module_name):
    if module_name is None:
        return platform.python_version()
    try:
        return getattr(__import__(module_name), "__version__", "")
    except ImportError:
        return ""


class AboutPage(QWidget):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        lang = i18n.language()
        self.root = QVBoxLayout(self)
        self.root.setContentsMargins(0, 0, 0, 0)
        self.build_header(lang)
        self.section(tr("О программе"))
        self.root.addWidget(label(tr("Лаунчер для Windows: плитки программ, командная строка, заметки, темы и звуки."),
                                  dim=True))
        self.section(tr("Условия"))
        self.root.addWidget(label(
            tr("Программа бесплатна. Продавать её и просить за неё донаты нельзя. Менять и раздавать можно "
               "бесплатно. Оригинал только от автора: за версии из других источников и за добавленный в них "
               "код автор не отвечает."), dim=True))
        row = QHBoxLayout()
        row.addWidget(button(tr("Условия использования"),
                             lambda: firstrun.TermsWindow(self.window()), width=190))
        row.addWidget(button(tr("Как пользоваться"),
                             lambda: firstrun.GuideWindow(self.window()), width=150))
        row.addStretch(1)
        self.root.addLayout(row)
        self.build_folders()
        self.build_components()
        self.build_system()

    def section(self, title):
        lab = label(title, bold=True, size=16)
        lab.setContentsMargins(0, 14, 0, 2)
        self.root.addWidget(lab)

    def build_header(self, lang):
        head = QHBoxLayout()
        if os.path.exists(ICON_PATH):
            # QPixmap(путь к .ico) берёт самый маленький размер из файла; QIcon выбирает нужный и даёт крупный
            pm = QIcon(ICON_PATH).pixmap(256, 256)
            if not pm.isNull():
                pic = label("", wrap=False)
                pic.setPixmap(pm.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio,
                                        Qt.TransformationMode.SmoothTransformation))
                pic.setFixedSize(80, 80)
                pic.setScaledContents(True)
                head.addWidget(pic, 0, Qt.AlignmentFlag.AlignTop)
        info = QVBoxLayout()
        info.addWidget(label(APP_NAME, bold=True, size=24, wrap=False))
        info.addWidget(label(tr("Версия {version}", version=VERSION), dim=True))
        info.addWidget(label(tr("Автор: {author}", author=legal.pick(legal.AUTHOR, lang)), dim=True))
        info.addWidget(links.linked_label(
            tr("Официальный источник: {source}", source=legal.pick(legal.SOURCE, lang)),
            color=theme.color("text_dim")))
        head.addLayout(info, 1)
        self.root.addLayout(head)

    def build_folders(self):
        self.section(tr("Где лежат данные"))
        notes = self.app.settings.get("notes_dir") or default_dir()
        rows = [
            (tr("Лаунчер, плитки и настройки"), BASE_DIR),
            (tr("Заметки"), notes),
            (tr("Темы"), theme.THEMES_DIR),
            (tr("Звуки"), sounds.SOUNDS_DIR),
        ]
        for title, path in rows:
            row = QHBoxLayout()
            name = label(title, wrap=False)
            name.setFixedWidth(170)
            row.addWidget(name)
            row.addWidget(label(path, dim=True), 1)

            def open_it(p=path):
                try:
                    open_folder(p)
                except OSError:
                    pass
            row.addWidget(button(tr("Открыть"), open_it, width=90))
            self.root.addLayout(row)

    def build_components(self):
        self.section(tr("Из чего сделано"))
        self.root.addWidget(label(
            tr("Программа использует сторонние компоненты со своими лицензиями. Темы, звуки и иконки, "
               "которые вы добавляете, остаются собственностью их авторов."), dim=True))
        for name, licence, module in COMPONENTS:
            version = version_of(module)
            self.root.addWidget(label(f"•  {name} {version} ({licence})".replace("  (", " ("), accent=True))
        for what, title, author, site, licence, licence_url in CREDITS:
            self.root.addWidget(label(f"{tr(what)}: {title}"))
            row = QHBoxLayout()
            row.addWidget(label(f"{tr('Автор')}: {author}  ({licence})", accent=True, wrap=False))
            row.addWidget(button(tr("Сайт автора"), lambda u=site: links.open_url(u), width=110))
            row.addWidget(button(tr("Лицензия"), lambda u=licence_url: links.open_url(u), width=100))
            row.addStretch(1)
            self.root.addLayout(row)

    def system_info(self):
        s = self.app.settings
        return "\n".join([
            f"{APP_NAME} {VERSION}",
            f"Python {platform.python_version()} ({platform.architecture()[0]})",
            f"PySide6 {version_of('PySide6')}, Pillow {version_of('PIL')}",
            f"Windows: {platform.platform()}",
            f"Language: {i18n.language()}",
            f"Theme: {s.get('theme_name', 'default')} ({s.get('theme_mode', 'dark')})",
            f"Frozen exe: {bool(getattr(sys, 'frozen', False))}",
        ])

    def build_system(self):
        self.section(tr("Сведения для сообщения об ошибке"))
        self.root.addWidget(label(tr("Если что-то не работает, скопируйте это и приложите к сообщению."), dim=True))
        box = QPlainTextEdit(self.system_info())
        box.setReadOnly(True)
        box.setFixedHeight(130)
        box.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.root.addWidget(box)
        self.copy_btn = button(tr("Скопировать"), self.copy, width=140)
        self.root.addWidget(self.copy_btn, 0, Qt.AlignmentFlag.AlignLeft)

    def copy(self):
        QApplication.clipboard().setText(self.system_info())
        sounds.play("copied")
        self.copy_btn.setText(tr("Скопировано"))
        QTimer.singleShot(1500, lambda: isValid(self.copy_btn) and self.copy_btn.setText(tr("Скопировать")))
