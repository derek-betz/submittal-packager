"""Run the test suite, installing test dependencies when needed."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXTRA_DEPENDENCIES = ".[test]"


def _pytest_available() -> bool:
    return importlib.util.find_spec("pytest") is not None


def _install_test_deps() -> None:
    print("pytest not found; installing test dependencies...", file=sys.stderr)
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", EXTRA_DEPENDENCIES],
        cwd=ROOT,
        check=True,
    )


def main() -> int:
    if not _pytest_available():
        try:
            _install_test_deps()
        except subprocess.CalledProcessError as exc:
            raise SystemExit(f"Failed to install test dependencies: {exc}") from exc
    result = subprocess.run([sys.executable, "-m", "pytest", *sys.argv[1:]], cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
