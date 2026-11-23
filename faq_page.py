"""Раздел FAQ в настройках (PySide6): вопросы раскрываются по клику, сверху поиск по вопросам и ответам.
Сами вопросы лежат в faq_data.py."""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

import sounds
from faq_data import FAQ
from i18n import tr
from ui_kit import clear_layout, label


class FaqPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.opened = set()  # номера раскрытых вопросов
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("Поиск по вопросам"))
        self.search.textChanged.connect(self.render)
        root.addWidget(self.search)
        self.box = QVBoxLayout()
        root.addLayout(self.box)
        self.render()

    def toggle(self, index):
        sounds.play("faq_toggle")
        self.opened.symmetric_difference_update({index})
        self.render()

    def scroll_bar(self):
        """Полоса прокрутки области, в которой лежит страница (или None)."""
        widget = self.parent()
        while widget is not None and not isinstance(widget, QScrollArea):
            widget = widget.parent()
        return widget.verticalScrollBar() if widget is not None else None

    def render(self, *_):
        # при пересборке содержимое на миг укорачивается и прокрутка сбрасывается вниз: запоминаем и возвращаем
        bar = self.scroll_bar()
        if bar is not None:
            position = bar.value()
            self.setMinimumHeight(self.height())
            QTimer.singleShot(0, lambda: self.restore_scroll(bar, position))
        self.rebuild()

    def restore_scroll(self, bar, position):
        try:
            self.setMinimumHeight(0)
            bar.setValue(position)
        except RuntimeError:
            pass  # страницу уже закрыли

    def rebuild(self):
        clear_layout(self.box)
        query = self.search.text().strip().lower()
        shown = 0
        for index, (question, answer) in enumerate(FAQ):
            if query and query not in question.lower() and query not in answer.lower():
                continue
            shown += 1
            expanded = bool(query) or index in self.opened  # при поиске ответы сразу видны
            btn = QPushButton(("▾  " if expanded else "▸  ") + question)
            btn.setProperty("nav", True)
            btn.setStyleSheet("font-size: 14px; font-weight: bold;")
            btn.clicked.connect(lambda _=False, i=index: self.toggle(i))
            self.box.addWidget(btn)
            if expanded:
                ans = label(answer, dim=True)
                ans.setContentsMargins(30, 0, 10, 6)
                self.box.addWidget(ans)
        if not shown:
            self.box.addWidget(label(tr("Ничего не найдено"), dim=True))
