"""ScreenGuard — point d'entrée.

Interface principale : HTML/CSS/JS (dossier ui_web/) affichée par pywebview.
Overlay plein écran, mini-fenêtre flottante et dialogue de calibration restent
en PyQt6. Pywebview est lancé avec gui='qt' pour partager la même boucle
d'événements que les widgets Qt.
"""
import os
import sys
import traceback
from pathlib import Path


def _crash_log(msg: str) -> None:
    try:
        log_dir = Path.home() / ".screenguard"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "crash.log", "w", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass


def _show_crash_dialog(error_text: str) -> None:
    try:
        from PyQt6.QtWidgets import QApplication, QMessageBox
        app = QApplication.instance() or QApplication(sys.argv)
        box = QMessageBox()
        box.setWindowTitle("ScreenGuard — Erreur au démarrage")
        box.setIcon(QMessageBox.Icon.Critical)
        box.setText("L'application a rencontré une erreur au démarrage.")
        box.setDetailedText(error_text)
        box.setInformativeText(
            "Détails enregistrés dans :\n"
            f"{Path.home() / '.screenguard' / 'crash.log'}"
        )
        box.exec()
    except Exception:
        print(f"SCREENGUARD CRASH:\n{error_text}", file=sys.stderr)
        input("Appuyez sur Entrée pour fermer...")


def main() -> None:
    os.environ.setdefault("QT_LOGGING_RULES", "*.debug=false")

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from PyQt6.QtCore import QTimer

    # QApplication must exist before any QWidget. pywebview(gui='qt') reuses it.
    app = QApplication(sys.argv)
    app.setApplicationName("ScreenGuard")
    app.setOrganizationName("ScreenGuard")

    if getattr(sys, "frozen", False):
        base_dir = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(base_dir, "assets", "icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    from config.settings import Settings
    from config.profiles import ProfileManager
    from core.engine import GuardEngine
    from core.logger import Logger

    settings = Settings()
    Logger(settings.config_dir)
    profile = ProfileManager(settings.config_dir)

    qss_path = os.path.join(base_dir, "ui", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    # Create Qt widgets up-front on the main thread
    from ui.mini_window import MiniWindow
    from ui.overlay import ProtectionOverlay
    from ui.popup import DecisionPopup

    engine = GuardEngine(settings, profile)
    overlay = ProtectionOverlay()
    mini = MiniWindow()
    popup = DecisionPopup()

    # ── Wire engine ↔ Qt widgets ────────────────────────────────────
    def on_protection(reason: str) -> None:
        overlay.set_opacity(settings.get("overlay_opacity"))
        pin = settings.get("pin_code")
        overlay.set_pin_code(pin if isinstance(pin, str) else "")
        if reason == "absence":
            overlay.show_protection(mode="absence")
            overlay.show_unlock_button()
        else:
            overlay.show_protection(mode="observer")
            popup.show_centered()

    def on_detection(result) -> None:
        if settings.get("camera_preview"):
            mini.update_frame(result.raw_frame)

    def refresh_mini() -> None:
        d = engine.last_detection
        mini.update_stats(
            d.faces_count, d.attention_score, engine.suspicion_score,
            settings.get("suspicion_threshold"), engine.total_scans, engine.session_seconds,
        )
        from core.state_machine import GuardState as _GS
        if engine.state == _GS.SHARING:
            mini.update_share_remaining(engine.share_remaining)

    engine.state_changed.connect(mini.update_state)
    engine.detection_update.connect(on_detection)
    engine.protection_triggered.connect(on_protection)
    engine.protection_cleared.connect(overlay.hide_protection)
    popup.protection_confirmed.connect(overlay.show_unlock_button)
    popup.share_requested.connect(engine.grant_share)
    popup.dismissed.connect(engine.dismiss_protection)
    overlay.unlock_requested.connect(engine.dismiss_protection)
    overlay.pin_validated.connect(engine.dismiss_protection)

    stats_timer = QTimer()
    stats_timer.timeout.connect(refresh_mini)
    stats_timer.start(500)

    # ── Launch the web UI (shares the Qt event loop) ────────────────
    from ui.webview_app import launch
    launch(settings, profile, engine, overlay, mini)

    # Auto-start if configured — delayed so the window is visible first
    if settings.get("auto_start"):
        QTimer.singleShot(900, lambda: engine.start())

    import webview
    webview.start(gui="qt", debug=False)

    # On close, cleanly stop engine and hide auxiliaries
    engine.stop()
    overlay.hide_protection()
    popup.hide()
    mini.hide()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_text = traceback.format_exc()
        _crash_log(error_text)
        _show_crash_dialog(error_text)
        sys.exit(1)
