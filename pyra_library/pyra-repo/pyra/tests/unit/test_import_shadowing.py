"""A local folder named 'pyra' must produce an explanation, not a cryptic ImportError."""

import subprocess
import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[2] / "src")


def test_shadowed_pyra_package_reports_the_real_cause(tmp_path: Path) -> None:
    decoy = tmp_path / "pyra"
    decoy.mkdir()
    (decoy / "__init__.py").write_text('"""Unrelated local package."""\n', encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-c", "import pyra_library"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"PYTHONPATH": SRC, "PATH": ""},
    )
    assert result.returncode != 0
    assert "shadows the installed library" in result.stderr
    assert "is not the PYRA library" in result.stderr
    assert str(decoy) in result.stderr


def test_unshadowed_import_still_exposes_the_friendly_surface(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import pyra_library as pk; print(len(pk.__all__))"],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
        env={"PYTHONPATH": SRC, "PATH": ""},
    )
    assert int(result.stdout.strip()) > 10
