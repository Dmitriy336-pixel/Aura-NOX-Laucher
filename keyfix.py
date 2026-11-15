"""Сочетания буфера обмена на любой раскладке.
В Tk Ctrl+V, Ctrl+C, Ctrl+X и Ctrl+A привязаны к латинским буквам, поэтому на русской раскладке
не срабатывают. Здесь мы смотрим на физическую клавишу (её код не зависит от раскладки)
и запускаем те же действия."""

ACTIONS = {86: "<<Paste>>", 67: "<<Copy>>", 88: "<<Cut>>", 65: "<<SelectAll>>"}  # V, C, X, A
CTRL = 0x0004
ALT = 0x20000


def install(root):
    """Подключается один раз к главному окну и действует во всех окнах программы."""
    def handler(event):
        if not event.state & CTRL or event.state & ALT:
            return None  # нужен Ctrl без Alt (Ctrl+Alt это AltGr на некоторых раскладках)
        action = ACTIONS.get(event.keycode)
        if action is None or event.keysym.lower() in ("v", "c", "x", "a"):
            return None  # латинская раскладка: Tk справляется сам, второй раз не вставляем
        try:
            event.widget.event_generate(action)
        except Exception:
            return None
        return "break"

    root.bind_all("<Key>", handler, add="+")