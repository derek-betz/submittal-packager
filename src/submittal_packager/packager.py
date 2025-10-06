"""High level validation and packaging routines."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Tuple
from zipfile import ZipFile, ZIP_DEFLATED

from loguru import logger
from rich.console import Console
from rich.table import Table

from .config import Config, ConfigError, load_config
from .models import ManifestEntry, MessageLevel, ParsedFilename, ValidationMessage, ValidationResult
from .pdf_utils import contains_forbidden, contains_keywords, pdf_extract_text, pdf_page_count
from .reporting import generate_html_report, generate_transmittal_docx
from .validators import (
    compile_ignore_patterns,
    detect_duplicate_ranges,
    is_ignored,
    parse_filename,
    validate_required,
)

console = Console()


class ValidationFailure(Exception):
    """Raised when validation fails."""

    def __init__(self, result: ValidationResult) -> None:
        super().__init__("Validation failed")
        self.result = result


def _gather_files(root: Path, ignore_file: Path | None) -> List[Path]:
    spec = compile_ignore_patterns(root, ignore_file)
    files: List[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not is_ignored(path, spec, root):
            files.append(path)
    return files


def _checksum(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _build_manifest(
    root: Path, files: Iterable[Path], config: Config, stage: str
) -> Tuple[List[ManifestEntry], List[ValidationMessage]]:
    entries: List[ManifestEntry] = []
    messages: List[ValidationMessage] = []
    parsed_records: List[ParsedFilename] = []

    for file in files:
        parsed, parse_messages = parse_filename(file, config)
        messages.extend(parse_messages)
        if parsed is None:
            continue
        parsed_records.append(parsed)

        pages = 0
        if parsed.ext == "pdf":
            try:
                pages = pdf_page_count(file)
            except Exception as exc:  # pragma: no cover - PyPDF2 failures rare
                messages.append(ValidationMessage(MessageLevel.WARNING, f"Failed to read pages for {file.name}: {exc}"))
        size_bytes = file.stat().st_size
        checksum = _checksum(file, config.packaging.checksum_algo)
        entry = ManifestEntry(
            relative_path=str(file.relative_to(root)),
            size_bytes=size_bytes,
            pages=pages,
            checksum=checksum,
            des=parsed.des,
            stage=parsed.stage,
            discipline=parsed.discipline,
            sheet_type=parsed.sheet_type,
            sheet_start=parsed.sheet_start,
            sheet_end=parsed.sheet_end,
            ext=parsed.ext,
        )
        entries.append(entry)

        if config.checks.pdf_text_scan.enabled and parsed.ext == "pdf":
            text = pdf_extract_text(file, max_pages=config.checks.pdf_text_scan.pages)
            if config.checks.pdf_text_scan.keywords_forbidden and contains_forbidden(
                text, config.checks.pdf_text_scan.keywords_forbidden
            ):
                messages.append(
                    ValidationMessage(
                        MessageLevel.ERROR,
                        f"Forbidden keywords present in {file.name}",
                    )
                )
    # Note: we do not warn when required keywords are missing to keep validation noise minimal.

    messages.extend(detect_duplicate_ranges(parsed_records))
    return entries, messages


def _summarize(entries: List[ManifestEntry]) -> Tuple[int, int]:
    files = len(entries)
    pages = sum(entry.pages for entry in entries)
    return files, pages


def validate_directory(
    root: Path,
    config: Config,
    stage: str,
    *,
    strict: bool = False,
    ignore_file: Path | None = None,
    map_file: Path | None = None,
) -> ValidationResult:
    """Validate directory contents and return result."""

    logger.debug("Starting validation for stage {}", stage)
    files = _gather_files(root, ignore_file)
    manifest_entries, messages = _build_manifest(root, files, config, stage)

    result = ValidationResult(manifest=manifest_entries)
    result.extend(messages)

    stage_config = config.stages.get(stage)
    if stage_config is None:
        result.errors.append(ValidationMessage(MessageLevel.ERROR, f"Stage '{stage}' not defined in config"))
        return result

    required_messages = validate_required(files, stage_config.required)
    result.extend(required_messages)

    files_count, total_pages = _summarize(manifest_entries)
    limits = config.checks.sheet_limits
    if limits.min_total_sheets and total_pages < limits.min_total_sheets:
        result.warnings.append(
            ValidationMessage(
                MessageLevel.WARNING,
                f"Total sheets {total_pages} below minimum {limits.min_total_sheets}",
            )
        )
    if limits.max_total_sheets and total_pages > limits.max_total_sheets:
        result.errors.append(
            ValidationMessage(
                MessageLevel.ERROR,
                f"Total sheets {total_pages} exceeds maximum {limits.max_total_sheets}",
            )
        )

    if map_file:
        grouped: dict[str, dict[str, int]] = {}
        for entry in manifest_entries:
            discipline = entry.discipline or "UNKNOWN"
            sheet_type = entry.sheet_type or "UNKNOWN"
            grouped.setdefault(discipline, {}).setdefault(sheet_type, 0)
            grouped[discipline][sheet_type] += entry.pages
        map_file.write_text(json.dumps(grouped, indent=2))

    if strict and result.has_warnings:
        for warn in result.warnings:
            result.errors.append(ValidationMessage(MessageLevel.ERROR, warn.text))
        result.warnings.clear()

    return result


def write_manifest(entries: List[ManifestEntry], path: Path) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "relative_path",
                "size_bytes",
                "pages",
                "des",
                "stage",
                "discipline",
                "sheet_type",
                "sheet_start",
                "sheet_end",
                "ext",
                "sha256",
            ]
        )
        for entry in entries:
            writer.writerow(
                [
                    entry.relative_path,
                    entry.size_bytes,
                    entry.pages,
                    entry.des or "",
                    entry.stage or "",
                    entry.discipline or "",
                    entry.sheet_type or "",
                    entry.sheet_start or "",
                    entry.sheet_end or "",
                    entry.ext or "",
                    entry.checksum,
                ]
            )


def write_checksums(entries: List[ManifestEntry], path: Path) -> None:
    with path.open("w") as handle:
        for entry in entries:
            handle.write(f"{entry.checksum} {entry.relative_path}\n")


def create_zip(entries: List[ManifestEntry], root: Path, zip_path: Path) -> None:
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for entry in entries:
            source = root / entry.relative_path
            archive.write(source, arcname=entry.relative_path)


def run_package(
    root: Path,
    config_path: Path,
    stage: str,
    *,
    out_dir: Path,
    strict: bool = False,
    ignore_file: Path | None = None,
    no_scan: bool = False,
    log_path: Path | None = None,
    map_file: Path | None = None,
) -> ValidationResult:
    config = load_config(config_path)
    if no_scan:
        config.checks.pdf_text_scan.enabled = False

    result = validate_directory(root, config, stage, strict=strict, ignore_file=ignore_file, map_file=map_file)
    if result.has_errors:
        raise ValidationFailure(result)

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / f"{config.project.designation}_{stage}_manifest.csv"
    write_manifest(result.manifest, manifest_path)

    if config.packaging.include_checksums:
        checksum_path = out_dir / f"{config.project.designation}_{stage}_checksums.{config.packaging.checksum_algo}"
        write_checksums(result.manifest, checksum_path)

    zip_name = config.packaging.zip_name_format.format(des=config.project.designation, stage=stage)
    zip_path = out_dir / zip_name
    create_zip(result.manifest, root, zip_path)

    generated_at = datetime.utcnow().isoformat()
    transmittal_path = out_dir / f"{config.project.designation}_{stage}_transmittal.docx"
    generate_transmittal_docx(
        config=config,
        manifest=result.manifest,
        stage=stage,
        output_path=transmittal_path,
        generated_at=generated_at,
        messages=result,
        template_path=config_path.parent / config.templates.transmittal_docx,
    )

    report_path = out_dir / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
    generate_html_report(
        config=config,
        manifest=result.manifest,
        stage=stage,
        output_path=report_path,
        generated_at=generated_at,
        messages=result,
        template_path=config_path.parent / config.templates.report_html,
    )

    if log_path:
        shutil.copy(log_path, out_dir / log_path.name)

    table = Table(title="Packaging Summary")
    table.add_column("Files", justify="right")
    table.add_column("Pages", justify="right")
    files_count, total_pages = _summarize(result.manifest)
    table.add_row(str(files_count), str(total_pages))
    console.print(table)

    return result


def run_validate(
    root: Path,
    config_path: Path,
    stage: str,
    *,
    strict: bool = False,
    ignore_file: Path | None = None,
    map_file: Path | None = None,
) -> ValidationResult:
    config = load_config(config_path)
    return validate_directory(root, config, stage, strict=strict, ignore_file=ignore_file, map_file=map_file)


def run_report(
    root: Path,
    config_path: Path,
    stage: str,
    *,
    out_dir: Path,
) -> Path:
    config = load_config(config_path)
    manifest_path = out_dir / f"{config.project.designation}_{stage}_manifest.csv"
    if not manifest_path.exists():
        raise FileNotFoundError("Manifest not found; run package first")
    manifest: List[ManifestEntry] = []
    with manifest_path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            manifest.append(
                ManifestEntry(
                    relative_path=row["relative_path"],
                    size_bytes=int(row["size_bytes"]),
                    pages=int(row["pages"]),
                    des=row.get("des") or None,
                    stage=row.get("stage") or None,
                    discipline=row.get("discipline") or None,
                    sheet_type=row.get("sheet_type") or None,
                    sheet_start=int(row["sheet_start"]) if row.get("sheet_start") else None,
                    sheet_end=int(row["sheet_end"]) if row.get("sheet_end") else None,
                    ext=row.get("ext") or None,
                    checksum=row["sha256"],
                )
            )
    generated_at = datetime.utcnow().isoformat()
    report_path = out_dir / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
    generate_html_report(
        config=config,
        manifest=manifest,
        stage=stage,
        output_path=report_path,
        generated_at=generated_at,
        messages=ValidationResult(manifest=manifest),
        template_path=config_path.parent / config.templates.report_html,
    )
    return report_path


__all__ = [
    "run_package",
    "run_validate",
    "run_report",
    "ValidationFailure",
]
