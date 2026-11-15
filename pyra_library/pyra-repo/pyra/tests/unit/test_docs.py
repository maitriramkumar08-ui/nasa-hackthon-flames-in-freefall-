"""The documentation is executable: doctests, the quickstart script and the generated API page."""

import doctest
import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
FLAGS = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE


def test_usage_page_examples_run() -> None:
    result = doctest.testfile(
        str(DOCS / "usage.md"), module_relative=False, optionflags=FLAGS, verbose=False
    )
    assert result.attempted > 10, "the usage page should contain doctest examples"
    assert result.failed == 0


def test_quickstart_script_runs_and_prints_expected_lines() -> None:
    res = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "quickstart.py")],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    assert "ratio status: SCENARIO" in res.stdout
    assert "lineage problems: []" in res.stdout


def test_complete_fire_test_example_runs_and_saves_output(tmp_path: Path) -> None:
    res = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "complete_fire_test.py")],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    assert "PYRA single-zone learning model (SIMULATED)" in res.stdout
    assert (tmp_path / "fire_test_result.json").exists()


def test_envelope_gate_example_runs_and_refuses_the_out_of_envelope_claim() -> None:
    res = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "envelope_gate.py")],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    assert "is OUTSIDE the recorded validation envelope" in res.stdout
    assert "ClaimGateError (this is the correct outcome)" in res.stdout
    assert "records no envelope limits" in res.stdout


def test_engine_study_example_runs_the_whole_flow() -> None:
    res = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "engine_study.py")],
        capture_output=True,
        text=True,
        check=True,
        env={"PYTHONPATH": str(ROOT / "src"), "PATH": ""},
    )
    assert "Validation envelope: covered by fictional-bench-01" in res.stdout
    assert "Refused, correctly:" in res.stdout
    assert "exploration only" in res.stdout
    assert "scenario.json" in res.stdout and "simulation_output.json" in res.stdout


def test_generated_api_page_is_up_to_date() -> None:
    script = ROOT / "scripts" / "gen_api_docs.py"
    spec = importlib.util.spec_from_file_location("gen_api_docs", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (DOCS / "api.md").read_text(encoding="utf-8") == module.render(), (
        "docs/api.md is stale: run python scripts/gen_api_docs.py"
    )


def test_every_public_name_is_documented() -> None:
    import pyrakit.provenance as prov

    page = (DOCS / "api.md").read_text(encoding="utf-8")
    missing = [n for n in prov.__all__ if f"`{n}" not in page]
    assert not missing, missing


def test_top_level_exports_exist() -> None:
    import pyrakit

    for name in pyrakit.__all__:
        assert hasattr(pyrakit, name), name
