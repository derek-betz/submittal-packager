"""Configuration loading and validation for Submittal Packager."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, root_validator, validator

from .idm_requirements import get_stage_defaults


class ProjectConfig(BaseModel):
    """Project level metadata."""

    designation: str
    route: str
    project_name: str
    consultant: str
    contact: str
    stage: str


class ExceptionPattern(BaseModel):
    """Secondary regex pattern allowing filename exceptions."""

    name: str
    regex: str


class ConventionsConfig(BaseModel):
    """Filename convention settings."""

    filename_pattern: str
    regex: str
    stage_case_insensitive: bool = True
    allow_spaces: bool = False
    allowed_extensions: List[str] = Field(default_factory=lambda: ["pdf", "docx"])
    exceptions: List[ExceptionPattern] | None = None

    @validator("allowed_extensions", each_item=True)
    def _normalize_extensions(cls, value: str) -> str:
        return value.lower()


class RequirementConfig(BaseModel):
    """Represents a required or optional artifact."""

    key: str
    pattern: str
    description: Optional[str] = None


class StageArtifacts(BaseModel):
    """Artifacts required for a particular stage."""

    preset: Optional[str] = Field(
        default=None, description="IDM stage preset to use for initial defaults."
    )
    inherit_defaults: bool = Field(
        default=True,
        description="Merge preset defaults into the stage configuration when true.",
    )
    required: List[RequirementConfig] = Field(default_factory=list)
    optional: List[RequirementConfig] = Field(default_factory=list)
    discipline_codes: List[str] = Field(default_factory=list)
    forms: List[str] = Field(default_factory=list)
    keywords_required: List[str] = Field(default_factory=list)
    keywords_optional: List[str] = Field(default_factory=list)
    keywords_forbidden: List[str] = Field(default_factory=list)

    @root_validator(pre=True)
    def _merge_preset_defaults(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        preset = values.get("preset")
        inherit = values.get("inherit_defaults", True)
        if not preset or not inherit:
            return values

        defaults = get_stage_defaults(preset)
        if defaults is None:
            raise ValueError(f"Unknown IDM stage preset '{preset}'")

        merged: Dict[str, Any] = dict(values)

        def _coerce_requirements(source: Any) -> List[Dict[str, Any]]:
            if not source:
                return []
            items: List[Dict[str, Any]] = []
            for entry in source:
                if isinstance(entry, RequirementConfig):
                    items.append(entry.dict())
                elif isinstance(entry, dict):
                    items.append(dict(entry))
                else:
                    raise TypeError(
                        "Stage artifact requirements must be dictionaries or RequirementConfig instances"
                    )
            return items

        def _merge_requirements(
            default_items: List[Dict[str, Any]],
            provided_items: List[Dict[str, Any]],
        ) -> List[Dict[str, Any]]:
            combined: Dict[str, Dict[str, Any]] = {}
            for item in default_items + provided_items:
                key = item.get("key")
                if not key:
                    raise ValueError("Each requirement must define a key")
                combined[key] = item
            return list(combined.values())

        def _merge_unique(default_items: List[str], provided: Any) -> List[str]:
            provided_list: List[str]
            if not provided:
                provided_list = []
            elif isinstance(provided, list):
                provided_list = [str(item) for item in provided]
            else:
                provided_list = [str(provided)]

            seen: set[str] = set()
            ordered: List[str] = []
            for item in list(default_items) + provided_list:
                if item not in seen:
                    seen.add(item)
                    ordered.append(item)
            return ordered

        for key in ("required", "optional"):
            defaults_list = [dict(item) for item in defaults.get(key, [])]
            provided_list = _coerce_requirements(values.get(key))
            merged[key] = _merge_requirements(defaults_list, provided_list)

        for key in (
            "discipline_codes",
            "forms",
            "keywords_required",
            "keywords_optional",
            "keywords_forbidden",
        ):
            merged[key] = _merge_unique(defaults.get(key, []), values.get(key))

        return merged


class PdfTextScanConfig(BaseModel):
    enabled: bool = False
    keywords_required: List[str] = Field(default_factory=list)
    keywords_forbidden: List[str] = Field(default_factory=list)
    pages: int = 3
    require_all_keywords: bool = True


class DateCheckConfig(BaseModel):
    require_revision_date: bool = False
    date_regex: Optional[str] = None


class DisciplineValidationConfig(BaseModel):
    enabled: bool = True


class FormsValidationConfig(BaseModel):
    enabled: bool = True


class SheetNumberingValidationConfig(BaseModel):
    enabled: bool = True
    width: int = 4
    require_contiguous: bool = False
    starting_number: Optional[int] = None


class SheetLimitConfig(BaseModel):
    min_total_sheets: Optional[int] = None
    max_total_sheets: Optional[int] = None


class ChecksConfig(BaseModel):
    pdf_text_scan: PdfTextScanConfig = Field(default_factory=PdfTextScanConfig)
    dates: DateCheckConfig = Field(default_factory=DateCheckConfig)
    sheet_limits: SheetLimitConfig = Field(default_factory=SheetLimitConfig)
    discipline_codes: DisciplineValidationConfig = Field(default_factory=DisciplineValidationConfig)
    forms: FormsValidationConfig = Field(default_factory=FormsValidationConfig)
    sheet_numbering: SheetNumberingValidationConfig = Field(default_factory=SheetNumberingValidationConfig)


class PackageFolderConfig(BaseModel):
    """Defines how files are grouped within the packaged ZIP."""

    name: str
    description: Optional[str] = None
    patterns: List[str] = Field(default_factory=list)
    extensions: List[str] = Field(default_factory=list)
    include_generated: bool = False

    @validator("extensions", each_item=True)
    def _normalize_extension(cls, value: str) -> str:
        value = value.lower().lstrip(".")
        if not value:
            raise ValueError("File extension filters cannot be empty")
        return value


def _default_packaging_folders() -> List["PackageFolderConfig"]:
    return [
        PackageFolderConfig(
            name="0_Admin",
            description="Administrative outputs including the manifest, transmittal, and validation report.",
            patterns=["*manifest*", "*checksum*", "*transmittal*", "*report*"],
            include_generated=True,
        ),
        PackageFolderConfig(
            name="1_Cover_Letter",
            description="Signed cover letter and formal correspondence transmitted to INDOT reviewers.",
            patterns=["*cover*letter*", "*transmittal*.pdf"],
        ),
        PackageFolderConfig(
            name="2_Plan_Set",
            description="Plan set PDFs organized per the IDM checklist.",
            extensions=["pdf"],
        ),
        PackageFolderConfig(
            name="3_Supporting_Docs",
            description="Supporting design documentation such as calculations or memos.",
            extensions=["doc", "docx", "xls", "xlsx"],
        ),
        PackageFolderConfig(
            name="4_PCFS",
            description="Project Certification Forms (PCFs) and related approvals.",
            patterns=["*pcf*"],
        ),
    ]


class PackagingConfig(BaseModel):
    include_checksums: bool = True
    checksum_algo: str = "sha256"
    zip_name_format: str = "{des}_{stage}_IDM.zip"
    root_folder_format: str = "{des}_{stage}_IDM"
    default_folder: str = "2_Plan_Set"
    folders: List[PackageFolderConfig] = Field(default_factory=_default_packaging_folders)


class TemplatesConfig(BaseModel):
    transmittal_docx: str
    report_html: str


class Config(BaseModel):
    """Top-level configuration."""

    project: ProjectConfig
    conventions: ConventionsConfig
    stages: Dict[str, StageArtifacts]
    checks: ChecksConfig = Field(default_factory=ChecksConfig)
    packaging: PackagingConfig = Field(default_factory=PackagingConfig)
    templates: TemplatesConfig

    @validator("stages")
    def _ensure_stage_entries(cls, value: Dict[str, StageArtifacts]) -> Dict[str, StageArtifacts]:
        if not value:
            raise ValueError("At least one stage must be configured")
        return value


class ConfigError(Exception):
    """Raised when a configuration file is invalid."""


def load_config(path: Path) -> Config:
    """Load configuration from YAML file."""

    try:
        data = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Failed to parse YAML: {exc}") from exc

    try:
        return Config.parse_obj(data)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration: {exc}") from exc


def save_config(config: Config, path: Path) -> None:
    """Persist configuration to disk as YAML."""

    rendered = config.dict()
    path.write_text(yaml.safe_dump(rendered, sort_keys=False))


__all__ = [
    "Config",
    "ConfigError",
    "load_config",
    "save_config",
    "ProjectConfig",
]
