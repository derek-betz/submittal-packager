"""Main window and navigation shell for the GUI."""

from __future__ import annotations

from typing import List, Optional
from PySide6.QtCore import QThread
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..models import ValidationResult
from .forms import ProjectSetupView
from .logging_bridge import LogBridge
from .models import ProjectSettings
from .views import PackagingProgressView, ValidationResultsView
from .workers import PackageWorker, ReportWorker, ValidateWorker


class MainWindow(QMainWindow):
    """Application shell with sidebar navigation."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("INDOT Submittal Packager")
        self.resize(1180, 780)

        self._threads: List[QThread] = []

        container = QWidget(self)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        body = QWidget(container)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._nav = QListWidget(body)
        self._nav.setMaximumWidth(220)
        self._nav.addItem(QListWidgetItem("Project Setup"))
        self._nav.addItem(QListWidgetItem("Validation Results"))
        self._nav.addItem(QListWidgetItem("Packaging Log"))
        self._nav.setCurrentRow(0)
        self._nav.setAlternatingRowColors(True)

        self._stack = QStackedWidget(body)
        self._project_view = ProjectSetupView(parent=self)
        self._validation_view = ValidationResultsView(parent=self)
        self._packaging_view = PackagingProgressView(parent=self)
        self._stack.addWidget(self._project_view)
        self._stack.addWidget(self._validation_view)
        self._stack.addWidget(self._packaging_view)

        self._log_bridge = LogBridge()
        self._log_bridge.message_emitted.connect(self._packaging_view.append_message)

        content = QWidget(body)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.addWidget(self._stack)

        body_layout.addWidget(self._nav)
        body_layout.addWidget(content, stretch=1)
        layout.addWidget(body)
        self.setCentralWidget(container)

        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)
        self._project_view.request_validate.connect(self._start_validation)
        self._project_view.request_package.connect(self._start_packaging)
        self._project_view.request_report.connect(self._start_report)

    # ------------------------------------------------------------------
    # Worker orchestration helpers
    # ------------------------------------------------------------------
    def _launch_worker(
        self,
        worker,
        *,
        on_finished=None,
        on_failed=None,
        on_progress=None,
    ) -> None:
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)

        def _cleanup() -> None:
            thread.quit()
            thread.wait()
            worker.deleteLater()

        if hasattr(worker, "finished") and on_finished:
            worker.finished.connect(lambda *args: self._handle_result(_cleanup, on_finished, *args))
        else:
            worker.finished.connect(lambda *args: _cleanup())

        if hasattr(worker, "failed"):
            worker.failed.connect(lambda *args: self._handle_failure(_cleanup, on_failed, *args))

        if on_progress and hasattr(worker, "progress"):
            worker.progress.connect(on_progress)

        thread.finished.connect(thread.deleteLater)
        self._threads.append(thread)
        thread.finished.connect(lambda: self._threads.remove(thread))
        thread.start()

    @staticmethod
    def _handle_result(cleanup, callback, *args) -> None:
        cleanup()
        if callback:
            callback(*args)

    @staticmethod
    def _handle_failure(cleanup, callback, *args) -> None:
        cleanup()
        if callback:
            callback(*args)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------
    def _start_validation(self, settings: ProjectSettings) -> None:
        self._project_view.setEnabled(False)
        self._packaging_view.set_status("Running validation…")
        self._validation_view.clear()

        def _done(result: ValidationResult) -> None:
            self._project_view.setEnabled(True)
            self._validation_view.show_result(result)
            self._packaging_view.set_status("Validation complete.")
            self._stack.setCurrentWidget(self._validation_view)

        def _fail(message: str) -> None:
            self._project_view.setEnabled(True)
            self._packaging_view.set_status("Validation failed.")
            QMessageBox.critical(self, "Validation failed", message)

        worker = ValidateWorker(settings)
        self._launch_worker(worker, on_finished=_done, on_failed=_fail)

    def _start_packaging(self, settings: ProjectSettings) -> None:
        self._project_view.setEnabled(False)
        self._packaging_view.clear()
        self._packaging_view.set_status("Packaging in progress…")
        self._stack.setCurrentWidget(self._packaging_view)

        def _progress(message: str) -> None:
            self._packaging_view.append_message(message)
            self._packaging_view.set_status(message)

        def _done(result: ValidationResult) -> None:
            self._project_view.setEnabled(True)
            self._validation_view.show_result(result)
            self._packaging_view.append_message("Packaging completed without errors.")
            QMessageBox.information(self, "Packaging complete", "Package created successfully.")

        def _fail(message: str, result: Optional[ValidationResult]) -> None:
            self._project_view.setEnabled(True)
            self._packaging_view.append_message(message)
            QMessageBox.warning(self, "Packaging halted", message)
            if result:
                self._validation_view.show_result(result)
                self._stack.setCurrentWidget(self._validation_view)

        worker = PackageWorker(settings)
        self._launch_worker(worker, on_finished=_done, on_failed=_fail, on_progress=_progress)

    def _start_report(self, settings: ProjectSettings) -> None:
        self._project_view.setEnabled(False)
        self._packaging_view.clear()
        self._packaging_view.set_status("Generating validation report…")
        self._packaging_view.append_message("Generating validation report…")
        self._stack.setCurrentWidget(self._packaging_view)

        def _done(path) -> None:
            self._project_view.setEnabled(True)
            self._packaging_view.append_message(f"Report generated at {path}")
            QMessageBox.information(self, "Report generated", f"HTML report written to:\n{path}")

        def _fail(message: str) -> None:
            self._project_view.setEnabled(True)
            self._packaging_view.append_message(message)
            QMessageBox.critical(self, "Report failed", message)

        worker = ReportWorker(settings)
        self._launch_worker(worker, on_finished=_done, on_failed=_fail)

    def closeEvent(self, event) -> None:  # pragma: no cover - UI only
        if hasattr(self, "_log_bridge"):
            self._log_bridge.close()
        super().closeEvent(event)


__all__ = ["MainWindow"]
