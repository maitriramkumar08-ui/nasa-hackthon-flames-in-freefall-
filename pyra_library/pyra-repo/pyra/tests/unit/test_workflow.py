"""The coordinating workflow must gate, run, record and compare in that order."""

import json
from pathlib import Path
from typing import Any

import pytest

from pyrakit.adapters import ClaimGateError, EngineCommand, ExternalEngineAdapter
from pyrakit.adapters.external import python_engine_command
from pyrakit.schema import Conditions, FuelSpec, Measure, ModelCard, Scenario, ValidationEvidence
from pyrakit.service.workflow import run_engine_study

ENGINE = Path(__file__).resolve().parents[1] / "fixtures" / "fake_engine.py"

ENVELOPE: dict[str, Any] = {
    "gravity_g": [0.0, 1.1],
    "o2_mole_fraction": [0.18, 0.25],
    "pressure": {"min": 95, "max": 105, "unit": "kPa"},
}


def scenario(scenario_id: str = "study-demo", o2: float = 0.21) -> Scenario:
    return Scenario(
        scenario_id=scenario_id,
        purpose="example",
        conditions=Conditions(
            gravity_g=Measure(value=1.0, unit="dimensionless"),
            pressure=Measure(value=101.3, unit="kPa"),
            o2_mole_fraction=Measure(value=o2, unit="dimensionless"),
            diluent="nitrogen",
            flow_mode="forced",
            fuel=FuelSpec(material="PMMA"),
            configuration="concurrent",
            length_scale=Measure(value=0.02, unit="m"),
        ),
    )


def adapter(envelope: dict[str, Any] | None = ENVELOPE) -> ExternalEngineAdapter:
    base = python_engine_command(ENGINE)
    card = ModelCard(
        name="fake-engine",
        version="0.1",
        code_hash="sha256:fictional",
        licence="MIT",
        physics_summary="fictional test engine",
        envelope=(
            []
            if envelope is None
            else [
                ValidationEvidence(
                    experiment_ids=["fictional-bench-01"],
                    quantity="hrr",
                    metric="bias",
                    result={"bias": 0.0},
                    envelope=envelope,
                )
            ]
        ),
    )
    return ExternalEngineAdapter(card, EngineCommand(executable=base.executable, args=base.args))


def test_a_supported_study_records_the_evidence_that_backed_it() -> None:
    study = run_engine_study(adapter(), scenario())
    assert study.supported
    assert study.envelope is not None and study.envelope.inside
    assert "covered by fictional-bench-01" in study.summary()
    assert "SIMULATED" in study.summary()


def test_an_unsupported_scenario_is_refused_before_the_engine_runs() -> None:
    with pytest.raises(ClaimGateError, match="o2_mole_fraction is 0.1"):
        run_engine_study(adapter(), scenario(o2=0.1))


def test_exploration_mode_runs_but_says_the_envelope_was_not_checked() -> None:
    study = run_engine_study(adapter(None), scenario(), require_support=False)
    assert not study.supported
    assert study.envelope is None
    assert "exploration only" in study.summary()
    assert "cannot support a claim" in study.summary()


def test_saving_keeps_the_scenario_beside_the_output(tmp_path: Path) -> None:
    study = run_engine_study(adapter(), scenario(), save_to=tmp_path / "run")
    assert study.saved_to is not None
    saved_scenario = json.loads((study.saved_to / "scenario.json").read_text(encoding="utf-8"))
    assert saved_scenario["scenario_id"] == "study-demo"
    assert saved_scenario["conditions"]["pressure"]["unit"] == "kPa"
    assert (study.saved_to / "simulation_output.json").exists()
    assert str(study.saved_to) in study.summary()


def test_a_comparison_uses_the_channel_unit_and_reports_the_verdict() -> None:
    generous = run_engine_study(
        adapter(), scenario(), compare_channel="hrr", observed=2.0, tolerance=100.0
    )
    assert generous.comparison is not None
    assert generous.comparison.unit == "kW"
    assert generous.comparison.within_tolerance
    assert "within the tolerance" in generous.summary()

    strict = run_engine_study(
        adapter(), scenario(), compare_channel="hrr", observed=2.0, tolerance=0.001
    )
    assert strict.comparison is not None and not strict.comparison.within_tolerance
    assert "outside the tolerance" in strict.summary()
    assert "not an uncertainty-aware validation" in strict.summary()


def test_comparison_arguments_must_be_given_together() -> None:
    with pytest.raises(ValueError, match="together or not at all"):
        run_engine_study(adapter(), scenario(), compare_channel="hrr")
    with pytest.raises(ValueError, match="together or not at all"):
        run_engine_study(adapter(), scenario(), observed=1.0, tolerance=0.5)


def test_comparing_an_unknown_channel_lists_what_the_run_has() -> None:
    with pytest.raises(KeyError, match="this run has"):
        run_engine_study(
            adapter(), scenario(), compare_channel="temperature", observed=1.0, tolerance=1.0
        )


def test_engine_warnings_reach_the_summary() -> None:
    assert "no physical meaning" in run_engine_study(adapter(), scenario()).summary()
