from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QSpinBox, QDoubleSpinBox, QCheckBox,
    QSlider, QScrollArea, QFrame, QMessageBox, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen
from config.settings import Settings
from config.profiles import ProfileManager
from core.engine import GuardEngine
from core.state_machine import GuardState
from core.logger import Logger
from vision.mediapipe_detector import DetectionResult
from ui.widgets import COLORS, PowerButton, StatusIndicator
from ui.mini_window import MiniWindow
from ui.overlay import ProtectionOverlay
from ui.calibration_dialog import CalibrationDialog


# ── Inline decision popup ──
class _DecisionPopup(QWidget):
    from PyQt6.QtCore import pyqtSignal
    protection_confirmed = pyqtSignal()
    share_requested = pyqtSignal(int)
    dismissed = pyqtSignal()

    _DURATIONS = {"30 secondes": 30, "1 minute": 60, "5 minutes": 300, "15 minutes": 900}

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(420, 320)
        self._build()

    def _build(self) -> None:
        lo = QVBoxLayout(self)
        lo.setContentsMargins(24, 24, 24, 24)
        lo.setSpacing(14)
        t = QLabel("⚠  Observateur détecté")
        t.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {COLORS['warning']}; background: transparent;")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lo.addWidget(t)
        d = QLabel("Un visage supplémentaire a été détecté.\nLa protection visuelle est activée.")
        d.setFont(QFont("Segoe UI", 11))
        d.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        d.setWordWrap(True)
        lo.addWidget(d)
        lo.addSpacing(6)

        b1 = QPushButton("Maintenir la protection")
        b1.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        b1.setStyleSheet(f"QPushButton {{ background: {COLORS['danger']}; color: white; border: none; border-radius: 10px; padding: 12px; }} QPushButton:hover {{ background: {COLORS['danger_dim']}; }}")
        b1.clicked.connect(lambda: (self.hide(), self.protection_confirmed.emit()))
        lo.addWidget(b1)

        sr = QHBoxLayout()
        sr.setSpacing(8)
        self._combo = QComboBox()
        for k in self._DURATIONS:
            self._combo.addItem(k)
        self._combo.setCurrentIndex(1)
        self._combo.setStyleSheet(f"QComboBox {{ background: {COLORS['bg_tertiary']}; border: 1px solid {COLORS['border_light']}; border-radius: 8px; padding: 8px 12px; color: {COLORS['text_primary']}; min-width: 130px; }}")
        sr.addWidget(self._combo)
        b2 = QPushButton("Partager temporairement")
        b2.setFont(QFont("Segoe UI", 11, QFont.Weight.DemiBold))
        b2.setStyleSheet(f"QPushButton {{ background: {COLORS['sharing']}; color: white; border: none; border-radius: 10px; padding: 12px 16px; }} QPushButton:hover {{ background: {COLORS['sharing_dim']}; }}")
        b2.clicked.connect(lambda: (self.hide(), self.share_requested.emit(self._DURATIONS.get(self._combo.currentText(), 60))))
        sr.addWidget(b2)
        lo.addLayout(sr)

        b3 = QPushButton("Fausse alerte — Désactiver")
        b3.setFont(QFont("Segoe UI", 10))
        b3.setStyleSheet(f"QPushButton {{ background: transparent; color: {COLORS['text_muted']}; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 8px; }} QPushButton:hover {{ color: {COLORS['text_secondary']}; border-color: {COLORS['border_light']}; }}")
        b3.clicked.connect(lambda: (self.hide(), self.dismissed.emit()))
        lo.addWidget(b3)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(COLORS["bg_secondary"])
        bg.setAlphaF(0.97)
        p.setBrush(QBrush(bg))
        bc = QColor(COLORS["warning"])
        bc.setAlphaF(0.4)
        p.setPen(QPen(bc, 1.5))
        p.drawRoundedRect(2, 2, self.width() - 4, self.height() - 4, 16, 16)
        p.end()

    def show_centered(self) -> None:
        from PyQt6.QtWidgets import QApplication
        s = QApplication.primaryScreen()
        if s:
            g = s.geometry()
            self.move(g.x() + (g.width() - self.width()) // 2, g.y() + (g.height() - self.height()) // 2)
        self.show()
        self.raise_()
        self.activateWindow()


class MainWindow(QMainWindow):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings
        self._log = Logger.get()
        self._profile = ProfileManager(self._settings.config_dir)

        self.setWindowTitle("ScreenGuard")
        self.setMinimumSize(500, 700)
        self.resize(520, 740)

        self._engine = GuardEngine(settings, self._profile)
        self._overlay = ProtectionOverlay()
        self._popup = _DecisionPopup()
        self._mini = MiniWindow()

        self._connect()
        self._build_ui()

        self._stats_timer = QTimer(self)
        self._stats_timer.timeout.connect(self._refresh_stats)
        self._stats_timer.start(500)

        if self._settings.get("auto_start"):
            QTimer.singleShot(600, self._auto_start)

    def _connect(self) -> None:
        self._engine.state_changed.connect(self._on_state)
        self._engine.detection_update.connect(self._on_detection)
        self._engine.protection_triggered.connect(self._on_protection)
        self._engine.protection_cleared.connect(self._on_clear)
        self._engine.share_expired.connect(lambda: self._log.info("Share expired"))
        self._engine.error_occurred.connect(lambda m: QMessageBox.warning(self, "Erreur", m))
        self._popup.protection_confirmed.connect(lambda: self._overlay.show_unlock_button())
        self._popup.share_requested.connect(self._engine.grant_share)
        self._popup.dismissed.connect(self._engine.dismiss_protection)
        self._overlay.unlock_requested.connect(self._engine.dismiss_protection)
        self._overlay.pin_validated.connect(self._engine.dismiss_protection)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        ml = QVBoxLayout(central)
        ml.setContentsMargins(24, 20, 24, 20)
        ml.setSpacing(14)

        # Header
        hdr = QHBoxLayout()
        logo = QLabel("◈ SCREENGUARD")
        logo.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        logo.setStyleSheet(f"color: {COLORS['accent']}; letter-spacing: 3px; background: transparent;")
        hdr.addWidget(logo)
        hdr.addStretch()
        self._si = StatusIndicator()
        hdr.addWidget(self._si)
        self._gsl = QLabel("Inactif")
        self._gsl.setFont(QFont("Segoe UI", 11))
        self._gsl.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        hdr.addWidget(self._gsl)
        ml.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {COLORS['border']};")
        ml.addWidget(sep)

        # Power
        pwr = QVBoxLayout()
        pwr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pwr.setSpacing(8)
        self._pbtn = PowerButton()
        self._pbtn.toggled.connect(self._on_power)
        pwr.addWidget(self._pbtn, alignment=Qt.AlignmentFlag.AlignCenter)
        self._plbl = QLabel("DÉMARRER")
        self._plbl.setFont(QFont("Segoe UI", 12, QFont.Weight.DemiBold))
        self._plbl.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        self._plbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pwr.addWidget(self._plbl)
        ml.addLayout(pwr)

        # Settings scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        sw = QWidget()
        sw.setStyleSheet("background: transparent;")
        sl = QVBoxLayout(sw)
        sl.setSpacing(12)

        # Detection
        dg = QGroupBox("  Détection")
        dl = QVBoxLayout()
        dl.setSpacing(8)
        self._sp_scan = self._spin_row(dl, "Intervalle scan (ms)", 100, 5000, self._settings.get("scan_interval_ms"), 50)
        self._sp_thresh = self._spin_row(dl, "Seuil suspicion", 1, 20, self._settings.get("suspicion_threshold"), 1)
        self._sp_decay = self._dspin_row(dl, "Décroissance score", 0.1, 5.0, self._settings.get("suspicion_decay"), 0.1)
        self._sp_fp = self._spin_row(dl, "Délai anti-faux positifs", 1, 10, self._settings.get("false_positive_delay"), 1)
        dg.setLayout(dl)
        sl.addWidget(dg)

        # Gaze
        gg = QGroupBox("  Regard")
        gl = QVBoxLayout()
        gl.setSpacing(8)
        self._sp_yaw = self._dspin_row(gl, "Seuil lacet (°)", 5.0, 60.0, self._settings.get("gaze_yaw_threshold"), 1.0)
        self._sp_pitch = self._dspin_row(gl, "Seuil tangage (°)", 5.0, 60.0, self._settings.get("gaze_pitch_threshold"), 1.0)
        gg.setLayout(gl)
        sl.addWidget(gg)

        # Display
        dpg = QGroupBox("  Affichage")
        dpl = QVBoxLayout()
        dpl.setSpacing(8)
        self._chk_cam = QCheckBox("Retour caméra")
        self._chk_cam.setChecked(self._settings.get("camera_preview"))
        self._chk_cam.toggled.connect(self._on_cam_toggle)
        dpl.addWidget(self._chk_cam)
        orow = QHBoxLayout()
        orow.addWidget(QLabel("Opacité protection"))
        self._sl_opacity = QSlider(Qt.Orientation.Horizontal)
        self._sl_opacity.setRange(50, 100)
        self._sl_opacity.setValue(int(self._settings.get("overlay_opacity") * 100))
        self._sl_opacity.valueChanged.connect(lambda v: (self._ov.setText(f"{v}%"), self._settings.set("overlay_opacity", v / 100)))
        orow.addWidget(self._sl_opacity)
        self._ov = QLabel(f"{self._sl_opacity.value()}%")
        self._ov.setFixedWidth(40)
        self._ov.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        orow.addWidget(self._ov)
        dpl.addLayout(orow)
        self._sp_share = self._spin_row(dpl, "Durée partage (s)", 10, 3600, self._settings.get("share_duration_s"), 10)
        dpg.setLayout(dpl)
        sl.addWidget(dpg)

        # System
        sg = QGroupBox("  Système")
        sgl = QVBoxLayout()
        sgl.setSpacing(8)
        self._sp_cam = self._spin_row(sgl, "Index caméra", 0, 10, self._settings.get("camera_index"), 1)
        self._chk_auto = QCheckBox("Démarrer automatiquement")
        self._chk_auto.setChecked(self._settings.get("auto_start"))
        self._chk_auto.toggled.connect(lambda v: self._settings.set("auto_start", v))
        sgl.addWidget(self._chk_auto)
        self._chk_log = QCheckBox("Activer les logs")
        self._chk_log.setChecked(self._settings.get("log_enabled"))
        self._chk_log.toggled.connect(lambda v: self._settings.set("log_enabled", v))
        sgl.addWidget(self._chk_log)
        sg.setLayout(sgl)
        sl.addWidget(sg)

        # Security
        from PyQt6.QtWidgets import QLineEdit
        secg = QGroupBox("  Sécurité")
        secl = QVBoxLayout()
        secl.setSpacing(8)

        pin_row = QHBoxLayout()
        pin_lbl = QLabel("Code PIN (4 chiffres)")
        pin_lbl.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        pin_row.addWidget(pin_lbl)
        pin_row.addStretch()
        self._pin_input = QLineEdit()
        self._pin_input.setPlaceholderText("Aucun")
        self._pin_input.setMaxLength(4)
        self._pin_input.setFixedWidth(100)
        self._pin_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._pin_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLORS['bg_tertiary']}; border: 1px solid {COLORS['border_light']};
                border-radius: 6px; padding: 6px 12px; color: {COLORS['text_primary']};
                font-size: 16px; letter-spacing: 6px; text-align: center;
            }}
        """)
        current_pin = self._settings.get("pin_code")
        if current_pin:
            self._pin_input.setText(current_pin)
        pin_row.addWidget(self._pin_input)
        secl.addLayout(pin_row)

        pin_hint = QLabel("Laisser vide = déverrouillage par bouton. Utilisé en cas d'absence.")
        pin_hint.setFont(QFont("Segoe UI", 8))
        pin_hint.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        pin_hint.setWordWrap(True)
        secl.addWidget(pin_hint)

        self._sp_abs_mult = self._dspin_row(secl, "Délai absence (×seuil)", 1.5, 5.0,
                                             self._settings.get("absence_threshold_multiplier"), 0.5)

        secg.setLayout(secl)
        sl.addWidget(secg)

        # Calibration
        cg = QGroupBox("  Calibration")
        cgl = QVBoxLayout()
        cgl.setSpacing(8)
        self._cal_status = QLabel("Non calibré" if not self._profile.has_encoding else "Calibré ✓")
        self._cal_status.setFont(QFont("Segoe UI", 10))
        color = COLORS["accent"] if self._profile.has_encoding else COLORS["warning"]
        self._cal_status.setStyleSheet(f"color: {color}; background: transparent;")
        cgl.addWidget(self._cal_status)
        cal_btn = QPushButton("Lancer la calibration")
        cal_btn.setStyleSheet(f"QPushButton {{ background: {COLORS['accent_dim']}; color: {COLORS['bg_primary']}; border: none; border-radius: 8px; padding: 10px; font-weight: 600; }} QPushButton:hover {{ background: {COLORS['accent']}; }}")
        cal_btn.clicked.connect(self._run_calibration)
        cgl.addWidget(cal_btn)
        reset_btn = QPushButton("Réinitialiser le profil")
        reset_btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {COLORS['text_muted']}; border: 1px solid {COLORS['border']}; border-radius: 8px; padding: 8px; }} QPushButton:hover {{ color: {COLORS['danger']}; border-color: {COLORS['danger']}; }}")
        reset_btn.clicked.connect(self._reset_profile)
        cgl.addWidget(reset_btn)
        cg.setLayout(cgl)
        sl.addWidget(cg)

        # Apply
        abtn = QPushButton("Appliquer les paramètres")
        abtn.setStyleSheet(f"QPushButton {{ background: {COLORS['accent_dim']}; color: {COLORS['bg_primary']}; border: none; border-radius: 8px; padding: 10px; font-weight: 600; }} QPushButton:hover {{ background: {COLORS['accent']}; }}")
        abtn.clicked.connect(self._apply)
        sl.addWidget(abtn)
        sl.addStretch()
        scroll.setWidget(sw)
        ml.addWidget(scroll, 1)

        ft = QLabel("v2.0 — MediaPipe Face Mesh · 100% local · Aucune donnée transmise")
        ft.setFont(QFont("Segoe UI", 8))
        ft.setStyleSheet(f"color: {COLORS['text_muted']}; background: transparent;")
        ft.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ml.addWidget(ft)

    # ── helpers ──
    def _spin_row(self, layout, label, mn, mx, val, step) -> QSpinBox:
        r = QHBoxLayout()
        l = QLabel(label)
        l.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        r.addWidget(l)
        r.addStretch()
        s = QSpinBox()
        s.setRange(mn, mx)
        s.setValue(val)
        s.setSingleStep(step)
        s.setFixedWidth(100)
        r.addWidget(s)
        layout.addLayout(r)
        return s

    def _dspin_row(self, layout, label, mn, mx, val, step) -> QDoubleSpinBox:
        r = QHBoxLayout()
        l = QLabel(label)
        l.setStyleSheet(f"color: {COLORS['text_secondary']}; background: transparent;")
        r.addWidget(l)
        r.addStretch()
        s = QDoubleSpinBox()
        s.setRange(mn, mx)
        s.setValue(val)
        s.setSingleStep(step)
        s.setDecimals(1)
        s.setFixedWidth(100)
        r.addWidget(s)
        layout.addLayout(r)
        return s

    # ── actions ──
    def _auto_start(self) -> None:
        self._pbtn.active = True
        self._on_power(True)

    def _on_power(self, on: bool) -> None:
        if on:
            if self._engine.start():
                self._plbl.setText("ACTIF")
                self._mini.position_bottom_right()
                self._mini.show()
                self._mini.set_camera_enabled(self._settings.get("camera_preview"))
                if not self._profile.has_encoding:
                    QTimer.singleShot(500, self._run_calibration)
            else:
                self._pbtn.active = False
                self._plbl.setText("ERREUR")
        else:
            self._engine.stop()
            self._plbl.setText("DÉMARRER")
            self._mini.hide()
            self._overlay.hide_protection()
            self._popup.hide()

    def _on_state(self, state: GuardState) -> None:
        m = {
            GuardState.IDLE: ("Inactif", COLORS["text_muted"], False),
            GuardState.ACTIVE: ("Actif", COLORS["accent"], True),
            GuardState.PROTECTED: ("Protégé", COLORS["danger"], True),
            GuardState.SHARING: ("Partage", COLORS["sharing"], True),
            GuardState.PAUSED: ("Pause", COLORS["warning"], False),
            GuardState.ERROR: ("Erreur", COLORS["danger"], True),
        }
        label, color, pulse = m.get(state, ("—", COLORS["text_muted"], False))
        self._gsl.setText(label)
        self._gsl.setStyleSheet(f"color: {color}; background: transparent;")
        self._si.set_color(color, pulse)
        self._mini.update_state(state)
        if state == GuardState.ACTIVE:
            self._plbl.setText("ACTIF")
        elif state == GuardState.PROTECTED:
            self._plbl.setText("PROTÉGÉ")
        elif state == GuardState.SHARING:
            self._plbl.setText("PARTAGE")

    def _on_detection(self, r: DetectionResult) -> None:
        if self._settings.get("camera_preview"):
            self._mini.update_frame(r.raw_frame)

    def _on_protection(self, reason: str = "observer") -> None:
        self._overlay.set_opacity(self._settings.get("overlay_opacity"))
        pin = self._settings.get("pin_code")
        self._overlay.set_pin_code(pin if isinstance(pin, str) else "")
        if reason == "absence":
            self._overlay.show_protection(mode="absence")
            # Absence: show unlock/PIN immediately, no popup
            self._overlay.show_unlock_button()
        else:
            self._overlay.show_protection(mode="observer")
            self._popup.show_centered()

    def _on_clear(self) -> None:
        self._overlay.hide_protection()

    def _on_cam_toggle(self, on: bool) -> None:
        self._settings.set("camera_preview", on)
        self._mini.set_camera_enabled(on)

    def _apply(self) -> None:
        self._settings.set("scan_interval_ms", self._sp_scan.value())
        self._settings.set("suspicion_threshold", self._sp_thresh.value())
        self._settings.set("suspicion_decay", self._sp_decay.value())
        self._settings.set("false_positive_delay", self._sp_fp.value())
        self._settings.set("share_duration_s", self._sp_share.value())
        self._settings.set("camera_index", self._sp_cam.value())
        self._settings.set("gaze_yaw_threshold", self._sp_yaw.value())
        self._settings.set("gaze_pitch_threshold", self._sp_pitch.value())
        # PIN: only save if empty or exactly 4 digits
        pin_text = self._pin_input.text().strip()
        if pin_text == "" or (len(pin_text) == 4 and pin_text.isdigit()):
            self._settings.set("pin_code", pin_text)
        else:
            self._pin_input.setText(self._settings.get("pin_code") or "")
        self._settings.set("absence_threshold_multiplier", self._sp_abs_mult.value())
        self._engine.update_scan_interval()
        self._log.info("Settings applied")

    def _run_calibration(self) -> None:
        cam = self._engine.get_camera()
        if cam is None or not cam.isOpened():
            QMessageBox.warning(self, "Calibration", "Activez le système d'abord (bouton ON).")
            return
        was_scanning = self._engine.state == GuardState.ACTIVE
        if was_scanning:
            self._engine.pause()
        dlg = CalibrationDialog(cam, self)
        result = dlg.exec()
        if result and dlg.get_encoding() is not None:
            enc = dlg.get_encoding()
            self._profile.set_encoding(enc)
            self._settings.set("calibration_done", True)
            self._engine.reload_profile()
            self._cal_status.setText("Calibré ✓")
            self._cal_status.setStyleSheet(f"color: {COLORS['accent']}; background: transparent;")
            self._log.info("Calibration completed")
        if was_scanning:
            self._engine.resume()

    def _reset_profile(self) -> None:
        self._profile.clear()
        self._settings.set("calibration_done", False)
        self._engine.reload_profile()
        self._cal_status.setText("Non calibré")
        self._cal_status.setStyleSheet(f"color: {COLORS['warning']}; background: transparent;")

    def _refresh_stats(self) -> None:
        e = self._engine
        d = e.last_detection
        self._mini.update_stats(
            d.faces_count, d.attention_score, e.suspicion_score,
            self._settings.get("suspicion_threshold"), e.total_scans, e.session_seconds,
        )
        if e.state == GuardState.SHARING:
            self._mini.update_share_remaining(e.share_remaining)

    def closeEvent(self, event) -> None:
        self._engine.stop()
        self._overlay.hide_protection()
        self._popup.hide()
        self._mini.hide()
        event.accept()
