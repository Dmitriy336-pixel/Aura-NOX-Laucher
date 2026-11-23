"""Редактор заметок с живым оформлением Markdown на PySide6.
Текст остаётся обычным .md (символы разметки не прячутся), но выглядит оформленным: заголовки крупные,
**жирный** и *курсив* настоящие, ссылки подчёркнуты, чекбоксы переключаются кликом.
Ещё: Enter продолжает список, Ctrl+клик по ссылке открывает её."""
import re

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (QColor, QDesktopServices, QFont, QSyntaxHighlighter, QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import QTextEdit

import theme

HEADING = re.compile(r"^(#{1,6})([ \t]+)")
BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
ITALIC = re.compile(r"(?<![*\w])([*_])(?![*\s])(.+?)(?<![*\s])\1(?![*\w])")
CODE = re.compile(r"`([^`\n]+)`")
LINK = re.compile(r"\[([^\]\n]+)\]\(([^)\n]*)\)")
STRIKE = re.compile(r"~~(?=\S)(.+?)(?<=\S)~~")
LIST_ITEM = re.compile(r"^(\s*)(- \[[ xX]\] |[-*+] |(\d+)\. )(.*)$")
CHECKBOX = re.compile(r"^(\s*[-*+] )\[([ xX])\]")
QUOTE = re.compile(r"^(\s*>[ \t]?)")
HEADING_SCALE = {1: 1.7, 2: 1.45, 3: 1.25, 4: 1.12, 5: 1.05, 6: 1.0}


class MarkdownHighlighter(QSyntaxHighlighter):
    def __init__(self, document, base_px=14):
        super().__init__(document)
        self.base_px = base_px
        self.family = None

    def set_base(self, px, family):
        self.base_px, self.family = px, family
        self.rehighlight()

    def highlightBlock(self, text):
        n = len(text)
        if not n:
            return
        dim = QColor(theme.color("text_dim"))
        accent = QColor(theme.color("accent"))
        code_bg = QColor(theme.color("select_bg"))
        scale = [1.0] * n
        bold, italic, under, strike, mono = ([False] * n for _ in range(5))
        color = [None] * n
        back = [None] * n

        def mark(span, dimmed=False, **kw):
            a, b = span
            for i in range(a, b):
                if dimmed:
                    color[i] = dim
                if kw.get("bold"):
                    bold[i] = True
                if kw.get("italic"):
                    italic[i] = True
                if kw.get("under"):
                    under[i] = True
                if kw.get("strike"):
                    strike[i] = True
                if kw.get("mono"):
                    mono[i] = True
                if kw.get("color") is not None:
                    color[i] = kw["color"]
                if kw.get("back") is not None:
                    back[i] = kw["back"]

        m = HEADING.match(text)
        if m:
            level = len(m.group(1))
            for i in range(n):
                scale[i] = HEADING_SCALE[level]
            mark((0, n), bold=True)
            mark((0, m.end()), dimmed=True)

        q = QUOTE.match(text)
        if q:
            mark((0, q.end()), dimmed=True)
            mark((q.end(), n), italic=True, color=dim)

        li = LIST_ITEM.match(text)
        if li:
            start, marker_end = len(li.group(1)), len(li.group(1)) + len(li.group(2))
            marker = li.group(2)
            if marker.startswith("- [") and marker[3] in "xX":
                mark((start, marker_end), bold=True, color=accent)
                mark((marker_end, n), strike=True, color=dim)
            else:
                mark((start, marker_end), bold=True, color=accent)

        for m in CODE.finditer(text):
            mark(m.span(), mono=True, back=code_bg)
        for m in BOLD.finditer(text):
            mark(m.span(), bold=True)
            mark((m.start(), m.start() + 2), dimmed=True)
            mark((m.end() - 2, m.end()), dimmed=True)
        for m in ITALIC.finditer(text):
            mark(m.span(), italic=True)
            mark((m.start(), m.start() + 1), dimmed=True)
            mark((m.end() - 1, m.end()), dimmed=True)
        for m in STRIKE.finditer(text):
            mark(m.span(), strike=True)
            mark((m.start(), m.start() + 2), dimmed=True)
            mark((m.end() - 2, m.end()), dimmed=True)
        for m in LINK.finditer(text):
            mark(m.span(), dimmed=True)
            mark(m.span(1), under=True, color=accent)

        # одинаковые подряд символы собираем в отрезки с одним форматом
        i = 0
        while i < n:
            key = (scale[i], bold[i], italic[i], under[i], strike[i], mono[i], color[i], back[i])
            j = i + 1
            while j < n and (scale[j], bold[j], italic[j], under[j], strike[j], mono[j], color[j], back[j]) == key:
                j += 1
            if key != (1.0, False, False, False, False, False, None, None):
                fmt = QTextCharFormat()
                font = QFont(self.family) if self.family else QFont()
                font.setPixelSize(max(8, int(self.base_px * key[0])))
                font.setBold(key[1])
                font.setItalic(key[2])
                font.setUnderline(key[3])
                font.setStrikeOut(key[4])
                if key[5]:
                    font.setFamily("Consolas")
                fmt.setFont(font)
                if key[6] is not None:
                    fmt.setForeground(key[6])
                if key[7] is not None:
                    fmt.setBackground(key[7])
                self.setFormat(i, j - i, fmt)
            i = j


class MarkdownEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptRichText(False)  # вставка всегда обычным текстом
        self.setTabChangesFocus(False)
        self.viewport().setMouseTracking(True)
        self.highlighter = MarkdownHighlighter(self.document())

    def set_base_size(self, px):
        font = QFont(self.font())
        font.setPixelSize(int(px))
        self.setFont(font)
        self.highlighter.set_base(int(px), font.family())

    # --- клики: чекбокс и ссылка ---
    def checkbox_at(self, cursor):
        block = cursor.block()
        m = CHECKBOX.match(block.text())
        if not m:
            return None
        pos = cursor.positionInBlock()
        start = len(m.group(1))
        return (block, start, m.group(2)) if start <= pos <= start + 3 else None

    def link_at(self, cursor):
        pos = cursor.positionInBlock()
        for m in LINK.finditer(cursor.block().text()):
            if m.start() <= pos <= m.end():
                return m.group(2).strip()
        return None

    def mouseMoveEvent(self, event):
        cursor = self.cursorForPosition(event.position().toPoint())
        ctrl = bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
        over = self.checkbox_at(cursor) is not None or (ctrl and self.link_at(cursor))
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if over else Qt.CursorShape.IBeamCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection():
            cursor = self.cursorForPosition(event.position().toPoint())
            box = self.checkbox_at(cursor)
            if box is not None:
                block, start, state = box
                c = QTextCursor(block)
                c.setPosition(block.position() + start + 1)
                c.setPosition(block.position() + start + 2, QTextCursor.MoveMode.KeepAnchor)
                c.insertText(" " if state in "xX" else "x")
                event.accept()
                return
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                url = self.link_at(cursor)
                if url:
                    if "://" not in url and not url.startswith("mailto:"):
                        url = "https://" + url
                    QDesktopServices.openUrl(QUrl(url))
                    event.accept()
                    return
        super().mouseReleaseEvent(event)

    # --- Enter продолжает список ---
    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not (
                event.modifiers() & (Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier)):
            cursor = self.textCursor()
            block = cursor.block()
            m = LIST_ITEM.match(block.text())
            if m and not cursor.hasSelection() and cursor.positionInBlock() >= len(m.group(1)) + len(m.group(2)):
                cursor.beginEditBlock()
                if not m.group(4).strip():  # пустой пункт: Enter заканчивает список
                    c = QTextCursor(block)
                    c.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                    c.insertText("")
                else:
                    marker = m.group(2)
                    if m.group(3):
                        marker = f"{int(m.group(3)) + 1}. "
                    elif marker.startswith("- ["):
                        marker = "- [ ] "
                    cursor.insertText("\n" + m.group(1) + marker)
                    self.setTextCursor(cursor)
                cursor.endEditBlock()
                self.ensureCursorVisible()
                return
        super().keyPressEvent(event)
