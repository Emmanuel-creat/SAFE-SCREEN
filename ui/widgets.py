from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen, QRadialGradient, QFont, QBrush

COLORS = {
    "bg_primary": "#0a0e17",
    "bg_secondary": "#111827",
    "bg_tertiary": "#1a2235",
    "bg_card": "#151d2e",
    "accent": "#00e5a0",
    "accent_dim": "#00b37d",
    "danger": "#ff3b5c",
    "danger_dim": "#cc2f4a",
    "warning": "#ffb020",
    "text_primary": "#e8ecf4",
    "text_secondary": "#8892a4",
    "text_muted": "#4a5568",
    "border": "#1e293b",
    "border_light": "#2d3a50",
    "sharing": "#6366f1",
    "sharing_dim": "#4f46e5",
}


class PowerButton(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active = False
        self._hover = False
        self._glow_intensity = 0.0
        self.setFixedSize(120, 120)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._anim = QPropertyAnimation(self, b"glow_intensity")
        self._anim.setDuration(400)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def _get_glow(self) -> float:
        return self._glow_intensity

    def _set_glow(self, v: float) -> None:
        self._glow_intensity = v
        self.update()

    glow_intensity = pyqtProperty(float, _get_glow, _set_glow)

    @property
    def active(self) -> bool:
        return self._active

    @active.setter
    def active(self, value: bool) -> None:
        self._active = value
        self._anim.stop()
        self._anim.setStartValue(self._glow_intensity)
        self._anim.setEndValue(1.0 if value else 0.0)
        self._anim.start()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._active = not self._active
            self._anim.stop()
            self._anim.setStartValue(self._glow_intensity)
            self._anim.setEndValue(1.0 if self._active else 0.0)
            self._anim.start()
            self.toggled.emit(self._active)

    def enterEvent(self, event) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover = False
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = min(w, h) / 2 - 8
        accent = QColor("#00e5a0")
        inactive = QColor("#2d3a50")
        base = QColor("#111827")
        g = self._glow_intensity
        color = QColor(
            int(inactive.red() + (accent.red() - inactive.red()) * g),
            int(inactive.green() + (accent.green() - inactive.green()) * g),
            int(inactive.blue() + (accent.blue() - inactive.blue()) * g),
        )
        if g > 0.1:
            glow = QRadialGradient(cx, cy, radius + 15)
            gc = QColor(accent)
            gc.setAlphaF(0.25 * g)
            glow.setColorAt(0.6, gc)
            gc2 = QColor(accent)
            gc2.setAlphaF(0.0)
            glow.setColorAt(1.0, gc2)
            p.setBrush(QBrush(glow))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx - radius - 15), int(cy - radius - 15),
                          int((radius + 15) * 2), int((radius + 15) * 2))
        p.setBrush(QBrush(base))
        p.setPen(QPen(color, 3))
        p.drawEllipse(int(cx - radius), int(cy - radius), int(radius * 2), int(radius * 2))
        if self._hover:
            hc = QColor(color)
            hc.setAlphaF(0.08)
            p.setBrush(QBrush(hc))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(int(cx - radius + 3), int(cy - radius + 3),
                          int((radius - 3) * 2), int((radius - 3) * 2))
        icon_pen = QPen(color, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(icon_pen)
        icon_r = radius * 0.38
        p.drawArc(int(cx - icon_r), int(cy - icon_r), int(icon_r * 2), int(icon_r * 2), 50 * 16, 260 * 16)
        line_len = icon_r * 0.7
        p.drawLine(int(cx), int(cy - icon_r - 2), int(cx), int(cy - icon_r + line_len))
        p.end()


class StatusIndicator(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = QColor("#2d3a50")
        self._pulse = False
        self.setFixedSize(12, 12)

    def set_color(self, color_hex: str, pulse: bool = False) -> None:
        self._color = QColor(color_hex)
        self._pulse = pulse
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = min(self.width(), self.height()) / 2 - 1
        if self._pulse:
            glow = QRadialGradient(self.width() / 2, self.height() / 2, r + 3)
            gc = QColor(self._color)
            gc.setAlphaF(0.4)
            glow.setColorAt(0.5, gc)
            gc2 = QColor(self._color)
            gc2.setAlphaF(0.0)
            glow.setColorAt(1.0, gc2)
            p.setBrush(QBrush(glow))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(0, 0, self.width(), self.height())
        p.setBrush(QBrush(self._color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(self.width() / 2 - r), int(self.height() / 2 - r), int(r * 2), int(r * 2))
        p.end()


class SuspicionBar(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = 0.0
        self._max = 10.0
        self.setFixedHeight(8)
        self.setMinimumWidth(120)

    def set_value(self, val: float, max_val: float = 10.0) -> None:
        self._value = max(0.0, min(val, max_val))
        self._max = max_val
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        p.setBrush(QBrush(QColor("#1a2235")))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        ratio = self._value / self._max if self._max > 0 else 0
        fill_w = int(w * ratio)
        if fill_w > 0:
            color = QColor("#00e5a0") if ratio < 0.5 else QColor("#ffb020") if ratio < 0.8 else QColor("#ff3b5c")
            p.setBrush(QBrush(color))
            p.drawRoundedRect(0, 0, fill_w, h, h / 2, h / 2)
        p.end()
