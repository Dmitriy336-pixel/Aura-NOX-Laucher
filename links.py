"""Кликабельные ссылки в тексте: в текстовых полях (условия) и в подписях («О программе») на PySide6.
Адрес вида http(s)://... находится в тексте сам и открывается в браузере по умолчанию."""
import html
import re
import webbrowser

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QTextBrowser

URL = re.compile(r"https?://\S+")
TRAILING = ".,;:!?)]}»\"'"   # знаки после адреса к нему не относятся: «(https://site.com).»
LINK_COLOR = "#4a9eff"


def open_url(url):
    try:
        webbrowser.open(url)
    except Exception:  # noqa: BLE001  браузера нет или он не открылся: лаунчер из-за ссылки падать не должен
        pass


def split(text):
    """[(кусок, адрес или None)]: обычный текст и найденные адреса по порядку."""
    parts, pos = [], 0
    for match in URL.finditer(text):
        url = match.group().rstrip(TRAILING)
        start, end = match.start(), match.start() + len(url)
        if start > pos:
            parts.append((text[pos:start], None))
        parts.append((url, url))
        pos = end
    if pos < len(text):
        parts.append((text[pos:], None))
    return parts


def to_html(text):
    """Обычный текст -> HTML: переносы строк сохраняются, адреса становятся ссылками."""
    out = []
    for piece, url in split(text):
        if url is None:
            out.append(html.escape(piece).replace("\n", "<br>"))
        else:
            safe = html.escape(url, quote=True)
            out.append(f'<a href="{safe}" style="color:{LINK_COLOR}">{safe}</a>')
    return "".join(out)


def make_browser(parent=None):
    """Текстовое поле только для чтения; ссылки открываются в браузере."""
    box = QTextBrowser(parent)
    box.setOpenLinks(False)
    box.anchorClicked.connect(lambda url: open_url(url.toString()))
    return box


def fill_text(box, text):
    """Кладёт текст в QTextBrowser (только чтение) с кликабельными адресами."""
    if not isinstance(box, QTextBrowser):
        raise TypeError("fill_text ожидает QTextBrowser (см. links.make_browser)")
    box.setHtml(f'<div style="white-space: pre-wrap">{to_html(text)}</div>')


def linked_label(text, color=None, wraplength=420, parent=None):
    """Подпись, где адреса кликабельны. Без адресов это обычный QLabel."""
    label = QLabel(parent)
    label.setWordWrap(True)
    label.setMaximumWidth(wraplength)
    if color:
        label.setStyleSheet(f"color: {color};")
    if all(url is None for _piece, url in split(text)):
        label.setText(text)
        return label
    label.setTextFormat(Qt.TextFormat.RichText)
    label.setText(to_html(text))
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
    label.setOpenExternalLinks(False)
    label.linkActivated.connect(open_url)
    return label
