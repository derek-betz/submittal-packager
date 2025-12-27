"""High level validation and packaging routines."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from zipfile import ZipFile, ZIP_DEFLATED

from loguru import logger
from rich.console import Console
from rich.table import Table

from .config import Config, ConfigError, PackagingConfig, StageArtifacts, load_config
from .models import ManifestEntry, MessageLevel, ParsedFilename, ValidationMessage, ValidationResult
from .pdf_utils import pdf_extract_text, pdf_page_count
from .reporting import generate_html_report, generate_transmittal_docx
from .validators import (
    compile_ignore_patterns,
    is_ignored,
    parse_filename,
    resolve_stage_config,
    validate_discipline_codes,
    validate_indot_forms,
    validate_required,
    validate_sheet_numbering,
)

console = Console()


class ValidationFailure(Exception):
    """Raised when validation fails."""

    def __init__(self, result: ValidationResult) -> None:
        super().__init__("Validation failed")
        self.result = result


def _gather_files(
    root: Path, ignore_file: Path | None, exclude: set[Path] | None = None
) -> List[Path]:
    spec = compile_ignore_patterns(root, ignore_file)
    files: List[Path] = []
    for path in sorted(root.rglob("*")):
        resolved = path.resolve()
        if exclude and any(resolved == ex or resolved.is_relative_to(ex) for ex in exclude):
            continue
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
    root: Path,
    files: Iterable[Path],
    config: Config,
    stage_config: StageArtifacts | None,
) -> Tuple[List[ManifestEntry], List[ValidationMessage], List[ParsedFilename]]:
    entries: List[ManifestEntry] = []
    messages: List[ValidationMessage] = []
    parsed_records: List[ParsedFilename] = []

    scan_config = config.checks.pdf_text_scan
    checksum_algo = config.packaging.checksum_algo
    required_keywords_global: set[str] = set()
    forbidden_keywords_global: set[str] = set()
    if scan_config.enabled:
        required_keywords_global.update(scan_config.keywords_required)
        forbidden_keywords_global.update(scan_config.keywords_forbidden)
        if stage_config:
            required_keywords_global.update(stage_config.keywords_required)
            forbidden_keywords_global.update(stage_config.keywords_forbidden)

    missing_keywords = {keyword for keyword in required_keywords_global}

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
        stats = file.stat()
        size_bytes = stats.st_size
        checksum = _checksum(file, checksum_algo)
        modified = (
            datetime.utcfromtimestamp(stats.st_mtime).replace(microsecond=0).isoformat() + "Z"
        )
        entry = ManifestEntry(
            relative_path=str(file.relative_to(root)),
            size_bytes=size_bytes,
            pages=pages,
            checksum=checksum,
            checksum_algorithm=checksum_algo,
            des=parsed.des,
            stage=parsed.stage,
            discipline=parsed.discipline,
            sheet_type=parsed.sheet_type,
            sheet_start=parsed.sheet_start,
            sheet_end=parsed.sheet_end,
            ext=parsed.ext,
            source_modified=modified,
        )
        entries.append(entry)

        if scan_config.enabled and parsed.ext == "pdf":
            text = pdf_extract_text(file, max_pages=scan_config.pages)
            text_lower = text.lower()
            for keyword in list(missing_keywords):
                if keyword.lower() in text_lower:
                    missing_keywords.discard(keyword)

            if forbidden_keywords_global:
                hits = [kw for kw in sorted(forbidden_keywords_global) if kw.lower() in text_lower]
                if hits:
                    messages.append(
                        ValidationMessage(
                            MessageLevel.ERROR,
                            f"Forbidden keywords present in {file.name}: {', '.join(hits)}",
                        )
                    )

    if scan_config.enabled and missing_keywords:
        level = MessageLevel.ERROR if scan_config.require_all_keywords else MessageLevel.WARNING
        messages.append(
            ValidationMessage(
                level,
                f"Missing required keywords across submission: {', '.join(sorted(missing_keywords))}",
            )
        )

    return entries, messages, parsed_records


def _summarize(entries: List[ManifestEntry]) -> Tuple[int, int]:
    files = len(entries)
    pages = sum(entry.pages for entry in entries)
    return files, pages


def _folder_for_generated(packaging: PackagingConfig) -> str:
    for folder in packaging.folders:
        if folder.include_generated:
            return folder.name
    return packaging.default_folder


def _match_package_folder(entry: ManifestEntry, packaging: PackagingConfig) -> str:
    file_name = Path(entry.relative_path).name.lower()
    relative = entry.relative_path.lower()
    ext = (entry.ext or Path(file_name).suffix.lstrip(".")).lower()
    for folder in packaging.folders:
        if folder.patterns and any(
            fnmatch(file_name, pattern.lower()) or fnmatch(relative, pattern.lower())
            for pattern in folder.patterns
        ):
            return folder.name
        if folder.extensions and ext in folder.extensions:
            return folder.name
    return packaging.default_folder


def _assign_package_paths(
    entries: List[ManifestEntry], packaging: PackagingConfig, root_folder: str
) -> None:
    for entry in entries:
        folder = _match_package_folder(entry, packaging)
        package_target = Path(root_folder)
        if folder:
            package_target = package_target / folder
        package_target = package_target / Path(entry.relative_path).name
        entry.package_path = package_target.as_posix()


def _folder_from_package_path(
    entry: ManifestEntry, default_folder: str
) -> str:
    if entry.package_path:
        parts = Path(entry.package_path).parts
        if len(parts) >= 2:
            return parts[1]
    return default_folder


def _build_package_overview(
    entries: List[ManifestEntry],
    packaging: PackagingConfig,
    root_folder: str,
    generated_artifacts: List[Dict[str, str]] | None = None,
) -> Dict[str, Any]:
    totals_files = len(entries)
    totals_pages = sum(entry.pages for entry in entries)

    folder_summary: Dict[str, Dict[str, int]] = defaultdict(lambda: {"files": 0, "pages": 0})
    discipline_summary: Dict[str, Dict[str, int]] = defaultdict(lambda: {"files": 0, "pages": 0})
    extension_summary: Dict[str, Dict[str, int]] = defaultdict(lambda: {"files": 0, "pages": 0})

    default_folder = packaging.default_folder
    for entry in entries:
        folder_name = _folder_from_package_path(entry, default_folder)
        folder_summary[folder_name]["files"] += 1
        folder_summary[folder_name]["pages"] += entry.pages

        discipline = entry.discipline or "UNASSIGNED"
        discipline_summary[discipline]["files"] += 1
        discipline_summary[discipline]["pages"] += entry.pages

        ext = entry.ext or Path(entry.relative_path).suffix.lstrip(".").lower() or "unknown"
        extension_summary[ext]["files"] += 1
        extension_summary[ext]["pages"] += entry.pages

    folder_details: List[Dict[str, Any]] = []
    configured_names = set()
    for folder in packaging.folders:
        configured_names.add(folder.name)
        folder_details.append(
            {
                "name": folder.name,
                "description": folder.description,
                "include_generated": folder.include_generated,
                "summary": dict(folder_summary.get(folder.name, {"files": 0, "pages": 0})),
            }
        )

    for folder_name, stats in folder_summary.items():
        if folder_name not in configured_names:
            folder_details.append(
                {
                    "name": folder_name,
                    "description": None,
                    "include_generated": False,
                    "summary": dict(stats),
                }
            )

    overview: Dict[str, Any] = {
        "root": root_folder,
        "totals": {"files": totals_files, "pages": totals_pages},
        "folders": folder_details,
        "folder_summary": {key: dict(value) for key, value in folder_summary.items()},
        "discipline_summary": {key: dict(value) for key, value in discipline_summary.items()},
        "extension_summary": {key: dict(value) for key, value in extension_summary.items()},
    }

    if generated_artifacts:
        overview["generated"] = generated_artifacts

    return overview


def _build_zip_entries(
    entries: List[ManifestEntry],
    root: Path,
    generated_files: List[Tuple[Path, str, str]],
) -> Tuple[List[Tuple[Path, str]], List[Dict[str, str]]]:
    zip_entries: List[Tuple[Path, str]] = []
    for entry in entries:
        package_path = entry.package_path or entry.relative_path
        zip_entries.append((root / entry.relative_path, package_path))

    generated_artifacts: List[Dict[str, str]] = []
    for path, label, arcname in generated_files:
        if not path.exists():
            continue
        zip_entries.append((path, arcname))
        generated_artifacts.append({"label": label, "package_path": arcname})

    return zip_entries, generated_artifacts


def validate_directory(
    root: Path,
    config: Config,
    stage: str,
    *,
    strict: bool = False,
    ignore_file: Path | None = None,
    map_file: Path | None = None,
    exclude_paths: Iterable[Path] | None = None,
) -> ValidationResult:
    """Validate directory contents and return result."""

    logger.debug("Starting validation for stage {}", stage)
    exclude = {path.resolve() for path in exclude_paths} if exclude_paths else None
    files = _gather_files(root, ignore_file, exclude)
    stage_key, stage_config = resolve_stage_config(stage, config)
    manifest_entries, messages, parsed_records = _build_manifest(root, files, config, stage_config)

    result = ValidationResult(manifest=manifest_entries)
    result.extend(messages)

    if stage_key is None or stage_config is None:
        result.errors.append(ValidationMessage(MessageLevel.ERROR, f"Stage '{stage}' not defined in config"))
        return result

    required_messages = validate_required(files, stage_config.required)
    result.extend(required_messages)

    result.extend(validate_discipline_codes(parsed_records, stage_key, stage_config, config))
    result.extend(validate_indot_forms(files, stage_config, config))
    result.extend(validate_sheet_numbering(parsed_records, config))

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


def write_manifest(
    entries: List[ManifestEntry], path: Path, overview: Dict[str, Any]
) -> None:
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
                "checksum",
                "checksum_algorithm",
                "package_path",
                "source_modified_utc",
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
                    entry.checksum_algorithm,
                    entry.package_path or "",
                    entry.source_modified or "",
                ]
            )

        writer.writerow([])
        writer.writerow(["package_root", overview.get("root", "")])
        writer.writerow([])
        writer.writerow(["Folder", "Files", "Pages"])
        for folder_name, stats in sorted(overview.get("folder_summary", {}).items()):
            writer.writerow([folder_name, stats.get("files", 0), stats.get("pages", 0)])
        writer.writerow(["TOTAL", overview.get("totals", {}).get("files", 0), overview.get("totals", {}).get("pages", 0)])

        writer.writerow([])
        writer.writerow(["Discipline", "Files", "Pages"])
        for discipline, stats in sorted(overview.get("discipline_summary", {}).items()):
            writer.writerow([discipline, stats.get("files", 0), stats.get("pages", 0)])

        writer.writerow([])
        writer.writerow(["Extension", "Files", "Pages"])
        for ext, stats in sorted(overview.get("extension_summary", {}).items()):
            writer.writerow([ext, stats.get("files", 0), stats.get("pages", 0)])


def write_checksums(
    entries: List[ManifestEntry], path: Path, algorithm: str
) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["algorithm", "checksum", "relative_path", "package_path"])
        for entry in entries:
            writer.writerow(
                [
                    algorithm,
                    entry.checksum,
                    entry.relative_path,
                    entry.package_path or "",
                ]
            )


def create_zip(zip_entries: Iterable[Tuple[Path, str]], zip_path: Path) -> None:
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
        for source, arcname in zip_entries:
            archive.write(source, arcname=arcname)


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

    result = validate_directory(
        root,
        config,
        stage,
        strict=strict,
        ignore_file=ignore_file,
        map_file=map_file,
        exclude_paths=[config_path, out_dir],
    )
    if result.has_errors:
        raise ValidationFailure(result)

    out_dir.mkdir(parents=True, exist_ok=True)
    package_root = config.packaging.root_folder_format.format(
        des=config.project.designation, stage=stage
    )
    _assign_package_paths(result.manifest, config.packaging, package_root)
    manifest_overview = _build_package_overview(result.manifest, config.packaging, package_root)

    manifest_path = out_dir / f"{config.project.designation}_{stage}_manifest.csv"
    write_manifest(result.manifest, manifest_path, manifest_overview)

    generated_folder = _folder_for_generated(config.packaging)

    def _admin_destination(path: Path) -> str:
        target = Path(package_root)
        if generated_folder:
            target = target / generated_folder
        return (target / path.name).as_posix()

    generated_files: List[Tuple[Path, str, str]] = []
    generated_preview: List[Dict[str, str]] = []

    def _register_existing(path: Path, label: str) -> None:
        destination = _admin_destination(path)
        generated_files.append((path, label, destination))
        generated_preview.append({"label": label, "package_path": destination})

    _register_existing(manifest_path, "Manifest CSV")

    checksum_path: Path | None = None
    if config.packaging.include_checksums:
        checksum_path = out_dir / (
            f"{config.project.designation}_{stage}_checksums.{config.packaging.checksum_algo}"
        )
        write_checksums(result.manifest, checksum_path, config.packaging.checksum_algo)
        _register_existing(
            checksum_path, f"Checksums ({config.packaging.checksum_algo.upper()})"
        )

    log_copy: Path | None = None
    if log_path:
        log_copy = out_dir / log_path.name
        shutil.copy(log_path, log_copy)
        _register_existing(log_copy, "Validation Log")

    transmittal_path = out_dir / f"{config.project.designation}_{stage}_transmittal.docx"
    transmittal_dest = _admin_destination(transmittal_path)
    generated_preview.append({"label": "Transmittal Letter", "package_path": transmittal_dest})

    report_path = out_dir / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
    report_dest = _admin_destination(report_path)
    generated_preview.append({"label": "Validation Report", "package_path": report_dest})

    package_overview = _build_package_overview(
        result.manifest, config.packaging, package_root, generated_preview
    )

    generated_at = datetime.utcnow().isoformat()
    generate_transmittal_docx(
        config=config,
        manifest=result.manifest,
        stage=stage,
        output_path=transmittal_path,
        generated_at=generated_at,
        messages=result,
        template_path=config_path.parent / config.templates.transmittal_docx,
        package_overview=package_overview,
    )
    generated_files.append((transmittal_path, "Transmittal Letter", transmittal_dest))

    generate_html_report(
        config=config,
        manifest=result.manifest,
        stage=stage,
        output_path=report_path,
        generated_at=generated_at,
        messages=result,
        template_path=config_path.parent / config.templates.report_html,
        package_overview=package_overview,
    )
    generated_files.append((report_path, "Validation Report", report_dest))

    zip_entries, generated_artifacts = _build_zip_entries(
        result.manifest, root, generated_files
    )

    if generated_artifacts:
        package_overview = _build_package_overview(
            result.manifest, config.packaging, package_root, generated_artifacts
        )
        generate_transmittal_docx(
            config=config,
            manifest=result.manifest,
            stage=stage,
            output_path=transmittal_path,
            generated_at=generated_at,
            messages=result,
            template_path=config_path.parent / config.templates.transmittal_docx,
            package_overview=package_overview,
        )
        generate_html_report(
            config=config,
            manifest=result.manifest,
            stage=stage,
            output_path=report_path,
            generated_at=generated_at,
            messages=result,
            template_path=config_path.parent / config.templates.report_html,
            package_overview=package_overview,
        )

    zip_name = config.packaging.zip_name_format.format(
        des=config.project.designation, stage=stage
    )
    zip_path = out_dir / zip_name
    create_zip(zip_entries, zip_path)

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
    return validate_directory(
        root,
        config,
        stage,
        strict=strict,
        ignore_file=ignore_file,
        map_file=map_file,
        exclude_paths=[config_path],
    )


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
            relative = row.get("relative_path")
            if not relative or not row.get("checksum"):
                break
            manifest.append(
                ManifestEntry(
                    relative_path=relative,
                    size_bytes=int(row["size_bytes"]),
                    pages=int(row["pages"]),
                    des=row.get("des") or None,
                    stage=row.get("stage") or None,
                    discipline=row.get("discipline") or None,
                    sheet_type=row.get("sheet_type") or None,
                    sheet_start=int(row["sheet_start"]) if row.get("sheet_start") else None,
                    sheet_end=int(row["sheet_end"]) if row.get("sheet_end") else None,
                    ext=row.get("ext") or None,
                    checksum=row.get("checksum") or row.get("sha256") or "",
                    checksum_algorithm=row.get("checksum_algorithm") or config.packaging.checksum_algo,
                    package_path=row.get("package_path") or None,
                    source_modified=row.get("source_modified_utc") or None,
                )
            )
    generated_at = datetime.utcnow().isoformat()
    report_path = out_dir / f"report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"
    package_root = config.packaging.root_folder_format.format(
        des=config.project.designation, stage=stage
    )
    package_overview = _build_package_overview(manifest, config.packaging, package_root)
    generate_html_report(
        config=config,
        manifest=manifest,
        stage=stage,
        output_path=report_path,
        generated_at=generated_at,
        messages=ValidationResult(manifest=manifest),
        template_path=config_path.parent / config.templates.report_html,
        package_overview=package_overview,
    )
    return report_path


__all__ = [
    "run_package",
    "run_validate",
    "run_report",
    "ValidationFailure",
]
