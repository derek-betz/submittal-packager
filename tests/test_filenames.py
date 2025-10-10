import pytest

from pathlib import Path

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
from submittal_packager.validators import normalize_sheet_range, parse_filename


@pytest.fixture()
def sample_config() -> Config:
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
                ],
                discipline_codes=["ROAD", "TITLE"],
            )
        },
        checks=ChecksConfig(),
        packaging=PackagingConfig(),
        templates=TemplatesConfig(
            transmittal_docx="templates/transmittal.docx.j2",
            report_html="templates/report.html.j2",
        ),
    )


def test_parse_filename_success(sample_config: Config) -> None:
    path = Path("2401490_Stage2_ROAD_PLANS_0001-0003.pdf")
    parsed, messages = parse_filename(path, sample_config)
    assert parsed is not None
    assert parsed.des == "2401490"
    assert parsed.stage == "stage2"
    assert parsed.stage_key == "Stage2"
    assert parsed.sheet_start == 1
    assert parsed.sheet_end == 3
    assert not messages


def test_parse_filename_reject_spaces(sample_config: Config) -> None:
    path = Path("bad file.pdf")
    parsed, messages = parse_filename(path, sample_config)
    assert parsed is None
    assert any("Spaces" in msg.text for msg in messages)


def test_normalize_sheet_range() -> None:
    assert normalize_sheet_range("0001-0010") == (1, 10)
    assert normalize_sheet_range("12") == (12, None)


def test_parse_filename_invalid_discipline(sample_config: Config) -> None:
    path = Path("2401490_Stage2_BAD_PLANS_0001.pdf")
    parsed, messages = parse_filename(path, sample_config)
    assert parsed is not None
    assert any("Discipline" in msg.text for msg in messages)


def test_parse_filename_invalid_sheet_format(sample_config: Config) -> None:
    path = Path("2401490_Stage2_ROAD_PLANS_1.pdf")
    parsed, messages = parse_filename(path, sample_config)
    assert parsed is not None
    assert any("must be" in msg.text for msg in messages)
