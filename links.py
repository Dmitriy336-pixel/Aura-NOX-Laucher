"""Кликабельные ссылки в тексте: в текстовых полях (условия) и в подписях («О программе»).
Адрес вида http(s)://... находится в тексте сам и открывается в браузере по умолчанию."""
import re
import tkinter as tk
import webbrowser

import customtkinter as ctk

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


def fill_text(box, text):
    """Кладёт текст в CTkTextbox (его можно сделать только для чтения) с кликабельными адресами."""
    inner = box._textbox
    inner.configure(state="normal")
    inner.delete("1.0", "end")
    for number, (piece, url) in enumerate(split(text)):
        if url is None:
            inner.insert("end", piece)
            continue
        tag = f"link{number}"
        inner.insert("end", piece, (tag,))
        inner.tag_configure(tag, foreground=LINK_COLOR, underline=True)
        inner.tag_bind(tag, "<Button-1>", lambda e, u=url: open_url(u))
        inner.tag_bind(tag, "<Enter>", lambda e: inner.configure(cursor="hand2"))
        inner.tag_bind(tag, "<Leave>", lambda e: inner.configure(cursor=""))
    inner.configure(state="disabled")


def linked_label(master, text, text_color=None, wraplength=420, **kwargs):
    """Подпись, где адреса кликабельны. Без адресов это обычный CTkLabel."""
    parts = split(text)
    if all(url is None for _piece, url in parts):
        return ctk.CTkLabel(master, text=text, text_color=text_color, anchor="w", justify="left",
                            wraplength=wraplength, **kwargs)
    row = ctk.CTkFrame(master, fg_color="transparent")
    for piece, url in parts:
        if url is None:
            ctk.CTkLabel(row, text=piece, text_color=text_color, anchor="w", **kwargs).pack(side="left")
            continue
        label = ctk.CTkLabel(row, text=url, text_color=LINK_COLOR, anchor="w",
                             font=ctk.CTkFont(underline=True), **kwargs)
        label.pack(side="left")
        try:
            label._label.configure(cursor="hand2")  # рука над ссылкой
        except (AttributeError, tk.TclError):
            pass
        label.bind("<Button-1>", lambda e, u=url: open_url(u))
    return row
