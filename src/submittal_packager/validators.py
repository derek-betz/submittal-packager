"""Validation helpers for Submittal Packager."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from pathspec import PathSpec
from pathspec.patterns import GitWildMatchPattern

from .config import Config, RequirementConfig, StageArtifacts
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


def resolve_stage_config(
    stage_name: str | None, config: Config
) -> Tuple[str | None, StageArtifacts | None]:
    """Return the configured stage entry for a parsed stage name."""

    if not stage_name:
        return None, None

    for key, stage_config in config.stages.items():
        if key == stage_name:
            return key, stage_config
        if config.conventions.stage_case_insensitive and key.lower() == stage_name.lower():
            return key, stage_config
    return None, None


def normalize_sheet_range(raw: str) -> Tuple[int, int | None]:
    """Convert a sheet range string to integers."""

    if "-" in raw:
        start_str, end_str = raw.split("-", 1)
        return int(start_str), int(end_str)
    return int(raw), None


def _normalize_token(value: str) -> str:
    """Normalize a string for fuzzy comparisons."""

    return re.sub(r"[^a-z0-9]", "", value.lower())


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

    raw_stage = data.get("stage")
    if raw_stage:
        parsed.stage = normalize_stage(raw_stage, case_insensitive=config.conventions.stage_case_insensitive)
    stage_key, stage_config = resolve_stage_config(raw_stage, config)
    parsed.stage_key = stage_key

    if raw_stage and stage_key is None:
        messages.append(
            ValidationMessage(
                MessageLevel.ERROR,
                f"Stage '{raw_stage}' referenced by {name} is not configured in project settings",
            )
        )

    if parsed.discipline:
        parsed.discipline = parsed.discipline.upper()
        if (
            stage_config
            and config.checks.discipline_codes.enabled
            and stage_config.discipline_codes
            and parsed.discipline not in {code.upper() for code in stage_config.discipline_codes}
        ):
            stage_label = getattr(stage_config, "name", stage_key or raw_stage or "configured stage")
            messages.append(
                ValidationMessage(
                    MessageLevel.ERROR,
                    f"Discipline '{parsed.discipline}' is not valid for {stage_label}",
                )
            )

    sheet_range = data.get("sheet_range")
    if sheet_range:
        parsed.sheet_range_raw = sheet_range
        number_config = config.checks.sheet_numbering
        components = sheet_range.split("-")
        has_error = False
        for component in components:
            if not component.isdigit():
                messages.append(
                    ValidationMessage(
                        MessageLevel.ERROR,
                        f"Sheet number '{component}' in {name} is not numeric",
                    )
                )
                has_error = True
                continue
            if number_config.enabled and number_config.width and len(component) != number_config.width:
                messages.append(
                    ValidationMessage(
                        MessageLevel.ERROR,
                        f"Sheet number '{component}' in {name} must be {number_config.width} digits",
                    )
                )
                has_error = True
        if not has_error:
            start, end = normalize_sheet_range(sheet_range)
            parsed.sheet_start = start
            parsed.sheet_end = end
            if end is not None and start > end:
                messages.append(
                    ValidationMessage(
                        MessageLevel.ERROR,
                        f"Sheet range {sheet_range} in {name} is invalid (start greater than end)",
                    )
                )

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


def validate_discipline_codes(
    parsed_files: Sequence[ParsedFilename],
    stage_key: str,
    stage_config: StageArtifacts | None,
    config: Config,
) -> List[ValidationMessage]:
    """Ensure parsed files use the expected stage and discipline codes."""

    messages: List[ValidationMessage] = []
    if not stage_config or not config.checks.discipline_codes.enabled:
        return messages

    allowed = {code.upper() for code in stage_config.discipline_codes}
    for parsed in parsed_files:
        if parsed.stage_key and parsed.stage_key != stage_key:
            messages.append(
                ValidationMessage(
                    MessageLevel.ERROR,
                    f"File {parsed.source.name} references stage '{parsed.stage}' but validating stage is '{stage_key}'",
                )
            )
        if not allowed or not parsed.discipline:
            continue
        if parsed.discipline.upper() not in allowed:
            messages.append(
                ValidationMessage(
                    MessageLevel.ERROR,
                    f"Discipline '{parsed.discipline}' in {parsed.source.name} is not permitted for stage {stage_key}",
                )
            )
    return messages


def validate_indot_forms(
    files: Sequence[Path], stage_config: StageArtifacts | None, config: Config
) -> List[ValidationMessage]:
    """Validate presence of required INDOT forms by fuzzy filename matching."""

    messages: List[ValidationMessage] = []
    if not stage_config or not config.checks.forms.enabled or not stage_config.forms:
        return messages

    normalized_files = [_normalize_token(path.name) for path in files]
    for form in stage_config.forms:
        token = _normalize_token(form)
        if not token:
            continue
        if not any(token in name for name in normalized_files):
            messages.append(
                ValidationMessage(
                    MessageLevel.ERROR,
                    f"Expected form '{form}' was not found in submission",
                )
            )
    return messages


def validate_sheet_numbering(
    parsed_files: Sequence[ParsedFilename], config: Config
) -> List[ValidationMessage]:
    """Validate sheet numbering continuity and detect overlaps."""

    number_config = config.checks.sheet_numbering
    messages: List[ValidationMessage] = []
    if not number_config.enabled:
        return messages

    messages.extend(detect_duplicate_ranges(parsed_files))

    if not number_config.require_contiguous and number_config.starting_number is None:
        return messages

    by_discipline: Dict[str, List[ParsedFilename]] = {}
    for parsed in parsed_files:
        if parsed.sheet_start is None:
            continue
        key = parsed.discipline or "UNKNOWN"
        by_discipline.setdefault(key, []).append(parsed)

    for discipline, records in by_discipline.items():
        records.sort(key=lambda entry: entry.sheet_start or 0)
        if number_config.starting_number is not None and records:
            first = records[0].sheet_start
            if first is not None and first != number_config.starting_number:
                messages.append(
                    ValidationMessage(
                        MessageLevel.WARNING,
                        f"Discipline {discipline} begins at sheet {first:0{number_config.width}d} but expected {number_config.starting_number:0{number_config.width}d}",
                    )
                )
        if not number_config.require_contiguous:
            continue
        expected = records[0].sheet_start or 0
        for record in records:
            if record.sheet_start != expected:
                messages.append(
                    ValidationMessage(
                        MessageLevel.ERROR,
                        f"Discipline {discipline} numbering jumps to {record.sheet_start:0{number_config.width}d} in {record.source.name}; expected {expected:0{number_config.width}d}",
                    )
                )
                expected = record.sheet_start or expected
            end_value = record.sheet_end or record.sheet_start or expected
            expected = end_value + 1
    return messages


__all__ = [
    "compile_ignore_patterns",
    "is_ignored",
    "parse_filename",
    "find_required_artifacts",
    "validate_required",
    "detect_duplicate_ranges",
    "normalize_sheet_range",
    "resolve_stage_config",
    "validate_discipline_codes",
    "validate_indot_forms",
    "validate_sheet_numbering",
]
