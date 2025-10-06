"""Configuration loading and validation for Submittal Packager."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, validator


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


class StageArtifacts(BaseModel):
    """Artifacts required for a particular stage."""

    required: List[RequirementConfig] = Field(default_factory=list)
    optional: List[RequirementConfig] = Field(default_factory=list)


class PdfTextScanConfig(BaseModel):
    enabled: bool = False
    keywords_required: List[str] = Field(default_factory=list)
    keywords_forbidden: List[str] = Field(default_factory=list)
    pages: int = 3


class DateCheckConfig(BaseModel):
    require_revision_date: bool = False
    date_regex: Optional[str] = None


class SheetLimitConfig(BaseModel):
    min_total_sheets: Optional[int] = None
    max_total_sheets: Optional[int] = None


class ChecksConfig(BaseModel):
    pdf_text_scan: PdfTextScanConfig = Field(default_factory=PdfTextScanConfig)
    dates: DateCheckConfig = Field(default_factory=DateCheckConfig)
    sheet_limits: SheetLimitConfig = Field(default_factory=SheetLimitConfig)


class PackagingConfig(BaseModel):
    include_checksums: bool = True
    checksum_algo: str = "sha256"
    zip_name_format: str = "{des}_{stage}_submittal.zip"


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
