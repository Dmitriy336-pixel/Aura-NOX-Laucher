"""Вкладка «Управление» в настройках (PySide6): справочник клавиш и смена быстрых клавиш плиток.
Логика назначения клавиш лежит в tile_keys.py."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

import dialogs
import theme
from i18n import tr
from ui_kit import button, clear_layout, label

MODIFIER_KEYS = {Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta,
                 Qt.Key.Key_AltGr, Qt.Key.Key_CapsLock, Qt.Key.Key_NumLock}

# Справочник: группа -> (клавиши, что делают). Меняешь текст здесь, и он меняется в настройках.
SHORTCUTS = [
    (tr("Главное окно"), [
        ("Arrow Keys", tr("выбрать плитку; на панели справа Up Arrow / Down Arrow выбирают кнопку, Left Arrow возвращает к плиткам")),
        ("Tab", tr("перенести выбор между плитками и панелью справа")),
        ("Enter", tr("запустить выбранную плитку, добавить программу на «+» / открыть поиск на лупе или нажать выбранную кнопку панели")),
        (tr("Клавиша плитки"), tr("сразу запускает плитку (клавиша написана на плитке, сменить её можно выше)")),
        ("Delete", tr("меню выбранной плитки: удалить, цвет, иконка")),
        (tr("Правый клик"), tr("то же меню у плитки под курсором")),
        (tr("Мышь"), tr("зажать плитку и потянуть: поменять плитки местами")),
        ("Ctrl Arrow Keys", tr("передвинуть выбранную плитку (если перетаскивание не заблокировано кнопкой ⇅)")),
        ("F2", tr("открыть настройки")),
        ("Ctrl+Q", tr("полностью закрыть лаунчер")),
    ]),
    (tr("Командная строка"), [
        ("Tab", tr("подставить выбранную подсказку")),
        ("Up Arrow / Down Arrow", tr("выбрать подсказку")),
        ("Enter", tr("выполнить команду")),
        ("PgUp / PgDn", tr("листать длинный ответ")),
        ("Esc", tr("закрыть строку")),
    ]),
    (tr("Заметки"), [
        ("Ctrl+N", tr("новая заметка")),
        ("Ctrl+S", tr("сохранить сразу (иначе заметка сохраняется сама)")),
    ]),
]


class ShortcutsReference(QWidget):
    """Справочник: какие клавиши что делают внутри лаунчера."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        for group, rows in SHORTCUTS:
            head = label(group.upper(), dim=True, bold=True, size=11)
            head.setContentsMargins(4, 8, 0, 2)
            root.addWidget(head)
            box = QFrame()
            box.setProperty("card", True)
            grid = QGridLayout(box)
            grid.setColumnStretch(1, 1)
            for i, (keys, text) in enumerate(rows):
                k = label(keys, accent=True, bold=True, size=14)
                k.setFixedWidth(150)
                grid.addWidget(k, i, 0, Qt.AlignmentFlag.AlignTop)
                grid.addWidget(label(text, dim=True), i, 1, Qt.AlignmentFlag.AlignTop)
            root.addWidget(box)


