"""Bridge loguru messages into Qt signals."""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QObject, Signal


class LogBridge(QObject):
    """Forward loguru records to the GUI."""

    message_emitted = Signal(str)

    def __init__(self, level: str = "INFO") -> None:
        super().__init__()
        self._sink_id = logger.add(self._sink, level=level)

    def _sink(self, message) -> None:  # pragma: no cover - integrates with loguru internals
        text = message.record.get("message", "").rstrip("\n")
        self.message_emitted.emit(text)

    def close(self) -> None:
        logger.remove(self._sink_id)


__all__ = ["LogBridge"]
