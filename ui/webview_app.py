"""Pont pywebview ↔ GuardEngine.

Fenêtre principale : HTML/CSS/JS (ui_web/) affichée par pywebview avec le
backend Qt (gui='qt'). Les widgets Qt (overlay, mini-fenêtre, dialogue de
calibration) continuent à vivre dans la même QApplication.

Les callbacks `js_api` de pywebview sont invoqués dans un thread worker ;
on utilise des signaux QueuedConnection pour tout ce qui touche les
widgets Qt — ils seront traités sur le thread principal.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, Qt, pyqtSignal

from config.settings import Settings
from config.profiles import ProfileManager
from core.engine import GuardEngine
from core.state_machine import GuardState
from core.logger import Logger


_STATE_SLUG = {
    GuardState.IDLE: "idle",
    GuardState.ACTIVE: "active",
    GuardState.PROTECTED: "protected",
    GuardState.SHARING: "sharing",
    GuardState.PAUSED: "paused",
    GuardState.ERROR: "error",
}


class WebBridge(QObject):
    """QObject exposé à JS via pywebview `js_api`."""

    # Signaux de marshalling vers le thread Qt
    _s_power_on = pyqtSignal()
    _s_power_off = pyqtSignal()
    _s_show_calib = pyqtSignal()
    _s_share = pyqtSignal(int)
    _s_dismiss = pyqtSignal()
    _s_reload = pyqtSignal()
    _s_update_scan = pyqtSignal()

    def __init__(self, settings: Settings, profile: ProfileManager, engine: GuardEngine) -> None:
        super().__init__()
        self._settings = settings
        self._profile = profile
        self._engine = engine
        self._log = Logger.get()
        self._window = None
        self._overlay = None
        self._mini = None
        self._calib_result: str | None = None
        self._calib_event = threading.Event()

        # Marshall tout vers le thread principal (QueuedConnection = async safe)
        qc = Qt.ConnectionType.QueuedConnection
        self._s_power_on.connect(self._on_powered_on, qc)
        self._s_power_off.connect(self._on_powered_off, qc)
        self._s_show_calib.connect(self._show_calibration, qc)
        self._s_share.connect(self._engine.grant_share, qc)
        self._s_dismiss.connect(self._engine.dismiss_protection, qc)
        self._s_reload.connect(self._engine.reload_profile, qc)
        self._s_update_scan.connect(self._engine.update_scan_interval, qc)

    def set_window(self, window: Any) -> None:
        self._window = window

    def wire(self, overlay: Any, mini: Any) -> None:
        self._overlay = overlay
        self._mini = mini

    # ── JS API (exposé via pywebview) ───────────────────────────────
    def get_state(self) -> dict:
        e = self._engine
        d = e.last_detection
        return {
            "state": _STATE_SLUG.get(e.state, "idle"),
            "suspicion": float(e.suspicion_score),
            "threshold": int(self._settings.get("suspicion_threshold")),
            "faces": int(d.faces_count),
            "secondary": len(d.secondary_faces) if d.secondary_faces else 0,
            "attention": float(d.attention_score),
            "looking": bool(d.gaze.looking_at_screen) if d.gaze else False,
            "scans": int(e.total_scans),
            "alerts": int(e.total_alerts),
            "session_s": float(e.session_seconds),
            "share_remaining": float(e.share_remaining),
            "share_total": int(self._settings.get("share_duration_s")),
            "calibrated": bool(self._profile.has_encoding),
        }

    def get_settings(self) -> dict:
        keys = [
            "scan_interval_ms", "suspicion_threshold", "suspicion_decay",
            "false_positive_delay", "gaze_yaw_threshold", "gaze_pitch_threshold",
            "camera_preview", "auto_start", "log_enabled", "overlay_opacity",
            "share_duration_s", "camera_index", "pin_code",
            "absence_threshold_multiplier",
        ]
        return {k: self._settings.get(k) for k in keys}

    def set_settings(self, payload: dict) -> bool:
        pin = (payload.get("pin_code") or "").strip()
        if pin and (len(pin) != 4 or not pin.isdigit()):
            return False
        for key, val in payload.items():
            if key == "pin_code":
                self._settings.set(key, pin)
            else:
                self._settings.set(key, val)
        self._s_update_scan.emit()
        self._log.info("Settings applied via web UI")
        return True

    def toggle_power(self, on: bool) -> bool:
        # Pywebview invoke us on a worker thread; engine.start()/stop()
        # touch QTimer which must run on the Qt thread. Marshall both.
        if on:
            self._s_power_on.emit()
        else:
            self._s_power_off.emit()
        return True

    def grant_share(self, duration_s: int) -> None:
        self._s_share.emit(int(duration_s))

    def dismiss_protection(self) -> None:
        self._s_dismiss.emit()

    def reset_profile(self) -> None:
        self._profile.clear()
        self._settings.set("calibration_done", False)
        self._s_reload.emit()

    def start_calibration(self) -> str:
        cam = self._engine.get_camera()
        if cam is None or not cam.isOpened():
            return "need_power"
        self._calib_result = None
        self._calib_event.clear()
        self._s_show_calib.emit()
        self._calib_event.wait(timeout=120)
        return self._calib_result or "cancelled"

    # ── Handlers (toujours exécutés sur le thread Qt via QueuedConn) ─
    def _on_powered_on(self) -> None:
        if not self._engine.start():
            # engine.start() already emitted error_occurred; state becomes
            # ERROR which the next poll will reflect in the UI.
            return
        if self._mini is not None:
            self._mini.position_bottom_right()
            self._mini.show()
            self._mini.set_camera_enabled(self._settings.get("camera_preview"))
        if not self._profile.has_encoding:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, self._show_calibration)

    def _on_powered_off(self) -> None:
        self._engine.stop()
        if self._mini is not None:
            self._mini.hide()
        if self._overlay is not None:
            self._overlay.hide_protection()

    def _show_calibration(self) -> None:
        from ui.calibration_dialog import CalibrationDialog
        cam = self._engine.get_camera()
        was_scanning = self._engine.state == GuardState.ACTIVE
        if was_scanning:
            self._engine.pause()
        dlg = CalibrationDialog(cam)
        ok = dlg.exec()
        enc = dlg.get_encoding() if ok else None
        if enc is not None:
            self._profile.set_encoding(enc)
            self._settings.set("calibration_done", True)
            self._engine.reload_profile()
            self._calib_result = "ok"
        else:
            self._calib_result = "cancelled" if ok == 0 else "failed"
        if was_scanning:
            self._engine.resume()
        self._calib_event.set()


def launch(settings: Settings, profile: ProfileManager, engine: GuardEngine,
           overlay: Any, mini: Any) -> WebBridge:
    """Create the webview window and return the bridge.

    The caller must then call webview.start(gui='qt') to enter the shared
    Qt + web event loop.
    """
    import webview

    bridge = WebBridge(settings, profile, engine)
    bridge.wire(overlay, mini)

    base = Path(__file__).resolve().parent.parent
    html = base / "ui_web" / "index.html"

    win = webview.create_window(
        "ScreenGuard",
        str(html),
        js_api=bridge,
        width=1100, height=760, min_size=(880, 620),
        background_color="#1d2025",
    )
    bridge.set_window(win)
    return bridge
