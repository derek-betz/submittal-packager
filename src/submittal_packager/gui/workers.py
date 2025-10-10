"""Background workers that execute packager tasks without freezing the UI."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal

from ..config import load_config
from ..packager import ValidationFailure, run_package, run_report, validate_directory
from .models import ProjectSettings


class ValidateWorker(QObject):
    """Run validation in a background thread."""

    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, settings: ProjectSettings) -> None:
        super().__init__()
        self._settings = settings

    def run(self) -> None:
        try:
            config = load_config(self._settings.config_path)
            if self._settings.disable_keyword_scan:
                config.checks.pdf_text_scan.enabled = False
            result = validate_directory(
                self._settings.root_directory,
                config,
                self._settings.stage,
                strict=self._settings.strict,
                ignore_file=self._settings.ignore_file,
                map_file=self._settings.map_file,
                exclude_paths=[self._settings.config_path],
            )
        except Exception as exc:  # pragma: no cover - runtime error surface to GUI
            logger.exception("Validation failed")
            self.failed.emit(f"Validation failed: {exc}")
        else:
            self.finished.emit(result)


class PackageWorker(QObject):
    """Run packaging and emit progress updates."""

    finished = Signal(object)
    failed = Signal(str, object)
    progress = Signal(str)

    def __init__(self, settings: ProjectSettings) -> None:
        super().__init__()
        self._settings = settings

    def run(self) -> None:
        out_dir = self._settings.output_directory
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.exception("Unable to create output directory")
            self.failed.emit(f"Unable to create output directory: {exc}", None)
            return

        log_path = out_dir / "packager.log"
        try:
            self.progress.emit("Running packaging workflow…")
            result = run_package(
                self._settings.root_directory,
                self._settings.config_path,
                self._settings.stage,
                out_dir=out_dir,
                strict=self._settings.strict,
                ignore_file=self._settings.ignore_file,
                no_scan=self._settings.disable_keyword_scan,
                log_path=log_path,
                map_file=self._settings.map_file,
            )
        except ValidationFailure as failure:
            logger.warning("Packaging aborted due to validation errors")
            self.failed.emit("Validation errors detected during packaging", failure.result)
        except Exception as exc:  # pragma: no cover - runtime error surface to GUI
            logger.exception("Packaging failed")
            self.failed.emit(f"Packaging failed: {exc}", None)
        else:
            self.progress.emit("Packaging completed successfully.")
            self.finished.emit(result)


class ReportWorker(QObject):
    """Generate the HTML report in the background."""

    finished = Signal(Path)
    failed = Signal(str)

    def __init__(self, settings: ProjectSettings) -> None:
        super().__init__()
        self._settings = settings

    def run(self) -> None:
        try:
            path = run_report(
                self._settings.root_directory,
                self._settings.config_path,
                self._settings.stage,
                out_dir=self._settings.output_directory,
            )
        except Exception as exc:  # pragma: no cover - runtime error surface to GUI
            logger.exception("Report generation failed")
            self.failed.emit(f"Report generation failed: {exc}")
        else:
            self.finished.emit(path)


__all__ = ["ValidateWorker", "PackageWorker", "ReportWorker"]
