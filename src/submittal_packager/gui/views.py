"""Data presentation widgets for validation output and packaging logs."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import ManifestEntry, MessageLevel, ValidationMessage, ValidationResult


class ValidationResultsView(QWidget):
    """Display validation results grouped by severity."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._summary = QLabel("Run validation to see results.", self)
        self._summary.setWordWrap(True)
        layout.addWidget(self._summary)

        self._messages = QTreeWidget(self)
        self._messages.setHeaderLabels(["Severity", "Message"])
        self._messages.setColumnWidth(0, 120)
        layout.addWidget(self._messages, stretch=1)

        self._manifest_table = QTableWidget(self)
        self._manifest_table.setColumnCount(6)
        self._manifest_table.setHorizontalHeaderLabels(
            [
                "Relative Path",
                "Stage",
                "Discipline",
                "Sheet Type",
                "Sheets",
                "Pages",
            ]
        )
        self._manifest_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._manifest_table, stretch=2)

    def clear(self) -> None:
        self._summary.setText("Run validation to see results.")
        self._messages.clear()
        self._manifest_table.setRowCount(0)

    def show_result(self, result: ValidationResult) -> None:
        self._messages.clear()
        self._manifest_table.setRowCount(0)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        counts = [
            f"Errors: {len(result.errors)}",
            f"Warnings: {len(result.warnings)}",
            f"Sheets: {sum(entry.pages for entry in result.manifest)}",
            f"Files: {len(result.manifest)}",
        ]
        self._summary.setText(f"Validation completed at {timestamp}. " + " • ".join(counts))
        self._populate_messages("Errors", result.errors)
        self._populate_messages("Warnings", result.warnings)
        self._populate_manifest(result.manifest)

    def _populate_messages(self, label: str, messages: Iterable[ValidationMessage]) -> None:
        root = QTreeWidgetItem(self._messages, [label, ""])
        severity = label.lower()
        color = {
            "errors": Qt.red,
            "warnings": Qt.darkYellow,
        }.get(severity)
        if color:
            root.setForeground(0, color)
        count = 0
        for message in messages:
            item = QTreeWidgetItem(root, [message.level.value.upper(), message.text])
            if message.level == MessageLevel.ERROR:
                item.setForeground(0, Qt.red)
            elif message.level == MessageLevel.WARNING:
                item.setForeground(0, Qt.darkYellow)
            count += 1
        root.setText(0, f"{label} ({count})")
        root.setExpanded(True)

    def _populate_manifest(self, manifest: Iterable[ManifestEntry]) -> None:
        entries = list(manifest)
        self._manifest_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            sheet_range = ""
            if entry.sheet_start and entry.sheet_end:
                sheet_range = f"{entry.sheet_start}-{entry.sheet_end}"
            elif entry.sheet_start:
                sheet_range = str(entry.sheet_start)
            values = [
                entry.relative_path,
                entry.stage or "",
                entry.discipline or "",
                entry.sheet_type or "",
                sheet_range,
                str(entry.pages),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self._manifest_table.setItem(row, column, item)
        self._manifest_table.resizeColumnsToContents()


class PackagingProgressView(QWidget):
    """Streaming view of packaging progress and log output."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self._status = QLabel("Ready.", self)
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        self._log = QPlainTextEdit(self)
        self._log.setReadOnly(True)
        layout.addWidget(self._log, stretch=1)

    def append_message(self, message: str) -> None:
        self._log.appendPlainText(message)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())

    def set_status(self, message: str) -> None:
        self._status.setText(message)

    def clear(self) -> None:
        self._log.clear()
        self._status.setText("Ready.")


__all__ = ["ValidationResultsView", "PackagingProgressView"]
