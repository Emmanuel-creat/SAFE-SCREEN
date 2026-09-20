import cv2
import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen, QImage, QPixmap
from vision.calibrator import Calibrator
from ui.widgets import COLORS


class CalibrationDialog(QDialog):
    def __init__(self, camera: cv2.VideoCapture | None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Calibration ScreenGuard")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(460, 440)
        self.setModal(True)

        self._camera = camera
        self._calibrator = Calibrator()
        self._encoding: np.ndarray | None = None
        self._running = False

        self._build_ui()

        self._capture_timer = QTimer(self)
        self._capture_timer.timeout.connect(self._capture_tick)

        self._preview_timer = QTimer(self)
        self._preview_timer.timeout.connect(self._update_preview)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        title = QLabel("Calibration du visage")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Regardez la caméra bien en face.\n"
            "Restez immobile pendant la capture."
        )
        desc.setFont(QFont("Segoe UI", 11))
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._preview = QLabel()
        self._preview.setFixedHeight(200)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            f"background: {COLORS['bg_tertiary']}; border-radius: 8px;"
        )
        self._preview.setText("Caméra...")
        layout.addWidget(self._preview)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setFixedHeight(18)
        layout.addWidget(self._progress)

        self._status = QLabel("Appuyez sur Démarrer")
        self._status.setFont(QFont("Segoe UI", 10))
        self._status.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._start_btn = QPushButton("Démarrer la calibration")
        self._start_btn.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent']};
                color: {COLORS['bg_primary']};
                border: none; border-radius: 10px;
                padding: 12px 24px; font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {COLORS['accent_dim']}; }}
        """)
        self._start_btn.clicked.connect(self._start_calibration)
        btn_row.addWidget(self._start_btn)

        self._cancel_btn = QPushButton("Annuler")
        self._cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px; padding: 12px 24px;
            }}
            QPushButton:hover {{
                color: {COLORS['text_secondary']};
                border-color: {COLORS['border_light']};
            }}
        """)
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        layout.addLayout(btn_row)

    def _start_calibration(self) -> None:
        if self._camera is None or not self._camera.isOpened():
            self._status.setText("Erreur : caméra non disponible")
            return
        self._running = True
        self._calibrator.reset()
        self._start_btn.setEnabled(False)
        self._start_btn.setText("Capture en cours...")
        self._preview_timer.start(60)
        self._capture_timer.start(Calibrator.CAPTURE_INTERVAL_MS)
        self._status.setText("Regardez la caméra...")

    def _capture_tick(self) -> None:
        if self._camera is None or not self._camera.isOpened():
            self._stop("Caméra perdue")
            return

        ret, frame = self._camera.read()
        if not ret or frame is None:
            return

        ok, msg = self._calibrator.process_frame(frame)
        self._status.setText(msg)
        self._progress.setValue(int(self._calibrator.progress * 100))

        if self._calibrator.is_complete:
            self._encoding = self._calibrator.compute_final_encoding()
            self._stop("Calibration réussie !" if self._encoding is not None else "Échec de la calibration")
            if self._encoding is not None:
                QTimer.singleShot(800, self.accept)

    def _update_preview(self) -> None:
        if self._camera is None or not self._camera.isOpened():
            return
        ret, frame = self._camera.read()
        if not ret or frame is None:
            return
        small = cv2.resize(frame, (400, 200))
        rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
        self._preview.setText("")
        self._preview.setPixmap(QPixmap.fromImage(img))

    def _stop(self, msg: str) -> None:
        self._capture_timer.stop()
        self._preview_timer.stop()
        self._running = False
        self._status.setText(msg)
        self._start_btn.setEnabled(True)
        self._start_btn.setText("Recommencer")

    def get_encoding(self) -> np.ndarray | None:
        return self._encoding

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(COLORS["bg_secondary"])
        bg.setAlphaF(0.97)
        p.setBrush(QBrush(bg))
        border = QColor(COLORS["accent"])
        border.setAlphaF(0.3)
        p.setPen(QPen(border, 1.5))
        p.drawRoundedRect(2, 2, self.width() - 4, self.height() - 4, 16, 16)
        p.end()

    def closeEvent(self, event) -> None:
        self._capture_timer.stop()
        self._preview_timer.stop()
        super().closeEvent(event)
