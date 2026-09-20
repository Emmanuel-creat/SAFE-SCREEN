import cv2
import numpy as np
from enum import Enum, auto
from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt6.QtCore import Qt, QPoint, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QColor, QFont, QPainter, QBrush, QPen, QImage, QPixmap
from ui.widgets import COLORS, StatusIndicator, SuspicionBar
from core.state_machine import GuardState


class DockSide(Enum):
    NONE = auto()
    RIGHT = auto()
    LEFT = auto()


class MiniWindow(QWidget):
    EXPANDED_W = 280
    EXPANDED_H = 240
    COMPACT_H = 142
    COLLAPSED_W = 28
    COLLAPSED_H = 90

    def __init__(self) -> None:
        super().__init__()
        self._always_on_top = True
        self._apply_flags()
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._expanded = True
        self._dock_side = DockSide.RIGHT
        self._drag_pos: QPoint | None = None
        self._camera_enabled = False
        self._tab_status_color = COLORS["text_muted"]
        self._screen_geo = QRect(0, 0, 1920, 1080)

        self._slide_anim = QPropertyAnimation(self, b"geometry")
        self._slide_anim.setDuration(250)
        self._slide_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._build_panel()
        self._build_tab()
        self._update_visibility()

    def _apply_flags(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self._always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)

    @property
    def _current_h(self) -> int:
        return self.EXPANDED_H if self._camera_enabled else self.COMPACT_H

    def _build_panel(self) -> None:
        self._panel = QWidget(self)
        layout = QVBoxLayout(self._panel)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(5)

        header = QHBoxLayout()
        header.setSpacing(5)
        self._status_dot = StatusIndicator()
        header.addWidget(self._status_dot)
        self._state_label = QLabel("INACTIF")
        self._state_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self._state_label.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        header.addWidget(self._state_label)
        header.addStretch()
        self._time_label = QLabel("00:00")
        self._time_label.setFont(QFont("Segoe UI", 9))
        self._time_label.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        header.addWidget(self._time_label)

        btn_style = f"""QPushButton {{ background: {COLORS['bg_tertiary']}; color: {COLORS['text_muted']};
            border: 1px solid {COLORS['border']}; border-radius: 4px; font-size: 11px; padding: 0; }}
            QPushButton:hover {{ color: {COLORS['text_secondary']}; border-color: {COLORS['border_light']}; background: {COLORS['bg_card']}; }}"""

        self._bg_btn = QPushButton("⇩")
        self._bg_btn.setToolTip("Arrière-plan")
        self._bg_btn.setFixedSize(22, 22)
        self._bg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._bg_btn.setStyleSheet(btn_style)
        self._bg_btn.clicked.connect(self._toggle_bg)
        header.addWidget(self._bg_btn)

        self._collapse_btn = QPushButton("›")
        self._collapse_btn.setToolTip("Replier")
        self._collapse_btn.setFixedSize(22, 22)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setStyleSheet(btn_style.replace(COLORS['text_secondary'], COLORS['accent']).replace(COLORS['border_light'], COLORS['accent_dim']))
        self._collapse_btn.clicked.connect(self._collapse)
        header.addWidget(self._collapse_btn)
        layout.addLayout(header)

        self._camera_label = QLabel()
        self._camera_label.setFixedHeight(90)
        self._camera_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._camera_label.setStyleSheet(f"background: {COLORS['bg_tertiary']}; border-radius: 6px;")
        self._camera_label.setFont(QFont("Segoe UI", 8))
        self._camera_label.hide()
        layout.addWidget(self._camera_label)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self._faces_w = self._stat_widget("Visages", "0")
        stats.addWidget(self._faces_w)
        self._att_w = self._stat_widget("Attention", "—")
        stats.addWidget(self._att_w)
        self._scans_w = self._stat_widget("Scans", "0")
        stats.addWidget(self._scans_w)
        layout.addLayout(stats)

        susp = QHBoxLayout()
        sl = QLabel("Suspicion")
        sl.setFont(QFont("Segoe UI", 8))
        sl.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        susp.addWidget(sl)
        self._susp_bar = SuspicionBar()
        susp.addWidget(self._susp_bar, 1)
        self._susp_val = QLabel("0.0")
        self._susp_val.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        self._susp_val.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        susp.addWidget(self._susp_val)
        layout.addLayout(susp)

        self._share_label = QLabel("")
        self._share_label.setFont(QFont("Segoe UI", 9, QFont.Weight.DemiBold))
        self._share_label.setStyleSheet(f"color: {COLORS['sharing']}; background: transparent;")
        self._share_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._share_label.hide()
        layout.addWidget(self._share_label)

    def _stat_widget(self, label: str, value: str) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        vl = QVBoxLayout(w)
        vl.setContentsMargins(0, 0, 0, 0)
        vl.setSpacing(1)
        val = QLabel(value)
        val.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        val.setStyleSheet(f"color: {COLORS['text_primary']}; background: transparent;")
        val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        val.setObjectName(f"stat_val_{label}")
        vl.addWidget(val)
        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 8))
        lbl.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vl.addWidget(lbl)
        return w

    def _build_tab(self) -> None:
        self._tab = QWidget(self)
        self._tab.setGeometry(0, 0, self.COLLAPSED_W, self.COLLAPSED_H)
        self._tab.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tab.hide()

    # ── visibility ──
    def _update_visibility(self) -> None:
        if self._expanded:
            h = self._current_h
            self._panel.show()
            self._tab.hide()
            self.setFixedSize(self.EXPANDED_W, h)
            self._panel.setGeometry(0, 0, self.EXPANDED_W, h)
        else:
            self._panel.hide()
            self._tab.show()
            self.setFixedSize(self.COLLAPSED_W, self.COLLAPSED_H)
            self._tab.setGeometry(0, 0, self.COLLAPSED_W, self.COLLAPSED_H)

    def _refresh_size(self) -> None:
        if self._expanded:
            h = self._current_h
            self.setFixedSize(self.EXPANDED_W, h)
            self._panel.setGeometry(0, 0, self.EXPANDED_W, h)

    def _refresh_geo(self) -> None:
        from PyQt6.QtWidgets import QApplication
        s = QApplication.primaryScreen()
        if s:
            self._screen_geo = s.availableGeometry()

    # ── collapse / expand ──
    def _collapse(self) -> None:
        if not self._expanded:
            return
        self._detect_side()
        target = self._collapsed_rect()
        h = self._current_h
        edge = QRect(target.x(), self.y(), self.EXPANDED_W, h)
        if self._dock_side == DockSide.RIGHT:
            edge.moveLeft(self._screen_geo.right() - 10)
        else:
            edge.moveLeft(self._screen_geo.left() - self.EXPANDED_W + 10)
        self._slide_anim.stop()
        self._slide_anim.setStartValue(self.geometry())
        self._slide_anim.setEndValue(edge)
        self._slide_anim.finished.connect(self._finish_collapse)
        self._slide_anim.start()

    def _finish_collapse(self) -> None:
        self._slide_anim.finished.disconnect(self._finish_collapse)
        self._expanded = False
        self._update_visibility()
        self.setGeometry(self._collapsed_rect())

    def _expand(self) -> None:
        if self._expanded:
            return
        self._expanded = True
        self._update_visibility()
        self._slide_anim.stop()
        self._slide_anim.setStartValue(self.geometry())
        self._slide_anim.setEndValue(self._expanded_rect())
        self._slide_anim.start()

    def _detect_side(self) -> None:
        self._refresh_geo()
        cx = self.x() + self.width() / 2
        sx = self._screen_geo.x() + self._screen_geo.width() / 2
        self._dock_side = DockSide.RIGHT if cx >= sx else DockSide.LEFT

    def _collapsed_rect(self) -> QRect:
        self._refresh_geo()
        g = self._screen_geo
        y = max(g.y() + 40, min(self.y(), g.bottom() - self.COLLAPSED_H - 40))
        x = g.right() - self.COLLAPSED_W + 1 if self._dock_side == DockSide.RIGHT else g.left()
        return QRect(x, y, self.COLLAPSED_W, self.COLLAPSED_H)

    def _expanded_rect(self) -> QRect:
        self._refresh_geo()
        g = self._screen_geo
        h = self._current_h
        y = max(g.y() + 20, min(self.y(), g.bottom() - h - 20))
        x = g.right() - self.EXPANDED_W - 20 if self._dock_side == DockSide.RIGHT else g.left() + 20
        return QRect(x, y, self.EXPANDED_W, h)

    # ── background ──
    def _toggle_bg(self) -> None:
        self._always_on_top = not self._always_on_top
        vis = self.isVisible()
        pos, sz = self.pos(), self.size()
        self._apply_flags()
        self._bg_btn.setText("⇧" if not self._always_on_top else "⇩")
        self._bg_btn.setToolTip("Premier plan" if not self._always_on_top else "Arrière-plan")
        if vis:
            self.show()
            self.setGeometry(QRect(pos, sz))
            if self._expanded:
                self._update_visibility()

    # ── public API ──
    def set_camera_enabled(self, on: bool) -> None:
        self._camera_enabled = on
        if on:
            self._camera_label.show()
        else:
            self._camera_label.setPixmap(QPixmap())
            self._camera_label.setText("")
            self._camera_label.hide()
        self._refresh_size()

    def update_frame(self, frame: np.ndarray | None) -> None:
        if not self._camera_enabled or frame is None:
            return
        small = cv2.resize(frame, (256, 90))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._camera_label.setText("")
        self._camera_label.setPixmap(QPixmap.fromImage(img))

    def update_state(self, state: GuardState) -> None:
        m = {
            GuardState.IDLE: ("INACTIF", COLORS["text_muted"], False),
            GuardState.ACTIVE: ("ACTIF", COLORS["accent"], True),
            GuardState.PROTECTED: ("PROTÉGÉ", COLORS["danger"], True),
            GuardState.SHARING: ("PARTAGE", COLORS["sharing"], True),
            GuardState.PAUSED: ("PAUSE", COLORS["warning"], False),
            GuardState.ERROR: ("ERREUR", COLORS["danger"], True),
        }
        label, color, pulse = m.get(state, ("—", COLORS["text_muted"], False))
        self._state_label.setText(label)
        self._state_label.setStyleSheet(f"color: {color}; background: transparent;")
        self._status_dot.set_color(color, pulse)
        self._tab_status_color = color
        if state != GuardState.SHARING:
            self._share_label.hide()
        if not self._expanded:
            self.update()

    def update_stats(self, faces: int, attention: float, suspicion: float,
                     threshold: float, scans: int, session_s: float) -> None:
        self._find("Visages").setText(str(faces))
        self._find("Attention").setText(f"{attention:.0%}" if attention > 0 else "—")
        self._find("Scans").setText(str(scans))
        self._susp_bar.set_value(suspicion, threshold * 2)
        self._susp_val.setText(f"{suspicion:.1f}")
        m, s = int(session_s) // 60, int(session_s) % 60
        self._time_label.setText(f"{m:02d}:{s:02d}")

    def update_share_remaining(self, sec: float) -> None:
        if sec > 0:
            m, s = int(sec) // 60, int(sec) % 60
            self._share_label.setText(f"Partage : {m:02d}:{s:02d}")
            self._share_label.show()
        else:
            self._share_label.hide()

    def _find(self, label: str) -> QLabel:
        r = self.findChild(QLabel, f"stat_val_{label}")
        return r if r else QLabel()

    def position_bottom_right(self) -> None:
        self._refresh_geo()
        g = self._screen_geo
        if self._expanded:
            h = self._current_h
            self.move(g.right() - self.EXPANDED_W - 20, g.bottom() - h - 20)
        else:
            self.setGeometry(self._collapsed_rect())

    # ── paint ──
    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._expanded:
            bg = QColor(COLORS["bg_secondary"])
            bg.setAlphaF(0.93)
            p.setBrush(QBrush(bg))
            bc = QColor(COLORS["border_light"])
            bc.setAlphaF(0.5)
            p.setPen(QPen(bc, 1))
            p.drawRoundedRect(1, 1, self.width() - 2, self.height() - 2, 12, 12)
        else:
            w, h = self.width(), self.height()
            bg = QColor(COLORS["bg_secondary"])
            bg.setAlphaF(0.92)
            p.setBrush(QBrush(bg))
            bc = QColor(COLORS["border_light"])
            bc.setAlphaF(0.5)
            p.setPen(QPen(bc, 1))
            if self._dock_side == DockSide.RIGHT:
                p.drawRoundedRect(0, 0, w + 4, h, 6, 6)
            else:
                p.drawRoundedRect(-4, 0, w + 4, h, 6, 6)
            dc = QColor(self._tab_status_color)
            p.setBrush(QBrush(dc))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(w // 2 - 4, h // 2 - 20, 8, 8)
            ac = QColor(COLORS["text_muted"])
            ac.setAlphaF(0.7)
            p.setPen(QPen(ac, 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            ay = h // 2 + 10
            ax = w // 2
            if self._dock_side == DockSide.RIGHT:
                p.drawLine(ax + 4, ay - 6, ax - 3, ay)
                p.drawLine(ax - 3, ay, ax + 4, ay + 6)
            else:
                p.drawLine(ax - 4, ay - 6, ax + 3, ay)
                p.drawLine(ax + 3, ay, ax - 4, ay + 6)
        p.end()

    # ── mouse ──
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._expanded:
                self._expand()
            else:
                self._drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        if self._expanded and self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
