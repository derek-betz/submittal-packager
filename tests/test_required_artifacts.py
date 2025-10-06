from pathlib import Path

from submittal_packager.config import RequirementConfig
from submittal_packager.validators import validate_required


def test_missing_required_artifact(tmp_path: Path) -> None:
    files = [tmp_path / "a.pdf"]
    requirement = RequirementConfig(key="title_sheet", pattern="*TITLE*.pdf")
    messages = validate_required(files, [requirement])
    assert any("Missing required" in message.text for message in messages)


def test_required_artifact_present(tmp_path: Path) -> None:
    required_file = tmp_path / "MY_TITLE.pdf"
    required_file.write_text("test")
    files = [required_file]
    requirement = RequirementConfig(key="title_sheet", pattern="*TITLE*.pdf")
    messages = validate_required(files, [requirement])
    assert not messages
