"""Reusable Qt widgets for the Submittal Packager GUI."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class PathPicker(QWidget):
    """Widget combining a line edit and a browse button."""

    path_changed = Signal(Path)

    def __init__(
        self,
        caption: str,
        *,
        mode: str = "file",
        placeholder: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._caption = caption
        self._mode = mode
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._edit = QLineEdit(self)
        if placeholder:
            self._edit.setPlaceholderText(placeholder)
        layout.addWidget(self._edit, stretch=1)
        button = QPushButton("Browse…", self)
        button.clicked.connect(self._choose_path)
        layout.addWidget(button)
        self._edit.textChanged.connect(self._emit_path)

    def set_path(self, path: Optional[Path]) -> None:
        self._edit.setText(str(path or ""))

    def path(self) -> Path | None:
        value = self._edit.text().strip()
        return Path(value) if value else None

    def _choose_path(self) -> None:
        current = self.path()
        if self._mode == "directory":
            directory = QFileDialog.getExistingDirectory(self, self._caption, str(current or Path.home()))
            if directory:
                self._edit.setText(directory)
        elif self._mode == "save":
            file_path, _ = QFileDialog.getSaveFileName(self, self._caption, str(current or Path.home()))
            if file_path:
                self._edit.setText(file_path)
        else:
            file_path, _ = QFileDialog.getOpenFileName(self, self._caption, str(current or Path.home()))
            if file_path:
                self._edit.setText(file_path)

    def _emit_path(self, text: str) -> None:
        if text:
            self.path_changed.emit(Path(text))


class KeyValueLabel(QWidget):
    """Display a label/value pair commonly used for metadata."""

    def __init__(self, label: str, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        name = QLabel(f"<b>{label}:</b>", self)
        self._value = QLabel("—", self)
        self._value.setTextInteractionFlags(
            self._value.textInteractionFlags() | Qt.TextSelectableByMouse
        )
        layout.addWidget(name)
        layout.addWidget(self._value, stretch=1)

    def set_value(self, value: str | None) -> None:
        self._value.setText(value or "—")


__all__ = ["PathPicker", "KeyValueLabel"]
