from PyQt6.QtWidgets import QWidget, QPushButton, QLabel, QHBoxLayout, QVBoxLayout
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QBrush, QFont, QLinearGradient, QPen, QPainterPath
import math


class ProtectionOverlay(QWidget):
    unlock_requested = pyqtSignal()
    pin_validated = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self._opacity = 0.92
        self._phase = 0.0
        self._mode = "observer"  # "observer" or "absence"
        self._show_unlock = False
        self._btn_opacity = 0.0
        self._pin_code = ""       # configured PIN
        self._pin_input = ""      # current user input
        self._pin_error = False

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._tick)
        self._anim_timer.setInterval(50)

        # ── Unlock button (observer mode + absence without PIN) ──
        self._unlock_btn = QPushButton("🔓  Déverrouiller l'écran", self)
        self._unlock_btn.setFont(QFont("Segoe UI", 13, QFont.Weight.DemiBold))
        self._unlock_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._unlock_btn.setStyleSheet(self._unlock_style(0.9))
        self._unlock_btn.clicked.connect(self._on_unlock_clicked)
        self._unlock_btn.hide()
        self._unlock_btn.setFixedSize(280, 50)

        self._btn_fade = QPropertyAnimation(self, b"btn_opacity")
        self._btn_fade.setDuration(500)
        self._btn_fade.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # ── PIN pad (absence mode with PIN configured) ──
        self._pin_container = QWidget(self)
        self._pin_container.setStyleSheet("background: transparent;")
        self._pin_container.hide()
        self._build_pin_pad()

    @staticmethod
    def _unlock_style(opacity: float) -> str:
        return f"""QPushButton {{
            background-color: rgba(0, 229, 160, {0.9 * opacity});
            color: rgba(10, 14, 23, {opacity});
            border: none; border-radius: 12px;
            padding: 14px 36px; font-size: 14px; font-weight: 700;
        }}
        QPushButton:hover {{ background-color: rgba(0, 229, 160, {min(1.0, opacity * 1.1)}); }}
        QPushButton:pressed {{ background-color: rgba(0, 179, 125, {opacity}); }}"""

    def _build_pin_pad(self) -> None:
        layout = QVBoxLayout(self._pin_container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._pin_dots = QLabel("", self._pin_container)
        self._pin_dots.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        self._pin_dots.setStyleSheet("color: #e8ecf4; background: transparent; letter-spacing: 12px;")
        self._pin_dots.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pin_dots.setFixedHeight(50)
        layout.addWidget(self._pin_dots)

        self._pin_msg = QLabel("", self._pin_container)
        self._pin_msg.setFont(QFont("Segoe UI", 10))
        self._pin_msg.setStyleSheet("color: #ff3b5c; background: transparent;")
        self._pin_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pin_msg.setFixedHeight(20)
        layout.addWidget(self._pin_msg)

        btn_style = """QPushButton {{
            background: rgba(30, 41, 59, 0.8); color: #e8ecf4;
            border: 1px solid rgba(45, 58, 80, 0.6); border-radius: 28px;
            font-size: 18px; font-weight: 600;
        }}
        QPushButton:hover {{ background: rgba(45, 58, 80, 0.9); border-color: rgba(0, 229, 160, 0.4); }}
        QPushButton:pressed {{ background: rgba(0, 229, 160, 0.3); }}"""

        keys = [
            ["1", "2", "3"],
            ["4", "5", "6"],
            ["7", "8", "9"],
            ["✕", "0", "✓"],
        ]
        for row_keys in keys:
            row = QHBoxLayout()
            row.setSpacing(14)
            row.setAlignment(Qt.AlignmentFlag.AlignCenter)
            for key in row_keys:
                btn = QPushButton(key)
                btn.setFixedSize(56, 56)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setStyleSheet(btn_style)
                btn.clicked.connect(lambda _, k=key: self._on_pin_key(k))
                row.addWidget(btn)
            layout.addLayout(row)

        self._pin_container.setFixedSize(220, 340)

    def _on_pin_key(self, key: str) -> None:
        if key == "✕":
            # Backspace
            self._pin_input = self._pin_input[:-1]
            self._pin_error = False
            self._pin_msg.setText("")
        elif key == "✓":
            # Validate
            if self._pin_input == self._pin_code:
                self._pin_input = ""
                self._pin_error = False
                self.pin_validated.emit()
            else:
                self._pin_error = True
                self._pin_msg.setText("Code incorrect")
                self._pin_input = ""
                QTimer.singleShot(1500, lambda: self._pin_msg.setText(""))
        else:
            if len(self._pin_input) < 4:
                self._pin_input += key
                self._pin_error = False
                self._pin_msg.setText("")
                # Auto-validate on 4 digits
                if len(self._pin_input) == 4:
                    QTimer.singleShot(200, lambda: self._on_pin_key("✓"))

        self._refresh_pin_dots()

    def _refresh_pin_dots(self) -> None:
        filled = len(self._pin_input)
        dots = "●" * filled + "○" * (4 - filled)
        self._pin_dots.setText(dots)

    # ── Properties ──
    def _get_btn_opacity(self) -> float:
        return self._btn_opacity

    def _set_btn_opacity(self, v: float) -> None:
        self._btn_opacity = v
        self._unlock_btn.setStyleSheet(self._unlock_style(v))

    btn_opacity = pyqtProperty(float, _get_btn_opacity, _set_btn_opacity)

    def set_opacity(self, opacity: float) -> None:
        self._opacity = max(0.5, min(1.0, opacity))

    def set_pin_code(self, code: str) -> None:
        self._pin_code = code

    # ── Show modes ──
    def show_protection(self, mode: str = "observer") -> None:
        """mode: 'observer' or 'absence'"""
        from PyQt6.QtWidgets import QApplication
        screen = QApplication.primaryScreen()
        if screen:
            self.setGeometry(screen.geometry())
        self._mode = mode
        self._show_unlock = False
        self._unlock_btn.hide()
        self._pin_container.hide()
        self._pin_input = ""
        self._pin_error = False
        self._btn_opacity = 0.0
        self.show()
        self.raise_()
        self._anim_timer.start()

    def show_unlock_button(self) -> None:
        """Show unlock escape: PIN pad if configured in absence mode, else button."""
        if self._mode == "absence" and self._pin_code and len(self._pin_code) == 4:
            self._show_pin_pad()
        else:
            self._show_unlock_btn()

    def _show_unlock_btn(self) -> None:
        self._show_unlock = True
        self._pin_container.hide()
        self._position_unlock_btn()
        self._unlock_btn.show()
        self._unlock_btn.raise_()
        self._btn_fade.stop()
        self._btn_fade.setStartValue(0.0)
        self._btn_fade.setEndValue(1.0)
        self._btn_fade.start()

    def _show_pin_pad(self) -> None:
        self._show_unlock = True
        self._unlock_btn.hide()
        self._pin_input = ""
        self._pin_error = False
        self._refresh_pin_dots()
        self._pin_msg.setText("")
        self._position_pin_pad()
        self._pin_container.show()
        self._pin_container.raise_()

    def hide_protection(self) -> None:
        self._anim_timer.stop()
        self._unlock_btn.hide()
        self._pin_container.hide()
        self._show_unlock = False
        self._pin_input = ""
        self.hide()

    # ── Positioning ──
    def _position_unlock_btn(self) -> None:
        x = (self.width() - self._unlock_btn.width()) // 2
        y = self.height() - self._unlock_btn.height() - 60
        self._unlock_btn.move(x, y)

    def _position_pin_pad(self) -> None:
        x = (self.width() - self._pin_container.width()) // 2
        y = self.height() // 2 + 40
        self._pin_container.move(x, y)

    def _on_unlock_clicked(self) -> None:
        self.unlock_requested.emit()

    def _tick(self) -> None:
        self._phase += 0.05
        self.update()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._show_unlock:
            self._position_unlock_btn()
            self._position_pin_pad()

    # ── Paint ──
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        if self._mode == "observer":
            self._paint_observer(p, w, h)
        else:
            self._paint_absence(p, w, h)
        p.end()

    def _paint_observer(self, p: QPainter, w: int, h: int) -> None:
        bg = QColor("#0a0e17")
        bg.setAlphaF(self._opacity)
        p.fillRect(0, 0, w, h, bg)

        grad = QLinearGradient(0, 0, w, h)
        c1 = QColor("#00e5a0")
        c1.setAlphaF(0.04 + 0.02 * math.sin(self._phase))
        c2 = QColor("#6366f1")
        c2.setAlphaF(0.03 + 0.02 * math.sin(self._phase + 1.5))
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        p.fillRect(0, 0, w, h, QBrush(grad))

        # Grid
        lc = QColor("#00e5a0")
        lc.setAlphaF(0.06)
        p.setPen(QPen(lc, 1))
        sp = 40
        off = int(self._phase * 10) % sp
        for yy in range(-sp + off, h + sp, sp):
            p.drawLine(0, yy, w, yy)
        for xx in range(-sp + off, w + sp, sp):
            p.drawLine(xx, 0, xx, h)

        # Shield icon
        ss = 80
        cx_s, cy_s = w / 2, h / 2 - ss / 2 - 30
        sc = QColor("#00e5a0")
        sc.setAlphaF(0.5 + 0.2 * math.sin(self._phase * 1.5))
        p.setPen(QPen(sc, 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath()
        path.moveTo(cx_s, cy_s)
        path.lineTo(cx_s + ss / 2, cy_s + ss * 0.3)
        path.lineTo(cx_s + ss * 0.4, cy_s + ss)
        path.lineTo(cx_s, cy_s + ss * 1.15)
        path.lineTo(cx_s - ss * 0.4, cy_s + ss)
        path.lineTo(cx_s - ss / 2, cy_s + ss * 0.3)
        path.closeSubpath()
        p.drawPath(path)
        # Checkmark
        cc = QColor("#00e5a0")
        cc.setAlphaF(0.7)
        p.setPen(QPen(cc, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.drawLine(int(cx_s - 15), int(cy_s + ss * 0.55), int(cx_s - 2), int(cy_s + ss * 0.72))
        p.drawLine(int(cx_s - 2), int(cy_s + ss * 0.72), int(cx_s + 18), int(cy_s + ss * 0.35))

        p.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        tc = QColor("#e8ecf4")
        tc.setAlphaF(0.85)
        p.setPen(tc)
        p.drawText(0, h // 2 + ss // 2 + 10, w, 40, Qt.AlignmentFlag.AlignCenter, "ÉCRAN PROTÉGÉ")
        p.setFont(QFont("Segoe UI", 12))
        stc = QColor("#8892a4")
        stc.setAlphaF(0.7)
        p.setPen(stc)
        p.drawText(0, h // 2 + ss // 2 + 55, w, 30, Qt.AlignmentFlag.AlignCenter, "Un observateur a été détecté")

        if self._show_unlock and self._btn_opacity > 0.3 and not self._pin_container.isVisible():
            p.setFont(QFont("Segoe UI", 9))
            htc = QColor("#8892a4")
            htc.setAlphaF(0.4 * self._btn_opacity)
            p.setPen(htc)
            by = self.height() - self._unlock_btn.height() - 60
            p.drawText(0, by - 26, w, 20, Qt.AlignmentFlag.AlignCenter, "Cliquez ci-dessous pour lever la protection")

    def _paint_absence(self, p: QPainter, w: int, h: int) -> None:
        # Darker, warmer background for absence mode
        bg = QColor("#0c0814")
        bg.setAlphaF(self._opacity)
        p.fillRect(0, 0, w, h, bg)

        grad = QLinearGradient(0, 0, w, h)
        c1 = QColor("#6366f1")
        c1.setAlphaF(0.05 + 0.02 * math.sin(self._phase))
        c2 = QColor("#a855f7")
        c2.setAlphaF(0.04 + 0.02 * math.sin(self._phase + 1.2))
        grad.setColorAt(0, c1)
        grad.setColorAt(1, c2)
        p.fillRect(0, 0, w, h, QBrush(grad))

        # Subtle dot pattern instead of grid
        dot_c = QColor("#6366f1")
        dot_c.setAlphaF(0.08)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(dot_c))
        sp = 30
        off = int(self._phase * 3) % sp
        for yy in range(-sp + off, h + sp, sp):
            for xx in range(-sp + off, w + sp, sp):
                p.drawEllipse(xx - 1, yy - 1, 2, 2)

        # Lock icon
        cx_l = w / 2
        cy_l = h / 2 - 80
        lock_c = QColor("#a855f7")
        lock_c.setAlphaF(0.6 + 0.15 * math.sin(self._phase * 1.2))
        p.setPen(QPen(lock_c, 2.5))
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Shackle (arc)
        shackle_w, shackle_h = 36, 32
        p.drawArc(
            int(cx_l - shackle_w / 2), int(cy_l - shackle_h),
            int(shackle_w), int(shackle_h * 2),
            0, 180 * 16,
        )
        # Body (rounded rect)
        body_w, body_h = 50, 38
        body_r = 6
        p.setPen(QPen(lock_c, 2.5))
        body_fill = QColor("#6366f1")
        body_fill.setAlphaF(0.15)
        p.setBrush(QBrush(body_fill))
        p.drawRoundedRect(
            int(cx_l - body_w / 2), int(cy_l),
            int(body_w), int(body_h), body_r, body_r,
        )
        # Keyhole
        kh_c = QColor("#a855f7")
        kh_c.setAlphaF(0.7)
        p.setBrush(QBrush(kh_c))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(cx_l - 5), int(cy_l + 10), 10, 10)
        p.setPen(QPen(kh_c, 2.5))
        p.drawLine(int(cx_l), int(cy_l + 18), int(cx_l), int(cy_l + 28))

        # Title
        p.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        tc = QColor("#e8ecf4")
        tc.setAlphaF(0.85)
        p.setPen(tc)
        p.drawText(0, int(cy_l + body_h + 24), w, 40, Qt.AlignmentFlag.AlignCenter, "SESSION VERROUILLÉE")

        # Subtitle
        p.setFont(QFont("Segoe UI", 12))
        stc = QColor("#8892a4")
        stc.setAlphaF(0.7)
        p.setPen(stc)
        sub = "Utilisateur absent — Entrez le code PIN" if self._pin_code else "Utilisateur absent"
        p.drawText(0, int(cy_l + body_h + 68), w, 30, Qt.AlignmentFlag.AlignCenter, sub)

        # Hint for unlock button when visible (no PIN)
        if self._show_unlock and self._btn_opacity > 0.3 and not self._pin_container.isVisible():
            p.setFont(QFont("Segoe UI", 9))
            htc = QColor("#8892a4")
            htc.setAlphaF(0.4 * self._btn_opacity)
            p.setPen(htc)
            by = self.height() - self._unlock_btn.height() - 60
            p.drawText(0, by - 26, w, 20, Qt.AlignmentFlag.AlignCenter, "Cliquez ci-dessous pour déverrouiller")

    def mousePressEvent(self, event) -> None:
        pass

    def keyPressEvent(self, event) -> None:
        pass
