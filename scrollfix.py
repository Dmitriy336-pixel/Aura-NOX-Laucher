"""Прокрутка CustomTkinter не возвращается сама, когда содержимое пересобрали и оно стало короче:
окно остаётся «проскроллено вниз», а содержимое оказывается где-то сверху. Эти функции это исправляют."""
import tkinter as tk


def canvas_of(scrollable):
    """Холст, на котором лежит содержимое прокручиваемой области."""
    return getattr(scrollable, "_parent_canvas", None) or scrollable.master


def scroll_to_top(scrollable):
    canvas_of(scrollable).yview_moveto(0)


def clamp_scroll(scrollable):
    """Возвращает прокрутку в допустимые границы, если после пересборки она оказалась за ними."""
    canvas = canvas_of(scrollable)
    first, last = canvas.yview()
    visible = last - first
    if visible >= 1.0 or first < 0:   # всё содержимое помещается: прокручивать нечего
        canvas.yview_moveto(0)
    elif last > 1.0:                  # смотрим ниже конца содержимого: прижимаем к низу
        canvas.yview_moveto(1.0 - visible)


def fix_later(scrollable, to_top=False):
    """Вызывать после пересборки содержимого. to_top=True: вернуть наверх (смена вкладки),
    иначе только поправить, если прокрутка вышла за границы (обычная перерисовка).
    Делается сразу и ещё раз чуть позже, когда Tk пересчитает размеры."""
    def run():
        try:
            if scrollable.winfo_exists():
                (scroll_to_top if to_top else clamp_scroll)(scrollable)
        except tk.TclError:
            pass  # окно как раз закрывают
    run()
    try:
        scrollable.after(60, run)
    except tk.TclError:
        pass