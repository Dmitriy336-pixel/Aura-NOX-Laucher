"""Размытый фон под командной строкой.
При открытии строки снимаем экран, размываем снимок и показываем его окном на весь экран прямо под строкой.
Строка при этом остаётся резкой. Клик по размытому фону закрывает строку.
Любая неудача (снимок не получился, нет памяти): строка просто открывается без размытия."""
from PIL import Image, ImageFilter
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

import theme

DOWNSCALE = 4       # размываем уменьшенную копию: быстро, а на глаз результат тот же
MAX_RADIUS = 10     # радиус на уменьшенной копии при силе 100%; на полном размере это около 40 px
DEFAULTS = {"strength": 50, "dim": 30, "fade_ms": 140}  # сила и затемнение в процентах


def qimage_to_pil(qimage):
    """QImage -> картинка PIL (RGB)."""
    qimage = qimage.convertToFormat(QImage.Format.Format_RGBA8888)
    size = (qimage.width(), qimage.height())
    data = bytes(qimage.constBits())
    return Image.frombuffer("RGBA", size, data, "raw", "RGBA", qimage.bytesPerLine(), 1).convert("RGB")


def blur_image(image, downscale=DOWNSCALE, radius=MAX_RADIUS / 2):
    """Размытая копия картинки, уменьшенная в downscale раз. Растягивает её обратно уже Qt при рисовании:
    так не тратим время и память на полноразмерное размытие."""
    small = image.reduce(max(1, downscale))
    if radius <= 0:
        return small
    return small.filter(ImageFilter.GaussianBlur(radius))


class BlurBackdrop(QWidget):
    """Окно на весь экран с размытым снимком. Фокус не берёт: он остаётся у командной строки."""
    clicked = Signal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                            | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.pixmap = None
        self.tint = QColor(0, 0, 0, 0)
        self.fade = QPropertyAnimation(self, b"windowOpacity", self)
        self.fade.setStartValue(0.0)
        self.fade.setEndValue(1.0)
        self.fade.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_over(self, screen, strength=50, dim=30, fade_ms=140):
        """Снять экран, размыть и показать. Вернёт False, если не вышло (тогда ничего не показано).
        strength и dim в процентах, fade_ms: время появления (0: сразу).
        Вызывать до показа самой командной строки, иначе она попадёт на снимок."""
        try:
            shot = screen.grabWindow(0)
            if shot.isNull():
                return False
            self.pixmap = theme.pil_to_pixmap(blur_image(qimage_to_pil(shot.toImage()), radius=MAX_RADIUS * strength / 100))
        except Exception:
            self.pixmap = None
            return False
        base = 255 if theme.current_mode() == "light" else 0  # светлая тема осветляем, тёмную затемняем
        self.tint = QColor(base, base, base, round(255 * max(0, min(100, dim)) / 100))
        self.setScreen(screen)
        self.setGeometry(screen.geometry())  # весь экран, вместе с панелью задач
        self.fade.stop()
        self.fade.setDuration(max(0, fade_ms))
        self.setWindowOpacity(0.0 if fade_ms > 0 else 1.0)
        self.show()
        if fade_ms > 0:
            self.fade.start()
        return True

    def hide_backdrop(self):
        self.fade.stop()
        self.hide()
        self.pixmap = None  # снимок большой, держать его между открытиями незачем

    def paintEvent(self, event):
        if self.pixmap is None:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawPixmap(self.rect(), self.pixmap)
        painter.fillRect(self.rect(), self.tint)

    def mousePressEvent(self, event):
        self.clicked.emit()
