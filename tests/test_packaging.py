from __future__ import annotations

import csv
import zipfile
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
    save_config,
)
from submittal_packager.packager import run_package
from .conftest import create_text_pdf


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def config_path(tmp_path: Path) -> Path:
    templates_dir = Path(__file__).resolve().parents[1] / "templates"
    config = Config(
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
    path = tmp_path / "config.yml"
    save_config(config, path)
    return path


def test_run_package_creates_outputs(project: Path, config_path: Path, tmp_path: Path) -> None:
    title = project / "2401490_Stage2_TITLE_TITLE_0001.pdf"
    plans = project / "2401490_Stage2_ROAD_PLANS_0001-0002.pdf"
    create_text_pdf(title, "TITLE")
    create_text_pdf(plans, "PLANS")

    out = tmp_path / "dist"
    result = run_package(project, config_path, "Stage2", out_dir=out)
    assert not result.has_errors

    manifest_path = out / "2401490_Stage2_manifest.csv"
    checksums_path = out / "2401490_Stage2_checksums.sha256"
    transmittal_path = out / "2401490_Stage2_transmittal.docx"
    assert manifest_path.exists()
    assert checksums_path.exists()
    assert transmittal_path.exists()

    with manifest_path.open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2

    with checksums_path.open() as handle:
        checksum_lines = [line.strip().split()[0] for line in handle if line.strip()]
    assert len(checksum_lines) == len(rows)

    # Re-run packaging to ensure deterministic checksums
    result_repeat = run_package(project, config_path, "Stage2", out_dir=out)
    assert not result_repeat.has_errors
    with checksums_path.open() as handle:
        checksum_lines_repeat = [line.strip().split()[0] for line in handle if line.strip()]
    assert checksum_lines == checksum_lines_repeat

    zip_candidates = list(out.glob("*_submittal.zip"))
    assert zip_candidates
    with zipfile.ZipFile(zip_candidates[0]) as archive:
        names = sorted(archive.namelist())
    assert names == sorted(row["relative_path"] for row in rows)
