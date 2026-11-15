"""Renaming to ``pyrakit`` is what fixes the package-name collision; prove it stays fixed.

The application this library is developed alongside ships its own top-level package named
``pyra``. Because Python searches the current working directory before installed packages,
that folder used to win over the library and produce a confusing ImportError. The library's
canonical import is now ``pyrakit``, which that folder cannot shadow.
"""

import subprocess
import sys
from pathlib import Path

SRC = str(Path(__file__).resolve().parents[2] / "src")


def _run(code: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=cwd,
        env={"PYTHONPATH": SRC, "PATH": ""},
    )


def _decoy(directory: Path, name: str) -> Path:
    """Create an unrelated local package that could shadow an installed one."""
    package = directory / name
    package.mkdir()
    (package / "__init__.py").write_text('"""Unrelated local package."""\n', encoding="utf-8")
    return package


def test_a_local_pyra_folder_no_longer_breaks_the_library(tmp_path: Path) -> None:
    """The collision that motivated the rename: a sibling `pyra/` package."""
    _decoy(tmp_path, "pyra")
    result = _run("import pyrakit as pk; print(len(pk.__all__))", tmp_path)
    assert result.returncode == 0, result.stderr
    assert int(result.stdout.strip()) > 10


def test_the_library_still_works_beside_a_folder_named_pyra_library(tmp_path: Path) -> None:
    _decoy(tmp_path, "pyra_library")
    result = _run("import pyrakit as pk; print(pk.__version__)", tmp_path)
    assert result.returncode == 0, result.stderr


def test_a_shadowed_pyrakit_is_reported_with_the_real_cause(tmp_path: Path) -> None:
    """If someone shadows the new name too, the legacy alias still explains why."""
    decoy = _decoy(tmp_path, "pyrakit")
    result = _run("import pyra", tmp_path)
    assert result.returncode != 0
    assert "shadows the installed library" in result.stderr
    assert str(decoy) in result.stderr


def test_the_legacy_names_still_import_and_share_one_implementation(tmp_path: Path) -> None:
    code = (
        "import pyra, pyra_library, pyrakit;"
        "from pyra.schema import ModelCard as A;"
        "from pyrakit.schema import ModelCard as B;"
        "print(A is B, pyra.__version__ == pyrakit.__version__,"
        " pyra_library.__version__ == pyrakit.__version__)"
    )
    result = _run(code, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True True True"
