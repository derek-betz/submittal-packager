# Submittal Packager

A Python CLI for validating and packaging INDOT roadway plan submittals. Built with Typer, Pydantic, Rich, and other modern libraries.

## Requirements

### Software Requirements
- **Python**: 3.11 or higher
- **pip**: Python package installer (typically included with Python)

### Python Package Dependencies
The following packages are automatically installed when you set up the project:
- `typer[all]` - CLI framework
- `pydantic>=1.10` - Data validation
- `rich>=13` - Terminal formatting
- `PyPDF2>=3` - PDF manipulation
- `pdfminer.six>=20221105` - PDF text extraction
- `jinja2>=3` - Template engine
- `python-docx>=0.8` - Word document processing
- `pyyaml>=6` - YAML configuration files
- `tomli>=2` - TOML file parsing
- `pathspec>=0.11` - Path matching
- `loguru>=0.7` - Logging

### Optional Dependencies
- `pytest` - For running tests
- `pytest-cov` - For test coverage reports
- `PySide6` - Enables the graphical desktop application
- `pyinstaller` - Bundles the GUI into a standalone executable

### System Dependencies
- **Windows users**: May need Microsoft C++ Build Tools if `python-docx` fails to build

## Quickstart

```bash
powershell -ExecutionPolicy Bypass -File scripts/bootstrap.ps1

python -m venv .venv
source .venv/bin/activate
pip install -e .[test]
submittal-packager init-config config.yml --idm-stage Stage2
submittal-packager validate examples/sample --stage Stage2 --config config.yml
```

Install the graphical user interface and launch it with:

```bash
pip install -e .[gui]
submittal-packager-gui
```

## Graphical User Interface

The desktop client provides a guided workflow for INDOT reviewers and consultants:

- **Project setup** – capture the project root, configuration file, stage preset, and optional ignore/map files. IDM defaults are surfaced inline so teams understand the expected deliverables for each stage.
- **Validation results** – errors and warnings are grouped by severity with manifest metadata so issues can be triaged without digging through console output.
- **Packaging log** – real-time progress updates and log forwarding mirror the CLI experience while keeping the interface responsive.

All actions run on background threads and reuse the existing `run_validate`, `run_package`, and `run_report` routines so the CLI and GUI stay in lockstep.

Logs are written to `~/.submittal_packager/gui.log` and are also streamed into the packaging view for quick troubleshooting.

### Building a Windows-ready executable

The repository ships with a helper script that wraps PyInstaller:

```bash
pip install -e .[gui]
python scripts/build_gui.py --clean --dist dist/gui
```

The resulting `dist/gui/submittal-packager-gui` folder contains the executable and bundled resources that can be copied directly to INDOT workstations without requiring a Python install.

## Example Configuration

See [`examples/config.example.yml`](examples/config.example.yml) for a complete configuration file with comments and defaults.

## Commands

* `validate PATH --stage Stage2 --config config.yml`: Validate the project folder.

* `package PATH --stage Stage2 --config config.yml`: Validate and create manifest, checksums, transmittal, and ZIP package.
* `report PATH --stage Stage2 --config config.yml`: Rebuild the HTML report from the last validation run.
* `init-config PATH [--idm-stage Stage3]`: Write a starter `config.yml` to the given path using optional Indiana Design Manual presets.

## Packaging Outputs

Running `submittal-packager package` now creates a ZIP that mirrors the IDM checklist structure:

```
DESIGNATION_STAGE_IDM/
├── 0_Admin/            # Generated manifest, checksum register, transmittal, validation report, log
├── 1_Cover_Letter/     # Signed cover letter or correspondence supplied in the project folder
├── 2_Plan_Set/         # Plan PDFs grouped by discipline/stage metadata
├── 3_Supporting_Docs/  # Design memoranda, calculations, and other supplemental files
└── 4_PCFS/             # Project Certification Forms and approvals
```

The manifest CSV includes additional IDM-aligned metadata:

* `package_path` – final location inside the ZIP
* `checksum_algorithm` – algorithm used to calculate `checksum`
* `source_modified_utc` – timestamp of the original file
* Summary sections for folder, discipline, and file-extension totals

Checksums are stored as a CSV (`algorithm,checksum,relative_path,package_path`) to aid reviewers that prefer spreadsheet filters.

The generated DOCX transmittal and HTML validation report highlight consultant contact information, the certification statement, a packaging layout table, and any validation exceptions so teams can quickly confirm IDM compliance.

## IDM Stage Presets

The Indiana Design Manual datasets live in `src/submittal_packager/idm_requirements.py`. Each entry describes the required and optional artifacts, discipline codes, INDOT form references, and common keywords for Stage 1, Stage 2, Stage 3, and Final submittals. The configuration loader now supports a `preset` flag under each `stages` entry. When set, the curated defaults are merged with any user-provided overrides so teams can start from the official checklist and add project-specific files.

Generate a configuration that pulls these defaults directly from the CLI:

```bash
submittal-packager init-config config.yml --idm-stage Stage3
```

The resulting YAML includes the merged artifact lists and also seeds the PDF keyword scan check with the expected phrases for the chosen stage. You can switch presets later by editing the `preset` value or disabling inheritance with `inherit_defaults: false` if you need a completely custom stage definition.


## Extending Filename Rules

Update the `conventions` section of the configuration file. You can supply a new `filename_pattern`, `regex`, and optional `exceptions` list to allow vendor-specific file names. The parser converts the format string to a validation regex and exposes the parsed fields to manifest generation and reporting.

## Troubleshooting

* **Missing Python dependencies**: install build tools such as Microsoft C++ Build Tools on Windows if `python-docx` fails to build.
* **PDF text extraction**: ensure PDFs are text-based. Scanned PDFs may require OCR before validation.

## Tests

Run the unit tests with:

```bash
python scripts/run_tests.py -q
```
