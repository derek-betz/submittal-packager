"""Validation helpers for Submittal Packager."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from .config import Config, RequirementConfig
from .models import MessageLevel, ParsedFilename, ValidationMessage


_FILENAME_FIELDS = ("des", "stage", "discipline", "sheet_type", "sheet_range", "ext")


def compile_ignore_patterns(root: Path, ignore_file: Path | None) -> PathSpec | None:
    """Load ignore patterns from a .spignore file."""

    if ignore_file is None or not ignore_file.exists():
        return None
    patterns = ignore_file.read_text().splitlines()
    return PathSpec.from_lines(GitWildMatchPattern, patterns)


def is_ignored(path: Path, spec: PathSpec | None, root: Path) -> bool:
    """Determine if path should be ignored."""

    if spec is None:
        return False
    rel = path.relative_to(root)
    return spec.match_file(str(rel))


def normalize_stage(stage: str, *, case_insensitive: bool) -> str:
    return stage.lower() if case_insensitive else stage


def normalize_sheet_range(raw: str) -> Tuple[int, int | None]:
    """Convert a sheet range string to integers."""

    if "-" in raw:
        start_str, end_str = raw.split("-", 1)
        return int(start_str), int(end_str)
    return int(raw), None


def parse_filename(path: Path, config: Config) -> Tuple[ParsedFilename | None, List[ValidationMessage]]:
    """Parse filename according to configuration rules."""

    name = path.name
    messages: List[ValidationMessage] = []
    if not config.conventions.allow_spaces and " " in name:
        messages.append(ValidationMessage(MessageLevel.ERROR, f"Spaces are not allowed in filename '{name}'"))
        return None, messages

    match = re.match(config.conventions.regex, name)
    if not match and config.conventions.exceptions:
        for exception in config.conventions.exceptions:
            match = re.match(exception.regex, name)
            if match:
                break

    if not match:
        messages.append(ValidationMessage(MessageLevel.ERROR, f"Filename '{name}' does not match convention regex"))
        return None, messages

    data = match.groupdict()
    parsed = ParsedFilename(source=path)
    # Populate simple fields directly from regex groups, but skip 'sheet_range'
    # because we convert it into numeric sheet_start/sheet_end below.
    for field in _FILENAME_FIELDS:
        if field == "sheet_range":
            continue
        if field in data:
            setattr(parsed, field, data[field])

    if parsed.ext and parsed.ext.lower() not in config.conventions.allowed_extensions:
        messages.append(ValidationMessage(MessageLevel.ERROR, f"Extension '{parsed.ext}' is not allowed"))

    sheet_range = data.get("sheet_range")
    if sheet_range:
        start, end = normalize_sheet_range(sheet_range)
        parsed.sheet_start = start
        parsed.sheet_end = end

    if parsed.stage and config.conventions.stage_case_insensitive:
        parsed.stage = parsed.stage.lower()

    if parsed.ext:
        parsed.ext = parsed.ext.lower()

    return parsed, messages


def find_required_artifacts(files: Sequence[Path], requirements: Sequence[RequirementConfig]) -> Dict[str, List[Path]]:
    """Find files matching each requirement pattern."""

    results: Dict[str, List[Path]] = {req.key: [] for req in requirements}
    for file in files:
        for req in requirements:
            patterns = [pattern.strip() for pattern in req.pattern.split("|")]
            if any(fnmatch.fnmatch(file.name.upper(), pattern.upper()) for pattern in patterns):
                results[req.key].append(file)
    return results


def validate_required(files: Sequence[Path], requirements: Sequence[RequirementConfig]) -> List[ValidationMessage]:
    """Validate that all required artifacts exist."""

    matches = find_required_artifacts(files, requirements)
    messages: List[ValidationMessage] = []
    for key, paths in matches.items():
        if not paths:
            messages.append(ValidationMessage(MessageLevel.ERROR, f"Missing required artifact: {key}"))
    return messages


def detect_duplicate_ranges(parsed_files: Sequence[ParsedFilename]) -> List[ValidationMessage]:
    """Detect overlapping sheet ranges within the same discipline."""

    messages: List[ValidationMessage] = []
    by_discipline: Dict[str, List[Tuple[int, int]]] = {}
    for parsed in parsed_files:
        if parsed.discipline and parsed.sheet_start is not None:
            start = parsed.sheet_start
            end = parsed.sheet_end or start
            by_discipline.setdefault(parsed.discipline, []).append((start, end))

    for discipline, ranges in by_discipline.items():
        sorted_ranges = sorted(ranges)
        for i in range(1, len(sorted_ranges)):
            prev = sorted_ranges[i - 1]
            current = sorted_ranges[i]
            if current[0] <= prev[1]:
                messages.append(
                    ValidationMessage(
                        MessageLevel.WARNING,
                        f"Discipline {discipline} has overlapping sheets {prev} and {current}",
                    )
                )
    return messages


__all__ = [
    "compile_ignore_patterns",
    "is_ignored",
    "parse_filename",
    "find_required_artifacts",
    "validate_required",
    "detect_duplicate_ranges",
    "normalize_sheet_range",
]
