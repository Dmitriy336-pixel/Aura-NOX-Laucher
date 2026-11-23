# tile_grid.py
"""Сетка плиток на PySide6. Только рисует. Что делать по клику, решает окно (app.py).
Каждая плитка — один виджет TileButton, который рисует себя сам (цвет, иконка, название, рамка, подпись)."""

import textwrap

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QFrame, QGridLayout, QScrollArea, QWidget

import sounds
import theme
from i18n import tr
import tile_icons
from config import GAP

DRAG_DISTANCE = 8     # на сколько px надо сдвинуть мышь, чтобы это стало перетаскиванием, а не кликом
EDGE = 40             # у верхнего и нижнего края области плиток перетаскивание прокручивает сетку
SCROLL_DELAY = 50     # как часто прокручиваем, мс
SCROLL_STEP = 14      # на сколько px за один шаг


SPECIAL_TILES = 2  # максимум служебных плиток: «+» (позиция 0) и поиск (позиция 1)


def special_count(settings):
    """Сколько служебных плиток сейчас: если «+» сам открывает поиск (add_tile_mode = search),
    отдельная плитка поиска не нужна — остаётся одна «+»."""
    return 1 if settings.get("add_tile_mode", "file") == "search" else SPECIAL_TILES


class TileButton(QWidget):
    """Плитка (или «+» при is_plus). Рисуется вручную: так работают и иконка над названием, и подпись под плиткой."""

    def __init__(self, grid, parent=None):
        super().__init__(parent)
        self.grid = grid
        self.index = -1          # номер плитки без «+»
        self.tile = None
        self.is_plus = False     # служебная плитка («+» или поиск): без цвета, иконки и перетаскивания
        self.kind = "plus"       # какая служебная: "plus" или "search"
        self.action = None       # что делать по клику на служебной плитке
        self.color = "#2d6a4f"
        self.text = ""
        self.pixmap = None
        self.caption = ""
        self.size_px = 60
        self.caption_h = 0
        self.font_px = 12
        self.small_px = 11
        self.border_w = 0
        self.border_c = "#ffffff"
        self.hovered = False
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # Tab и стрелки обрабатывает главное окно

    # --- настройка ---
    def configure(self, size, caption_h=0):
        self.size_px = size
        self.caption_h = caption_h
        self.setFixedSize(size, size + (caption_h + 4 if caption_h else 0))

    def set_border(self, width, color=None):
        self.border_w = width
        if color:
            self.border_c = color
        self.update()

    # --- рисование ---
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        s = self.size_px
        box = QRectF(0, 0, s, s)
        radius = theme.shape("tile_radius")

        if self.is_plus:
            fill = QColor(theme.color("ghost_hover")) if self.hovered else None
            text_color = QColor(theme.color("ghost_text"))
        else:
            fill = QColor(self.color)
            if self.hovered:
                fill = fill.lighter(112)
            text_color = QColor(theme.tile_text_color(self.color))

        if fill is not None:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(box, radius, radius)
        if self.border_w:
            half = self.border_w / 2
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(self.border_c), self.border_w))
            p.drawRoundedRect(box.adjusted(half, half, -half, -half), radius, radius)

        font = p.font()
        if self.is_plus:
            # значки рисуем линиями: символ шрифта сидит не по центру (у него свой базовый уровень)
            pen = QPen(text_color, max(2.0, s * 0.045))
            if self.kind == "search":  # лупа: кружок и ручка вниз вправо
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                r = s * 0.13
                cx = cy = s / 2 - r * 0.35
                p.drawEllipse(QPointF(cx, cy), r, r)
                edge = r * 0.7071
                p.drawLine(QPointF(cx + edge, cy + edge), QPointF(cx + edge + s * 0.1, cy + edge + s * 0.1))
                return
            half = s * 0.15
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            p.setPen(pen)
            p.drawLine(QPointF(s / 2 - half, s / 2), QPointF(s / 2 + half, s / 2))
            p.drawLine(QPointF(s / 2, s / 2 - half), QPointF(s / 2, s / 2 + half))
            return

        font.setPixelSize(self.font_px)
        p.setFont(font)
        p.setPen(text_color)
        flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
        pm = self.pixmap
        if pm is not None:
            ratio = pm.devicePixelRatio() or 1.0
            pw, ph = pm.width() / ratio, pm.height() / ratio
            if self.text:
                # высота текста: если иконка с текстом не помещаются, иконку уменьшаем
                th = p.fontMetrics().boundingRect(QRect(0, 0, int(s - 8), 10000), int(flags), self.text).height()
                avail = s - 8 - th - 2
                if ph > avail:
                    new = max(16, int(avail))
                    pm = pm.scaled(int(new * ratio), int(new * ratio), Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
                    pm.setDevicePixelRatio(ratio)
                    pw, ph = pm.width() / ratio, pm.height() / ratio
                top = max(4.0, (s - ph - 2 - th) / 2)
                p.drawPixmap(QPointF((s - pw) / 2, top), pm)
                y = top + ph + 2
                p.drawText(QRectF(4, y, s - 8, th + 2), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
                           | Qt.TextFlag.TextWordWrap, self.text)
            else:
                p.drawPixmap(QPointF((s - pw) / 2, (s - ph) / 2), pm)
        else:
            p.drawText(QRectF(4, 4, s - 8, s - 8), flags, self.text)

        if self.caption_h and self.caption:
            small = p.font()
            small.setPixelSize(self.small_px)
            p.setFont(small)
            p.setPen(QColor(theme.color("caption")))
            p.drawText(QRectF(0, s + 4, s, self.caption_h),
                       Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap,
                       self.caption)

    # --- мышь ---
    def enterEvent(self, event):
        self.hovered = True
        if not self.is_plus:
            sounds.play("hover")
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if self.is_plus:
            return
        pos = event.globalPosition().toPoint()
        if event.button() == Qt.MouseButton.LeftButton:
            self.grid.drag_press(self.index, pos)
        elif event.button() == Qt.MouseButton.RightButton:
            self.grid.on_menu(pos, self.index)

    def mouseMoveEvent(self, event):
        if not self.is_plus and event.buttons() & Qt.MouseButton.LeftButton:
            self.grid.drag_motion(event.globalPosition().toPoint())

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self.is_plus:
            if self.action is not None and self.rect().contains(event.position().toPoint()):
                self.action()
        else:
            self.grid.drag_release(event.globalPosition().toPoint(), self.tile)


class TileGrid(QScrollArea):
    def __init__(self, parent, on_add, on_run, on_menu, on_move=None, can_drag=None, on_search=None):
        super().__init__(parent)
        self.on_add = on_add      # нажали "+"
        self.on_search = on_search  # нажали плитку поиска
        self.on_run = on_run      # нажали плитку: on_run(tile)
        self.on_menu = on_menu    # правый клик: on_menu(QPoint в экранных координатах, index)
        self.on_move = on_move    # перетащили: on_move(откуда, куда), номера плиток без "+"
        self.can_drag = can_drag or (lambda: True)  # False, когда перетаскивание заблокировано
        self.buttons = []         # все кнопки по порядку: [0] = "+", [1] = поиск, дальше плитки
        self.drag = None          # состояние текущего нажатия левой кнопкой на плитке
        self.selected_pos = None
        self.special_n = SPECIAL_TILES  # сколько служебных плиток в последней отрисовке

        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.viewport().setStyleSheet("background: transparent;")

        self.holder = QWidget()
        self.holder.setObjectName("tileholder")
        self.holder.setStyleSheet("#tileholder { background: transparent; }")
        self.grid_layout = QGridLayout(self.holder)
        self.grid_layout.setContentsMargins(GAP, GAP, GAP, GAP)
        self.grid_layout.setSpacing(GAP * 2)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.setWidget(self.holder)

        self.scroll_timer = QTimer(self)
        self.scroll_timer.setInterval(SCROLL_DELAY)
        self.scroll_timer.timeout.connect(self.autoscroll)

    def tile_size(self, grid_width, columns, max_tile_size):
        usable = grid_width - 16 - 30 - columns * 2 * GAP  # рамки и полоса прокрутки
        return min(max_tile_size, max(60, usable // columns))

    def render(self, tiles, grid_width, selected, settings):
        columns = settings["columns"]
        max_tile_size = settings["max_tile_size"]
        mode = settings["tile_label"]  # inside / below / hover
        self.drag = None
        self.stop_autoscroll()
        while True:
            item = self.grid_layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.hide()
                widget.setParent(None)
                widget.deleteLater()

        size = self.tile_size(grid_width, columns, max_tile_size)
        font_px = max(12, size // 8)
        small_px = max(11, size // 10)
        caption_h = int(small_px * 2.8) if mode == "below" else 0

        self.buttons = []
        self.special_n = special_count(settings)
        specials = (("plus", self.on_add, tr("Добавить программу")), ("search", self.on_search, tr("Поиск программ")))
        specials = specials[:self.special_n]
        for pos, (kind, action, tip) in enumerate(specials):
            special = TileButton(self, self.holder)
            special.is_plus = True
            special.kind = kind
            special.action = action
            special.configure(size)
            special.set_border(2, theme.color("tile_border"))
            special.setToolTip(tip)
            self.grid_layout.addWidget(special, pos // columns, pos % columns, Qt.AlignmentFlag.AlignTop)
            self.buttons.append(special)

        palette = theme.CURRENT_TILE_COLORS
        for i, tile in enumerate(tiles):
            pos = i + self.special_n  # первые позиции заняты служебными плитками
            ratio = settings["tile_icon_size"] / 100 if mode == "inside" else 0.8
            icon = tile_icons.load(tile.get("icon"), int(size * ratio))
            text_inside = mode == "inside" or icon is None  # без иконки название всегда на плитке

            btn = TileButton(self, self.holder)
            btn.index = i
            btn.tile = tile
            btn.color = tile.get("color") or palette[i % len(palette)]
            btn.pixmap = icon
            btn.text = self.tile_text(tile, settings["tile_show_key"]) if text_inside else ""
            btn.font_px, btn.small_px = font_px, small_px
            btn.configure(size, caption_h)
            if mode == "below" and icon is not None:
                btn.caption = self.caption_text(tile, settings["tile_show_key"])
            elif mode == "hover" and icon is not None:
                key = tile.get("key")
                btn.setToolTip(tile["name"] + (f"   [{key.upper()}]" if key else ""))
            self.grid_layout.addWidget(btn, pos // columns, pos % columns, Qt.AlignmentFlag.AlignTop)
            self.buttons.append(btn)

        self.select(selected)

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
        """Подсвечивает плитку на позиции pos рамкой, у остальных рамку убирает."""
        self.selected_pos = pos
        for i, btn in enumerate(self.buttons):
            if i == pos:
                btn.set_border(3, theme.color("tile_select"))
            elif i < self.special_n:
                btn.set_border(2, theme.color("tile_border"))  # служебные плитки всегда с рамкой
            else:
                btn.set_border(0)
        if pos is not None and 0 <= pos < len(self.buttons):
            self.ensureWidgetVisible(self.buttons[pos])

    # --- клик и перетаскивание ---
    def drag_press(self, index, pos: QPoint):
        self.drag = {"index": index, "x": pos.x(), "y": pos.y(), "px": pos.x(), "py": pos.y(),
                     "moved": False, "active": False, "target": None}

    def drag_motion(self, pos: QPoint):
        d = self.drag
        if d is None:
            return
        d["px"], d["py"] = pos.x(), pos.y()
        if not d["moved"]:
            if abs(pos.x() - d["x"]) < DRAG_DISTANCE and abs(pos.y() - d["y"]) < DRAG_DISTANCE:
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
        if not self.scroll_timer.isActive() and self.edge_step() != 0:
            self.scroll_timer.start()

    def update_target(self):
        """Пересчитывает, на чьё место встанет плитка, и перекрашивает рамки."""
        d = self.drag
        target = self.target_at(d["px"], d["py"])
        if target != d["target"]:
            old, d["target"] = d["target"], target
            self.paint_drag(old)    # перекрашиваем только две плитки, а не все: так не тормозит
            self.paint_drag(target)

    def view_rect(self):
        view = self.viewport()
        top_left = view.mapToGlobal(QPoint(0, 0))
        return top_left.x(), top_left.y(), view.width(), view.height()

    def edge_step(self):
        """-1, если мышь у верхнего края области плиток, +1 у нижнего, иначе 0."""
        d = self.drag
        if d is None or not d["active"]:
            return 0
        left, top, width, height = self.view_rect()
        x, y = d["px"], d["py"]
        if not (left <= x < left + width and top <= y < top + height):
            return 0
        if y < top + EDGE:
            return -1
        if y >= top + height - EDGE:
            return 1
        return 0

    def autoscroll(self):
        step = self.edge_step()
        if step == 0 or not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            # кнопку отпустили (событие могло потеряться): прокрутку и перетаскивание прекращаем
            self.scroll_timer.stop()
            if step != 0:
                self.drag = None
                self.select(self.selected_pos)
            return
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() + step * SCROLL_STEP)
        self.update_target()

    def stop_autoscroll(self):
        self.scroll_timer.stop()

    def drag_release(self, pos: QPoint, tile):
        d, self.drag = self.drag, None
        self.stop_autoscroll()
        if d is None:
            return
        if d["active"]:
            target = self.target_at(pos.x(), pos.y())
            if target is not None and target != d["index"]:
                # чуть позже: плитка ещё обрабатывает отпускание кнопки, перерисовывать её рано
                src = d["index"]
                QTimer.singleShot(150, lambda: self.on_move(src, target))
            else:
                self.select(self.selected_pos)  # отмена: убираем рамки перетаскивания
        elif not d["moved"]:
            self.on_run(tile)  # обычный клик

    def paint_drag(self, index):
        """Рамка плитки index во время перетаскивания: жёлтая у той, что тащим, светлая у цели."""
        d = self.drag
        if index is None or d is None or index + self.special_n >= len(self.buttons):
            return
        btn = self.buttons[index + self.special_n]
        if index == d["index"]:
            btn.set_border(3, theme.color("drag_source"))
        elif index == d["target"]:
            btn.set_border(3, theme.color("drag_target"))
        else:
            btn.set_border(0)

    def target_at(self, x, y):
        """Номер плитки, ближайшей к точке (x, y) на экране; None, если точка вне области плиток."""
        left, top, width, height = self.view_rect()
        if not (left <= x < left + width and top <= y < top + height):
            return None
        best, best_dist = None, None
        for i, btn in enumerate(self.buttons[self.special_n:]):
            center = btn.mapToGlobal(QPoint(btn.width() // 2, btn.size_px // 2))
            dist = (x - center.x()) ** 2 + (y - center.y()) ** 2
            if best_dist is None or dist < best_dist:
                best, best_dist = i, dist
        return best