class TileKeysPage(QWidget):
    """Список плиток с быстрыми клавишами. Нажал на строку: сменить клавишу; «✕» убирает её."""

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.addWidget(label(
            tr("Нажми на плитку в списке, чтобы выбрать ей клавишу: подходят буквы и цифры, раскладка не важна. "
               "Если клавишу уже занимает другая плитка, они поменяются клавишами. «✕» убирает клавишу."), dim=True))
        root.addWidget(button(tr("Раздать заново по порядку"), self.reassign, width=220), 0, Qt.AlignmentFlag.AlignLeft)
        self.grid = QGridLayout()
        self.grid.setColumnStretch(0, 1)
        root.addLayout(self.grid)
        self.rows = []   # [(кнопка строки, кнопка «✕»)]
        self.shown = []  # какая клавиша сейчас написана в строке
        self.render()

    @staticmethod
    def row_text(tile):
        key = tile.get("key")
        return f"[{key.upper()}]   {tile['name']}" if key else f"  —     {tile['name']}"

    def render(self):
        clear_layout(self.grid)
        self.rows, self.shown = [], []
        if not self.app.tiles:
            self.grid.addWidget(label(tr("Плиток пока нет."), dim=True), 0, 0)
            return
        for index, tile in enumerate(self.app.tiles):
            key = tile.get("key") or ""
            name_btn = QPushButton(self.row_text(tile))
            name_btn.setProperty("nav", True)
            name_btn.clicked.connect(lambda _=False, i=index: self.change(i))
            clear_btn = QPushButton("✕")
            clear_btn.setProperty("ghost", True)
            clear_btn.setProperty("compact", True)
            clear_btn.setFixedWidth(40)
            clear_btn.setEnabled(bool(key))
            clear_btn.clicked.connect(lambda _=False, i=index: self.clear(i))
            self.grid.addWidget(name_btn, index, 0)
            self.grid.addWidget(clear_btn, index, 1)
            self.rows.append((name_btn, clear_btn))
            self.shown.append(key)

    def sync_rows(self):
        """Обновляет только строки, у которых клавиша изменилась."""
        for index, (name_btn, clear_btn) in enumerate(self.rows):
            if index >= len(self.app.tiles):
                break
            tile = self.app.tiles[index]
            key = tile.get("key") or ""
            if self.shown[index] != key:
                self.shown[index] = key
                name_btn.setText(self.row_text(tile))
                clear_btn.setEnabled(bool(key))

    def change(self, index):
        tile = self.app.tiles[index]
        KeyCapture(self.window(), tile["name"], tile.get("key"), lambda key: self.pick(index, key)).open()

    def pick(self, index, key):
        tiles = self.app.tiles
        owner = next((t for t in tiles if t is not tiles[index] and t.get("key") == key), None)
        if owner is not None and not dialogs.ask(
                self.window(), tr("Клавиша занята"),
                tr('Клавишу {v} уже занимает плитка «{name}».\nПоменять плитки клавишами?',
                   v=key.upper(), name=owner["name"])):
            return
        self.app.set_tile_key(index, key)
        self.sync_rows()

    def clear(self, index):
        self.app.set_tile_key(index, "")
        self.sync_rows()

    def reassign(self):
        if not dialogs.ask(self.window(), tr("Раздать заново"),
                           tr("Все плитки получат клавиши заново по порядку: 1, 2, 3… q, w, e…\nПродолжить?")):
            return
        self.app.reset_tile_keys()
        self.sync_rows()


class KeyCapture(QDialog):
    """Маленькое окно «нажми клавишу»: записывает одну букву или цифру."""

    def __init__(self, master, name, current, on_pick):
        super().__init__(master)
        self.current = current
        self.on_pick = on_pick  # on_pick(клавиша строчной буквой или цифрой)
        self.setWindowTitle(tr("Быстрая клавиша"))
        self.setFixedSize(380, 190)
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.addWidget(label(name, bold=True, size=15), 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(label(tr('Сейчас: {v}', v=current.upper()) if current else tr("Сейчас клавиши нет"),
                               dim=True), 0, Qt.AlignmentFlag.AlignHCenter)
        self.status = label(tr("Нажми новую клавишу: букву или цифру.\nEsc — отмена"), dim=True)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)
        layout.addStretch(1)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def say(self, text):
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {theme.color('error')};")

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
            return
        if key in MODIFIER_KEYS:
            return
        mods = event.modifiers()
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            self.say(tr("Нажми клавишу без Ctrl и Alt"))
            return
        code = event.nativeVirtualKey() or key  # физическая клавиша: раскладка не важна
        if not (48 <= code <= 57 or 65 <= code <= 90):
            self.say(tr("Подходят только буквы и цифры"))
            return
        chosen = chr(code).lower()
        self.accept()
        if chosen != self.current:
            self.on_pick(chosen)
