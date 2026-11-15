"""Сетка плиток. Только рисует. Что делать по клику, решает окно (app.py)."""
import textwrap

import customtkinter as ctk

import sounds
import theme
import tile_icons
from config import GAP
from tooltip import Tooltip
from scrollfix import fix_later

CAPTION_COLOR = theme.CAPTION  # цвет подписи под плиткой
DRAG_DISTANCE = 8          # на сколько px надо сдвинуть мышь, чтобы это стало перетаскиванием, а не кликом
DRAG_SOURCE = theme.DRAG_SOURCE    # рамка у плитки, которую тащим
DRAG_TARGET = theme.DRAG_TARGET  # рамка у плитки, на место которой встанет перетаскиваемая
EDGE = 40                  # у верхнего и нижнего края области плиток (px) перетаскивание прокручивает сетку
SCROLL_DELAY = 50          # как часто прокручиваем, мс
DEFAULT_TEXT = theme.TILE_TEXT_LIGHT   # светлый текст на тёмной плитке: плитки тёмные и на светлой теме тоже
DARK_TEXT = theme.TILE_TEXT_DARK      # текст на светлой плитке


def text_color_for(background):
    """Тёмный текст на светлой плитке, обычный светлый на тёмной."""
    try:
        r, g, b = (int(background[i:i + 2], 16) for i in (1, 3, 5))
    except (ValueError, TypeError):
        return DEFAULT_TEXT
    return DARK_TEXT if 0.299 * r + 0.587 * g + 0.114 * b > 160 else DEFAULT_TEXT


