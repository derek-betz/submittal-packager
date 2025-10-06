"""Typer-based CLI for submittal packager."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console

from .config import ConfigError, save_config, Config, ProjectConfig, ConventionsConfig, StageArtifacts, RequirementConfig, ChecksConfig, PackagingConfig, TemplatesConfig
from .packager import ValidationFailure, run_package, run_report, run_validate

app = typer.Typer(help="Validate and package INDOT roadway plan submittals.")
console = Console()


def _configure_logging(level: str, log_file: Path | None) -> None:
    logger.remove()
    logger.add(console.print, level=level)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_file, level=level)


@app.command()
def validate(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True),
    stage: str = typer.Option(..., "--stage", help="Stage name (Stage1, Stage2, Stage3, Final)"),
    config: Path = typer.Option(..., "--config", help="Path to configuration YAML"),
    strict: bool = typer.Option(False, "--strict/--no-strict", help="Treat warnings as errors"),
    out: Path = typer.Option(Path("dist"), "--out", help="Output directory"),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file", help="Ignore file similar to .gitignore"),
    log_level: str = typer.Option("INFO", "--log-level", help="Logging level"),
    map_file: Optional[Path] = typer.Option(None, "--map", help="Write JSON grouping by discipline/sheet type"),
) -> None:
    """Validate the provided directory."""

    log_path = out / "submittal_packager.log"
    _configure_logging(log_level.upper(), log_path)
    try:
        result = run_validate(path, config, stage, strict=strict, ignore_file=ignore_file, map_file=map_file)
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=4)

    if result.has_errors:
        for message in result.errors:
            console.print(f"[red]ERROR:[/red] {message.text}")
        for message in result.warnings:
            console.print(f"[yellow]WARNING:[/yellow] {message.text}")
        raise typer.Exit(code=3)

    for message in result.warnings:
        console.print(f"[yellow]WARNING:[/yellow] {message.text}")
    console.print("[green]Validation completed successfully.[/green]")
    raise typer.Exit(code=0 if not result.has_warnings else 2)


@app.command()
def package(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True),
    stage: str = typer.Option(..., "--stage"),
    config: Path = typer.Option(..., "--config"),
    strict: bool = typer.Option(False, "--strict/--no-strict"),
    out: Path = typer.Option(Path("dist"), "--out"),
    ignore_file: Optional[Path] = typer.Option(None, "--ignore-file"),
    log_level: str = typer.Option("INFO", "--log-level"),
    no_scan: bool = typer.Option(False, "--no-scan", help="Skip PDF keyword scanning"),
    map_file: Optional[Path] = typer.Option(None, "--map"),
) -> None:
    """Validate and package the directory into a ZIP."""

    log_path = out / "submittal_packager.log"
    _configure_logging(log_level.upper(), log_path)
    try:
        result = run_package(
            path,
            config,
            stage,
            out_dir=out,
            strict=strict,
            ignore_file=ignore_file,
            no_scan=no_scan,
            log_path=log_path,
            map_file=map_file,
        )
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=4)
    except ValidationFailure as failure:
        for message in failure.result.errors:
            console.print(f"[red]ERROR:[/red] {message.text}")
        for message in failure.result.warnings:
            console.print(f"[yellow]WARNING:[/yellow] {message.text}")
        raise typer.Exit(code=3)

    for message in result.warnings:
        console.print(f"[yellow]WARNING:[/yellow] {message.text}")
    console.print("[green]Packaging completed.[/green]")


@app.command("report")
def report_command(
    path: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True),
    stage: str = typer.Option(..., "--stage"),
    config: Path = typer.Option(..., "--config"),
    out: Path = typer.Option(Path("dist"), "--out"),
) -> None:
    """Regenerate HTML report from last manifest."""

    log_path = out / "submittal_packager.log"
    _configure_logging("INFO", log_path)
    try:
        report_path = run_report(path, config, stage, out_dir=out)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=3)
    except ConfigError as exc:
        console.print(f"[red]Configuration error:[/red] {exc}")
        raise typer.Exit(code=4)

    console.print(f"[green]Report regenerated at {report_path}[/green]")


@app.command("init-config")
def init_config(path: Path = typer.Argument(..., writable=True, resolve_path=True)) -> None:
    """Write an example configuration file to PATH."""

    config = Config(
        project=ProjectConfig(
            designation="Des 0000000",
            route="SR 00",
            project_name="Example Project",
            consultant="Consultant",
            contact="Jane Doe <jane@example.com>",
            stage="Stage1",
        ),
        conventions=ConventionsConfig(
            filename_pattern="{des}_{stage}_{discipline}_{sheet_type}_{sheet_range}.{ext}",
            regex="^(?P<des>\\d{7})_(?P<stage>Stage[123]|Final)_(?P<discipline>[A-Z]+)_(?P<sheet_type>[A-Za-z0-9]+)_(?P<sheet_range>\\d+(?:-\\d+)?)\\.(?P<ext>pdf|docx)$",
        ),
        stages={
            "Stage1": StageArtifacts(
                required=[
                    RequirementConfig(key="title_sheet", pattern="*TITLE*.pdf"),
                    RequirementConfig(key="index_sheet", pattern="*INDEX*.pdf"),
                ]
            )
        },
        checks=ChecksConfig(),
        packaging=PackagingConfig(),
        templates=TemplatesConfig(
            transmittal_docx="templates/transmittal.docx.j2",
            report_html="templates/report.html.j2",
        ),
    )
    save_config(config, path)
    console.print(f"[green]Wrote configuration to {path}[/green]")


if __name__ == "__main__":
    app()
