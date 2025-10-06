from __future__ import annotations

from pathlib import Path

import pytest
from submittal_packager.config import (
    ChecksConfig,
    Config,
    ConventionsConfig,
    PackagingConfig,
    ProjectConfig,
    RequirementConfig,
    StageArtifacts,
    TemplatesConfig,
)
from submittal_packager.packager import validate_directory
from .conftest import create_text_pdf


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def config(project_root: Path) -> Config:
    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    return Config(
        project=ProjectConfig(
            designation="2401490",
            route="SR 14",
            project_name="SR 14 Improvements",
            consultant="Consultant",
            contact="Jane Doe <jane@example.com>",
            stage="Stage2",
        ),
        conventions=ConventionsConfig(
            filename_pattern="{des}_{stage}_{discipline}_{sheet_type}_{sheet_range}.{ext}",
            regex="^(?P<des>\\d{7})_(?P<stage>Stage[123]|Final)_(?P<discipline>[A-Z]+)_(?P<sheet_type>[A-Za-z0-9]+)_(?P<sheet_range>\\d+(?:-\\d+)?)\\.(?P<ext>pdf|docx)$",
        ),
        stages={
            "Stage2": StageArtifacts(
                required=[
                    RequirementConfig(key="title_sheet", pattern="*TITLE*.pdf"),
                    RequirementConfig(key="plans", pattern="*PLANS*.pdf"),
                ]
            )
        },
        checks=ChecksConfig(),
        packaging=PackagingConfig(),
        templates=TemplatesConfig(
            transmittal_docx=str(templates_dir / "transmittal.docx.j2"),
            report_html=str(templates_dir / "report.html.j2"),
        ),
    )


def test_validate_directory_counts_pages(project_root: Path, config: Config) -> None:
    title = project_root / "2401490_Stage2_TITLE_TITLE_0001.pdf"
    plans = project_root / "2401490_Stage2_ROAD_PLANS_0001-0002.pdf"
    create_text_pdf(title, "TITLE")
    create_text_pdf(plans, "PLANS")

    result = validate_directory(project_root, config, "Stage2")
    assert not result.has_errors
    assert sum(entry.pages for entry in result.manifest) == 2


def test_pdf_keyword_scan(project_root: Path, config: Config) -> None:
    config.checks.pdf_text_scan.enabled = True
    config.checks.pdf_text_scan.keywords_required = ["REQUIRED"]
    config.checks.pdf_text_scan.keywords_forbidden = ["FORBIDDEN"]

    title = project_root / "2401490_Stage2_TITLE_TITLE_0001.pdf"
    plans = project_root / "2401490_Stage2_ROAD_PLANS_0001.pdf"
    create_text_pdf(title, "REQUIRED")
    create_text_pdf(plans, "OK")

    result = validate_directory(project_root, config, "Stage2")
    assert not result.has_errors
    assert not result.warnings

    forbidden = project_root / "2401490_Stage2_DRAIN_PLANS_0002.pdf"
    create_text_pdf(forbidden, "FORBIDDEN")
    result2 = validate_directory(project_root, config, "Stage2")
    assert any("Forbidden" in msg.text for msg in result2.errors)