class TileGrid(ctk.CTkScrollableFrame):
    def __init__(self, master, on_add, on_run, on_menu, on_move=None, can_drag=None):
        super().__init__(master)
        self.on_add = on_add    # нажали "+"
        self.on_run = on_run    # нажали плитку: on_run(tile)
        self.on_menu = on_menu  # правый клик: on_menu(event, index)
        self.buttons = []       # все кнопки по порядку: [0] = "+", дальше плитки
        self.on_move = on_move  # перетащили: on_move(откуда, куда), номера плиток без "+"
        self.can_drag = can_drag or (lambda: True)  # False, когда перетаскивание заблокировано
        self.drag = None        # состояние текущего нажатия левой кнопкой на плитке
        self.selected_pos = None
        self.scroll_job = None  # повторяющаяся прокрутка у края при перетаскивании

    def tile_size(self, grid_width, columns, max_tile_size):
        usable = grid_width - 16 - 30 - columns * 2 * GAP  # рамки и полоса прокрутки
        return min(max_tile_size, max(60, usable // columns))

    def render(self, tiles, grid_width, selected, settings):
        columns = settings["columns"]
        max_tile_size = settings["max_tile_size"]
        mode = settings["tile_label"]  # inside / below / hover
        self.drag = None
        self.stop_autoscroll()
        for child in self.winfo_children():
            child.destroy()

        size = self.tile_size(grid_width, columns, max_tile_size)
        font = ctk.CTkFont(size=max(12, size // 8))
        small = ctk.CTkFont(size=max(11, size // 10))

        # первая плитка всегда "+"
        plus_image = theme.image("plus", size // 2)  # картинка плюса из темы или None
        add_btn = ctk.CTkButton(
            self, text="" if plus_image else "+", image=plus_image, width=size, height=size,
            font=ctk.CTkFont(size=size // 2),
            fg_color="transparent", border_width=2, border_color=theme.TILE_BORDER,
            text_color=theme.GHOST_TEXT, hover_color=theme.GHOST_HOVER, corner_radius=theme.TILE_RADIUS,  # плюс виден на любой теме
            command=self.on_add,
        )
        add_btn.grid(row=0, column=0, padx=GAP, pady=GAP, sticky="n")
        self.buttons = [add_btn]

        for i, tile in enumerate(tiles):
            pos = i + 1  # позиция 0 занята плиткой "+"
            # при названии на плитке остаётся место под подпись, иначе иконка почти на всю плитку
            ratio = settings["tile_icon_size"] / 100 if mode == "inside" else 0.8
            icon = tile_icons.load(tile.get("icon"), int(size * ratio))
            text_inside = mode == "inside" or icon is None  # без иконки название всегда на плитке

            colors = theme.TILE_COLORS  # цвета плиток по кругу берутся из темы
            color = tile.get("color") or colors[i % len(colors)]  # свой цвет плитки, иначе по кругу
            cell = ctk.CTkFrame(self, fg_color="transparent")  # плитка и подпись под ней
            cell.grid(row=pos // columns, column=pos % columns, padx=GAP, pady=GAP, sticky="n")

            btn = ctk.CTkButton(
                cell,
                text=self.tile_text(tile, settings["tile_show_key"]) if text_inside else "",
                image=icon, compound="top",
                width=size, height=size, font=font,
                fg_color=color, text_color=text_color_for(color), corner_radius=theme.TILE_RADIUS,
            )
            btn.pack()
            self.bind_tile(btn, i, tile)  # клик запускает, перетаскивание переставляет
            btn.bind("<Button-3>", lambda e, idx=i: self.on_menu(e, idx))
            self.buttons.append(btn)

            if mode == "below":
                # подпись под плиткой одинаковой высоты у всех, чтобы ряды выглядели ровно
                caption = ctk.CTkLabel(
                    cell, text=self.caption_text(tile, settings["tile_show_key"]) if icon else "",
                    width=size, height=int(small.cget("size") * 2.8), wraplength=size,
                    font=small, text_color=CAPTION_COLOR, anchor="n", justify="center",
                )
                caption.pack(pady=(4, 0))
                self.bind_tile(caption, i, tile)  # подпись ведёт себя как сама плитка
                caption.bind("<Button-3>", lambda e, idx=i: self.on_menu(e, idx))
            elif mode == "hover" and icon is not None:
                key = tile.get("key")
                Tooltip(btn, tile["name"] + (f"   [{key.upper()}]" if key else ""))

        self.select(selected)
        fix_later(self)  # если плиток стало меньше, прокрутка не должна остаться ниже конца

    def tile_text(self, tile, show_key=True):
        """Название на плитке; сверху быстрая клавиша (если включено)."""
        name = textwrap.fill(tile["name"], 12, break_long_words=False)  # длинное слово не рвём
        key = tile.get("key")
        return f"[{key.upper()}]\n{name}" if key and show_key else name

    def caption_text(self, tile, show_key=True):
        """Название под плиткой: быстрая клавиша в начале (если включено), дальше название."""
        key = tile.get("key")
        return f"[{key.upper()}] {tile['name']}" if key and show_key else tile["name"]

    def select(self, pos):
        """Подсвечивает плитку на позиции pos белой рамкой, у остальных рамку убирает."""
        self.selected_pos = pos
        for i, btn in enumerate(self.buttons):
            if i == pos:
                btn.configure(border_width=3, border_color=theme.TILE_SELECT)  # тёмная рамка на светлой теме
            elif i == 0:
                btn.configure(border_width=2, border_color=theme.TILE_BORDER)  # "+" всегда с рамкой
            else:
                btn.configure(border_width=0)

    # --- клик и перетаскивание ---
    def bind_tile(self, widget, index, tile):
        """Запуск плитки теперь по отпусканию кнопки: так отличаем клик от перетаскивания."""
        widget.bind("<ButtonPress-1>", lambda e: self.drag_press(e, index))
        widget.bind("<B1-Motion>", self.drag_motion)
        widget.bind("<ButtonRelease-1>", lambda e: self.drag_release(e, tile))
        widget.bind("<Enter>", lambda e: sounds.play("hover"), add="+")

    def drag_press(self, event, index):
        self.drag = {"index": index, "x": event.x_root, "y": event.y_root, "px": event.x_root, "py": event.y_root,
                     "moved": False, "active": False, "target": None}

    def drag_motion(self, event):
        d = self.drag
        if d is None:
            return
        d["px"], d["py"] = event.x_root, event.y_root  # где мышь сейчас
        if not d["moved"]:
            if abs(event.x_root - d["x"]) < DRAG_DISTANCE and abs(event.y_root - d["y"]) < DRAG_DISTANCE:
                return
            d["moved"] = True  # мышь утащили: после отпускания плитку запускать уже не нужно
            if self.on_move is None or not self.can_drag():
                return         # перетаскивание заблокировано
            d["active"] = True
            sounds.play("drag_start")
            self.paint_drag(d["index"])
        if not d["active"]:
            return
        self.update_target()
        if self.scroll_job is None and self.edge_step() != 0:
            self.scroll_job = self.after(SCROLL_DELAY, self.autoscroll)

    def update_target(self):
        """Пересчитывает, на чьё место встанет плитка, и перекрашивает рамки."""
        d = self.drag
        target = self.target_at(d["px"], d["py"])
        if target != d["target"]:
            old, d["target"] = d["target"], target
            self.paint_drag(old)    # перекрашиваем только две плитки, а не все: так не тормозит
            self.paint_drag(target)

    def edge_step(self):
        """-1, если мышь у верхнего края области плиток, +1 у нижнего, иначе 0."""
        d = self.drag
        if d is None or not d["active"]:
            return 0
        view = self.master
        left, top = view.winfo_rootx(), view.winfo_rooty()
        x, y = d["px"], d["py"]
        if not (left <= x < left + view.winfo_width() and top <= y < top + view.winfo_height()):
            return 0
        if y < top + EDGE:
            return -1
        if y >= top + view.winfo_height() - EDGE:
            return 1
        return 0

    def autoscroll(self):
        self.scroll_job = None
        step = self.edge_step()
        if step == 0:
            return
        self.master.yview_scroll(step, "units")
        self.update_idletasks()  # после прокрутки координаты кнопок изменились
        self.update_target()
        self.scroll_job = self.after(SCROLL_DELAY, self.autoscroll)

    def stop_autoscroll(self):
        if self.scroll_job is not None:
            self.after_cancel(self.scroll_job)
            self.scroll_job = None

    def drag_release(self, event, tile):
        d, self.drag = self.drag, None
        self.stop_autoscroll()
        if d is None:
            return
        if d["active"]:
            target = self.target_at(event.x_root, event.y_root)
            if target is not None and target != d["index"]:
                # чуть позже: кнопка ещё доигрывает анимацию нажатия, и перерисовывать её рано
                self.after(150, lambda: self.on_move(d["index"], target))
            else:
                self.select(self.selected_pos)  # отмена: убираем рамки перетаскивания
        elif not d["moved"]:
            self.on_run(tile)  # обычный клик

    def paint_drag(self, index):
        """Рамка плитки index во время перетаскивания: жёлтая у той, что тащим, белая у цели."""
        d = self.drag
        if index is None or d is None or index + 1 >= len(self.buttons):
            return
        btn = self.buttons[index + 1]
        if index == d["index"]:
            btn.configure(border_width=3, border_color=DRAG_SOURCE)
        elif index == d["target"]:
            btn.configure(border_width=3, border_color=DRAG_TARGET)
        else:
            btn.configure(border_width=0)

    def target_at(self, x, y):
        """Номер плитки, ближайшей к точке (x, y) на экране; None, если точка вне области плиток."""
        view = self.master  # холст прокручиваемой области: его границы и есть видимая часть сетки
        left, top = view.winfo_rootx(), view.winfo_rooty()
        if not (left <= x < left + view.winfo_width() and top <= y < top + view.winfo_height()):
            return None
        best, best_dist = None, None
        for i, btn in enumerate(self.buttons[1:]):
            cx = btn.winfo_rootx() + btn.winfo_width() // 2
            cy = btn.winfo_rooty() + btn.winfo_height() // 2
            dist = (x - cx) ** 2 + (y - cy) ** 2
            if best_dist is None or dist < best_dist:
                best, best_dist = i, dist
        return best
