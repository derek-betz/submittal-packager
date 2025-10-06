from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from PyPDF2 import PdfWriter
from PyPDF2.generic import DictionaryObject, NameObject, DecodedStreamObject

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
from submittal_packager.packager import run_validate


def _pdf(path: Path, text: str) -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font_dict = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font_dict)
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})})
    page[NameObject("/Resources")] = resources
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    stream = DecodedStreamObject(); stream.set_data(content.encode("utf-8"))
    stream_ref = writer._add_object(stream)
    page[NameObject("/Contents")] = stream_ref
    with path.open("wb") as handle:
        writer.write(handle)


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    with TemporaryDirectory() as tmp_project, TemporaryDirectory() as tmp_cfg:
        project_root = Path(tmp_project)
        _pdf(project_root / "2401490_Stage2_TITLE_TITLE_0001.pdf", "TITLE")
        _pdf(project_root / "2401490_Stage2_ROAD_PLANS_0001-0002.pdf", "PLANS")

        cfg_dir = Path(tmp_cfg)
        cfg = Config(
            project=ProjectConfig(
                designation="2401490",
                route="SR 14",
                project_name="SR 14 Improvements",
                consultant="Consultant",
                contact="Jane",
                stage="Stage2",
            ),
            conventions=ConventionsConfig(
                filename_pattern="{des}_{stage}_{discipline}_{sheet_type}_{sheet_range}.{ext}",
                regex=r"^(?P<des>\d{7})_(?P<stage>Stage[123]|Final)_(?P<discipline>[A-Z]+)_(?P<sheet_type>[A-Za-z0-9]+)_(?P<sheet_range>\d+(?:-\d+)?)\.(?P<ext>pdf|docx)$",
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
                transmittal_docx=str(repo / "templates" / "transmittal.docx.j2"),
                report_html=str(repo / "templates" / "report.html.j2"),
            ),
        )
        config_path = cfg_dir / "config.yml"
        save_config(cfg, config_path)
        res = run_validate(project_root, config_path, "Stage2")
        print("errors:", [m.text for m in res.errors])
        print("warnings:", [m.text for m in res.warnings])
        print("manifest files:", [e.relative_path for e in res.manifest])


if __name__ == "__main__":
    main()
