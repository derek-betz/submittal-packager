"""Data models used by the GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(slots=True)
class ProjectSettings:
    """User supplied configuration collected from the setup form."""

    stage: str
    root_directory: Path
    config_path: Path
    output_directory: Path
    ignore_file: Optional[Path]
    map_file: Optional[Path]
    strict: bool
    disable_keyword_scan: bool


__all__ = ["ProjectSettings"]
