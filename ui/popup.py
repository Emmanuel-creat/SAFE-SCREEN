"""Popup de décision affiché quand un observateur est détecté."""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen

from ui.widgets import COLORS


class DecisionPopup(QWidget):
    protection_confirmed = pyqtSignal()
    share_requested = pyqtSignal(int)
    dismissed = pyqtSignal()

    _DURATIONS = {
        "30 secondes": 30,
        "1 minute": 60,
        "5 minutes": 300,
        "15 minutes": 900,
    }

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(440, 340)
        self._build()

    def _build(self) -> None:
        lo = QVBoxLayout(self)
        lo.setContentsMargins(28, 26, 28, 26)
        lo.setSpacing(14)

        title = QLabel("Observateur détecté")
        title.setFont(QFont("Segoe UI Variable Display", 16, QFont.Weight.DemiBold))
        title.setStyleSheet(f"color: {COLORS['warning']}; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(title)

        desc = QLabel(
            "Un visage supplémentaire a été détecté.\n"
            "La protection visuelle est activée."
        )
        desc.setFont(QFont("Segoe UI", 11))
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        lo.addWidget(desc)
        lo.addSpacing(8)

        keep = QPushButton("Maintenir la protection")
        keep.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        keep.setCursor(Qt.CursorShape.PointingHandCursor)
        keep.setStyleSheet(
            f"QPushButton {{ background: {COLORS['danger']}; color: #1a0b0e; "
            f"border: none; border-radius: 12px; padding: 13px; font-weight: 700; }} "
            f"QPushButton:hover {{ background: {COLORS['danger_dim']}; color: #fff; }}"
        )
        keep.clicked.connect(lambda: (self.hide(), self.protection_confirmed.emit()))
        lo.addWidget(keep)

        share_row = QHBoxLayout()
        share_row.setSpacing(10)
        self._combo = QComboBox()
        for k in self._DURATIONS:
            self._combo.addItem(k)
        self._combo.setCurrentIndex(1)
        self._combo.setFixedWidth(140)
        self._combo.setStyleSheet(
            f"QComboBox {{ background: {COLORS['bg_tertiary']}; "
            f"border: 1px solid {COLORS['border_light']}; border-radius: 10px; "
            f"padding: 10px 12px; color: {COLORS['text_primary']}; }}"
            f"QComboBox QAbstractItemView {{ background: {COLORS['bg_card']}; "
            f"border: 1px solid {COLORS['border_light']}; "
            f"selection-background-color: {COLORS['accent_dim']}; "
            f"color: {COLORS['text_primary']}; }}"
        )
        share_row.addWidget(self._combo)

        share = QPushButton("Partager temporairement")
        share.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        share.setCursor(Qt.CursorShape.PointingHandCursor)
        share.setStyleSheet(
            f"QPushButton {{ background: {COLORS['sharing']}; color: #0b1226; "
            f"border: none; border-radius: 12px; padding: 11px 16px; font-weight: 700; }} "
            f"QPushButton:hover {{ background: {COLORS['sharing_dim']}; color: #fff; }}"
        )
        share.clicked.connect(
            lambda: (
                self.hide(),
                self.share_requested.emit(
                    self._DURATIONS.get(self._combo.currentText(), 60)
                ),
            )
        )
        share_row.addWidget(share)
        lo.addLayout(share_row)

        dismiss = QPushButton("Fausse alerte — Désactiver")
        dismiss.setFont(QFont("Segoe UI", 10))
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {COLORS['text_muted']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 10px; padding: 9px; }} "
            f"QPushButton:hover {{ color: {COLORS['text_secondary']}; "
            f"border-color: {COLORS['border_light']}; }}"
        )
        dismiss.clicked.connect(lambda: (self.hide(), self.dismissed.emit()))
        lo.addWidget(dismiss)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(COLORS["bg_secondary"])
        bg.setAlphaF(0.97)
        p.setBrush(QBrush(bg))
        border = QColor(COLORS["warning"])
        border.setAlphaF(0.38)
        p.setPen(QPen(border, 1.5))
        p.drawRoundedRect(2, 2, self.width() - 4, self.height() - 4, 18, 18)
        p.end()

    def show_centered(self) -> None:
        from PyQt6.QtWidgets import QApplication
        s = QApplication.primaryScreen()
        if s:
            g = s.geometry()
            self.move(
                g.x() + (g.width() - self.width()) // 2,
                g.y() + (g.height() - self.height()) // 2,
            )
        self.show()
        self.raise_()
        self.activateWindow()
