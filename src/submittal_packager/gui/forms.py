"""Form views used by the Submittal Packager GUI."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Optional

from loguru import logger
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..config import ConfigError, load_config
from ..idm_requirements import available_stage_presets, get_stage_defaults
from .models import ProjectSettings
from .widgets import KeyValueLabel, PathPicker


def _stage_summary(stage_key: str) -> str:
    defaults = get_stage_defaults(stage_key)
    if not defaults:
        return "No defaults available for the selected stage."
    lines = [f"<h3>{defaults.get('name', stage_key)}</h3>"]
    description = defaults.get("description")
    if description:
        lines.append(f"<p>{description}</p>")
    required = defaults.get("required") or []
    if required:
        lines.append("<h4>Required Artifacts</h4><ul>")
        for item in required:
            label = item.get("description", item.get("key", ""))
            pattern = item.get("pattern")
            lines.append(f"<li><b>{label}</b> <code>{pattern or ''}</code></li>")
        lines.append("</ul>")
    optional = defaults.get("optional") or []
    if optional:
        lines.append("<h4>Optional Artifacts</h4><ul>")
        for item in optional:
            label = item.get("description", item.get("key", ""))
            pattern = item.get("pattern")
            lines.append(f"<li><b>{label}</b> <code>{pattern or ''}</code></li>")
        lines.append("</ul>")
    codes = defaults.get("discipline_codes") or []
    if codes:
        lines.append(f"<p><b>Discipline Codes:</b> {', '.join(codes)}</p>")
    forms = defaults.get("forms") or []
    if forms:
        lines.append("<p><b>Required Forms:</b><br/>" + "<br/>".join(forms) + "</p>")
    keywords_required = defaults.get("keywords_required") or []
    if keywords_required:
        lines.append(
            "<p><b>Keywords Checked:</b> " + ", ".join(keywords_required) + "</p>"
        )
    keywords_forbidden = defaults.get("keywords_forbidden") or []
    if keywords_forbidden:
        lines.append(
            "<p><b>Forbidden Keywords:</b> " + ", ".join(keywords_forbidden) + "</p>"
        )
    return "\n".join(lines)


class ProjectSetupView(QWidget):
    """Capture project metadata and drive validation/packaging actions."""

    request_validate = Signal(ProjectSettings)
    request_package = Signal(ProjectSettings)
    request_report = Signal(ProjectSettings)

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        form_group = QGroupBox("Project Configuration", self)
        form_layout = QFormLayout(form_group)

        self._root_picker = PathPicker("Select project root", mode="directory")
        form_layout.addRow("Project root", self._root_picker)

        self._config_picker = PathPicker("Select configuration", mode="file")
        form_layout.addRow("Config file", self._config_picker)

        self._stage_combo = QComboBox(self)
        for stage in available_stage_presets():
            self._stage_combo.addItem(stage)
        form_layout.addRow("Stage", self._stage_combo)

        self._output_picker = PathPicker("Select output directory", mode="directory")
        form_layout.addRow("Output folder", self._output_picker)

        self._ignore_picker = PathPicker("Select ignore file", mode="file")
        form_layout.addRow("Ignore patterns", self._ignore_picker)

        self._map_picker = PathPicker("Select sheet map", mode="file")
        form_layout.addRow("Sheet map", self._map_picker)

        flags_layout = QHBoxLayout()
        self._strict_checkbox = QCheckBox("Fail on warnings", self)
        self._scan_checkbox = QCheckBox("Disable keyword scan", self)
        flags_layout.addWidget(self._strict_checkbox)
        flags_layout.addWidget(self._scan_checkbox)
        form_layout.addRow("Validation options", flags_layout)

        layout.addWidget(form_group)

        self._config_summary = QGroupBox("Config Overview", self)
        summary_layout = QVBoxLayout(self._config_summary)
        self._designation_label = KeyValueLabel("Designation", parent=self._config_summary)
        self._project_label = KeyValueLabel("Project name", parent=self._config_summary)
        summary_layout.addWidget(self._designation_label)
        summary_layout.addWidget(self._project_label)
        layout.addWidget(self._config_summary)

        self._stage_summary = QTextBrowser(self)
        self._stage_summary.setOpenExternalLinks(True)
        self._stage_summary.setReadOnly(True)
        stage_group = QGroupBox("Stage Guidance", self)
        stage_layout = QVBoxLayout(stage_group)
        stage_layout.addWidget(self._stage_summary)
        layout.addWidget(stage_group, stretch=1)

        buttons_layout = QHBoxLayout()
        self._validate_button = QPushButton("Validate", self)
        self._package_button = QPushButton("Package", self)
        self._report_button = QPushButton("Generate Report", self)
        buttons_layout.addWidget(self._validate_button)
        buttons_layout.addWidget(self._package_button)
        buttons_layout.addWidget(self._report_button)
        layout.addLayout(buttons_layout)

        layout.addStretch(1)

        self._stage_combo.currentTextChanged.connect(self._update_stage_guidance)
        self._config_picker.path_changed.connect(self._load_config_summary)
        self._validate_button.clicked.connect(self._trigger_validate)
        self._package_button.clicked.connect(self._trigger_package)
        self._report_button.clicked.connect(self._trigger_report)

        if self._stage_combo.count():
            self._update_stage_guidance(self._stage_combo.currentText())

    def _update_stage_guidance(self, stage_key: str) -> None:
        self._stage_summary.setHtml(_stage_summary(stage_key))

    def _load_config_summary(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            config = load_config(path)
        except ConfigError as exc:
            logger.exception("Failed to load config")
            QMessageBox.critical(self, "Config error", str(exc))
            return
        project = getattr(config, "project", None)
        if project:
            self._designation_label.set_value(getattr(project, "designation", None))
            self._project_label.set_value(getattr(project, "name", None))

    def _build_settings(self) -> Optional[ProjectSettings]:
        config_path = self._config_picker.path()
        root = self._root_picker.path()
        out_dir = self._output_picker.path()
        if not config_path or not root or not out_dir:
            QMessageBox.warning(self, "Missing information", "Root, config, and output directories are required.")
            return None
        if not config_path.exists():
            QMessageBox.warning(self, "Invalid config", "The selected config file does not exist.")
            return None
        if not root.exists():
            QMessageBox.warning(self, "Invalid root", "The selected project root does not exist.")
            return None
        ignore_path = self._ignore_picker.path()
        map_path = self._map_picker.path()
        if ignore_path and not ignore_path.exists():
            QMessageBox.warning(
                self,
                "Ignore file missing",
                "The selected ignore file does not exist.",
            )
            return None
        if map_path and not map_path.parent.exists():
            QMessageBox.warning(
                self,
                "Invalid sheet map location",
                "Please select a sheet map path in an existing folder.",
            )
            return None
        settings = ProjectSettings(
            stage=self._stage_combo.currentText(),
            root_directory=root,
            config_path=config_path,
            output_directory=out_dir,
            ignore_file=ignore_path,
            map_file=map_path,
            strict=self._strict_checkbox.isChecked(),
            disable_keyword_scan=self._scan_checkbox.isChecked(),
        )
        logger.debug("Prepared settings: {}", asdict(settings))
        return settings

    def _trigger_validate(self) -> None:
        settings = self._build_settings()
        if settings:
            self.request_validate.emit(settings)

    def _trigger_package(self) -> None:
        settings = self._build_settings()
        if settings:
            self.request_package.emit(settings)

    def _trigger_report(self) -> None:
        settings = self._build_settings()
        if settings:
            self.request_report.emit(settings)


__all__ = ["ProjectSetupView"]
