import logging
import os
import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from erm import audio, database
from erm.dashboard import MainDashboardWindow

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _load_dotenv() -> None:
    """Load key=value pairs from a .env file next to main.py (dev) or the EXE (frozen)."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent
    env_file = base / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    _load_dotenv()
    database.init_db()
    audio.ensure_alert_sound()

    # Prevent Qt from rescaling the UI when Windows display DPI changes
    # (e.g. dragging to a different monitor or Windows auto-adjusting scale).
    # Floor rounding keeps the scale factor stable instead of jumping.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.Floor
    )
    os.environ.setdefault("QT_SCALE_FACTOR", "1")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # cross-platform style that respects custom CSS on Windows
    icon_path = Path(__file__).parent / "assets" / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainDashboardWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
    