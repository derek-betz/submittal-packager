"""Application bootstrap for the Submittal Packager GUI."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QStyle

from .main_window import MainWindow


def _init_logging() -> None:
    """Configure loguru to play nicely with the GUI."""

    # Remove default stderr handler so log messages flow through custom sinks.
    logger.remove()
    log_dir = Path.home() / ".submittal_packager"
    log_dir.mkdir(parents=True, exist_ok=True)
    logfile = log_dir / "gui.log"
    logger.add(logfile, rotation="1 week", retention=5, level="INFO")


def main() -> int:
    """Entry point used by setuptools and PyInstaller."""

    _init_logging()
    policy = getattr(Qt.HighDpiScaleFactorRoundingPolicy, "PassThrough", None)
    if policy is None:
        policy = getattr(Qt.HighDpiScaleFactorRoundingPolicy, "RoundPreferFloor", None)
    if policy is not None and hasattr(QApplication, "setHighDpiScaleFactorRoundingPolicy"):
        QApplication.setHighDpiScaleFactorRoundingPolicy(policy)
    app = QApplication(sys.argv)
    app.setOrganizationName("INDOT")
    app.setApplicationName("Submittal Packager")
    window = MainWindow()
    window.setWindowIcon(window.style().standardIcon(QStyle.SP_DesktopIcon))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
