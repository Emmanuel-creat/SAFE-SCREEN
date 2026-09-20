import sys
import os
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
    os.environ["QT_LOGGING_RULES"] = "*.debug=false"

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon

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
    from core.logger import Logger

    settings = Settings()
    Logger(settings.config_dir)

    # Load QSS stylesheet
    qss_path = os.path.join(base_dir, "ui", "styles.qss")
    if not os.path.exists(qss_path):
        qss_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui", "styles.qss")
    if os.path.exists(qss_path):
        with open(qss_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())

    from ui.main_window import MainWindow

    window = MainWindow(settings)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    try:
        main()
    except Exception:
        error_text = traceback.format_exc()
        _crash_log(error_text)
        _show_crash_dialog(error_text)
        sys.exit(1)
