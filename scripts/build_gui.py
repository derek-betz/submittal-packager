"""Build the Submittal Packager GUI into a standalone executable using PyInstaller."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
TEMPLATES_DIR = PROJECT_ROOT / "templates"


def run_pyinstaller(output_dir: Path, *, clean: bool = False) -> None:
    """Invoke PyInstaller with sensible defaults for the GUI."""

    build_dir = output_dir / "build"
    spec_dir = output_dir / "spec"
    build_dir.mkdir(parents=True, exist_ok=True)
    spec_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "pyinstaller",
        "--name",
        "submittal-packager-gui",
        "--noconfirm",
        "--windowed",
        "--paths",
        str(SRC_DIR),
        "--distpath",
        str(output_dir),
        "--workpath",
        str(build_dir),
        "--specpath",
        str(spec_dir),
        "--add-data",
        f"{TEMPLATES_DIR}{os.pathsep}templates",
        "--collect-submodules",
        "submittal_packager",
        str(SRC_DIR / "submittal_packager" / "gui" / "app.py"),
    ]
    if clean:
        cmd.insert(1, "--clean")
    env = os.environ.copy()
    subprocess.check_call(cmd, env=env, cwd=PROJECT_ROOT)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove PyInstaller cache before building.",
    )
    parser.add_argument(
        "--dist",
        type=Path,
        help="Optional custom distribution directory. Defaults to PyInstaller's dist/.",
    )
    args = parser.parse_args(argv)

    if args.dist:
        os.environ["PYINSTALLER_CONFIG_DIR"] = str(args.dist.resolve())
        os.environ["PYINSTALLER_CACHE_DIR"] = str(args.dist.resolve() / ".cache")

    run_pyinstaller(args.dist or PROJECT_ROOT / "dist", clean=args.clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
