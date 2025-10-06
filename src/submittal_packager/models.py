"""Shared models for validation and manifest data."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable, List, Optional


class MessageLevel(str, Enum):
    """Severity for validation messages."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(slots=True)
class ValidationMessage:
    """Represents a validation message."""

    level: MessageLevel
    text: str


@dataclass(slots=True)
class ParsedFilename:
    """Result of parsing a filename according to project conventions."""

    source: Path
    des: Optional[str] = None
    stage: Optional[str] = None
    discipline: Optional[str] = None
    sheet_type: Optional[str] = None
    sheet_start: Optional[int] = None
    sheet_end: Optional[int] = None
    ext: Optional[str] = None

    @property
    def sheet_count(self) -> Optional[int]:
        if self.sheet_start is None:
            return None
        if self.sheet_end is None:
            return 1
        return self.sheet_end - self.sheet_start + 1


@dataclass(slots=True)
class ManifestEntry:
    """Manifest row describing a single file."""

    relative_path: str
    size_bytes: int
    pages: int
    checksum: str
    des: Optional[str] = None
    stage: Optional[str] = None
    discipline: Optional[str] = None
    sheet_type: Optional[str] = None
    sheet_start: Optional[int] = None
    sheet_end: Optional[int] = None
    ext: Optional[str] = None


@dataclass(slots=True)
class ValidationResult:
    """Outcome of validation run."""

    manifest: List[ManifestEntry] = field(default_factory=list)
    errors: List[ValidationMessage] = field(default_factory=list)
    warnings: List[ValidationMessage] = field(default_factory=list)

    def extend(self, messages: Iterable[ValidationMessage]) -> None:
        for msg in messages:
            if msg.level == MessageLevel.ERROR:
                self.errors.append(msg)
            elif msg.level == MessageLevel.WARNING:
                self.warnings.append(msg)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    @property
    def has_warnings(self) -> bool:
        return bool(self.warnings)


__all__ = [
    "MessageLevel",
    "ValidationMessage",
    "ParsedFilename",
    "ManifestEntry",
    "ValidationResult",
]
