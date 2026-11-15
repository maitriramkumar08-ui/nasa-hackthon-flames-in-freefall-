"""The engine bridge, exercised against a fictional engine at every failure point.

The engine under test produces meaningless numbers on purpose; these tests check the
contract, the unit handling and the refusals, never physical correctness.
"""

from pathlib import Path
from typing import Any

import pytest

from pyra.adapters import ClaimGateError
from pyra.adapters.external import (
    CONTRACT_VERSION,
    EngineCommand,
    EngineFailedError,
    EngineNotFoundError,
    EngineOutputError,
    ExternalEngineAdapter,
    python_engine_command,
    scenario_payload,
)
from pyra.provenance import Status
from pyra.schema import Conditions, FuelSpec, Measure, ModelCard, Scenario, ValidationEvidence

ENGINE = Path(__file__).resolve().parents[1] / "fixtures" / "fake_engine.py"

COVERING_ENVELOPE: dict[str, Any] = {
    "gravity_g": [0.0, 1.1],
    "o2_mole_fraction": [0.18, 0.25],
    "pressure": {"min": 95, "max": 105, "unit": "kPa"},
}


def conditions(*, gravity_g: float = 1.0, o2: float = 0.21, pressure_kpa: float = 101.3):
    return Conditions(
        gravity_g=Measure(value=gravity_g, unit="dimensionless"),
        pressure=Measure(value=pressure_kpa, unit="kPa"),
        o2_mole_fraction=Measure(value=o2, unit="dimensionless"),
        diluent="nitrogen",
        flow_mode="forced",
        fuel=FuelSpec(material="PMMA", thickness=Measure(value=0.003, unit="m")),
        configuration="concurrent",
        length_scale=Measure(value=0.02, unit="m"),
    )


def scenario(scenario_id: str = "bridge-demo", **kwargs: Any) -> Scenario:
    return Scenario(scenario_id=scenario_id, purpose="example", conditions=conditions(**kwargs))


def card(envelope: dict[str, Any] | None = None, *, name: str = "fake-engine") -> ModelCard:
    evidence = (
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
    )
    return ModelCard(
        name=name,
        version="0.1",
        code_hash="sha256:fictional",
        licence="MIT",
        physics_summary="fictional test engine",
        envelope=evidence,
    )


def adapter(
    envelope: dict[str, Any] | None = None,
    *engine_flags: str,
    timeout_s: float = 300.0,
) -> ExternalEngineAdapter:
    base = python_engine_command(ENGINE)
    command = EngineCommand(
        executable=base.executable,
        args=(*base.args, *engine_flags),
        timeout_s=timeout_s,
    )
    return ExternalEngineAdapter(card(envelope), command)


def test_the_scenario_payload_carries_units_and_the_contract_version() -> None:
    payload = scenario_payload(scenario())
    assert payload["pyra_contract"] == CONTRACT_VERSION
    assert payload["scenario_id"] == "bridge-demo"
    sent = payload["conditions"]
    assert isinstance(sent, dict)
    assert sent["pressure"] == {"value": 101.3, "unit": "kPa", "u": None, "u_kind": "unknown"}
    assert sent["fuel"]["material"] == "PMMA"
    assert sent["fuel"]["thickness"]["unit"] == "m"


def test_a_successful_run_returns_a_validated_output_with_units_and_geometry() -> None:
    run = adapter().run(scenario())
    assert run.status is Status.SIMULATED
    assert run.engine_version == "0.1.0-fictional"
    assert run.model_card_id == "fake-engine:0.1"
    assert run.channel("hrr").unit == "kW"
    assert run.channel("hrr").label == "Heat release rate [kW]"
    assert len(run.channel("hrr").values) == len(run.time_s)
    assert run.flame_front is not None
    assert run.mesh is not None and run.mesh.dimensions == 2
    assert run.warnings and "no physical meaning" in run.warnings[0]
    assert run.duration_s == pytest.approx(10.0)


def test_the_scenario_actually_reaches_the_engine() -> None:
    """Different oxygen input must produce a different result, or the bridge is a no-op."""
    low = adapter().run(scenario(o2=0.18)).channel("hrr").values[-1]
    high = adapter().run(scenario(o2=0.25)).channel("hrr").values[-1]
    assert high > low


def test_a_run_round_trips_through_json_for_reproducibility(tmp_path: Path) -> None:
    from pyra.simulation import SimulationOutput

    run = adapter().run(scenario())
    restored = SimulationOutput.load(run.save(tmp_path / "run.json"))
    assert restored.to_dict() == run.to_dict()


def test_a_missing_executable_says_how_to_fix_it() -> None:
    broken = ExternalEngineAdapter(
        card(), EngineCommand(executable="pyra-no-such-engine-executable")
    )
    with pytest.raises(EngineNotFoundError, match="Install the engine"):
        broken.run(scenario())


def test_a_non_zero_exit_surfaces_the_engine_diagnostics() -> None:
    with pytest.raises(EngineFailedError, match="simulated failure"):
        adapter(None, "--exit-code=3").run(scenario())


def test_a_timeout_is_reported_rather_than_hanging() -> None:
    with pytest.raises(EngineFailedError, match="did not finish within"):
        adapter(None, "--hang", timeout_s=1.0).run(scenario())


def test_non_json_and_empty_output_are_rejected_clearly() -> None:
    with pytest.raises(EngineOutputError, match="did not return valid JSON"):
        adapter(None, "--emit-garbage").run(scenario())
    with pytest.raises(EngineOutputError, match="wrote nothing to stdout"):
        adapter(None, "--emit-nothing").run(scenario())


def test_a_malformed_channel_is_rejected_with_the_contract_reason() -> None:
    with pytest.raises(EngineOutputError, match="unusable output.*missing 'unit'"):
        adapter(None, "--drop-unit").run(scenario())


def test_an_engine_answering_the_wrong_scenario_or_claiming_another_card_is_refused() -> None:
    with pytest.raises(EngineOutputError, match="but was asked about 'bridge-demo'"):
        adapter(None, "--wrong-scenario").run(scenario())
    with pytest.raises(EngineOutputError, match="but its card says 'fake-engine:0.1'"):
        adapter(None, "--wrong-card").run(scenario())


def test_run_supported_refuses_a_scenario_outside_the_recorded_envelope() -> None:
    gated = adapter(COVERING_ENVELOPE)
    with pytest.raises(ClaimGateError, match="o2_mole_fraction is 0.1"):
        gated.run_supported(scenario(o2=0.1))


def test_run_supported_returns_the_evidence_that_backed_the_claim() -> None:
    run, check = adapter(COVERING_ENVELOPE).run_supported(scenario())
    assert check.inside
    assert check.covering[0].experiment_ids == ("fictional-bench-01",)
    assert run.channel("hrr").values[-1] > 0


def test_run_without_evidence_still_works_for_exploration() -> None:
    """An unvalidated engine may be explored; it just cannot support a claim."""
    plain = adapter(None)
    assert plain.run(scenario()).status is Status.SIMULATED
    with pytest.raises(ClaimGateError, match="no validation evidence"):
        plain.run_supported(scenario())


def test_hindcast_rewrites_the_scenario_with_measured_conditions() -> None:
    base = scenario()
    replayed = adapter().at(conditions(o2=0.19), base)
    assert replayed.purpose == "hindcast"
    assert replayed.conditions.o2_mole_fraction.value == 0.19
    assert replayed.scenario_id == base.scenario_id


def test_engine_command_rejects_nonsense_configuration() -> None:
    with pytest.raises(ValueError, match="executable must not be empty"):
        EngineCommand(executable="   ")
    with pytest.raises(ValueError, match="timeout_s must be positive"):
        EngineCommand(executable="engine", timeout_s=0)


def test_a_cancelled_run_stops_promptly_instead_of_waiting_for_the_timeout() -> None:
    """Cancel must beat the timeout, or a GUI stop button would do nothing useful."""
    import threading
    import time

    from pyra.adapters import EngineCancelled

    gated = adapter(None, "--hang", timeout_s=30.0)
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()

    started = time.monotonic()
    with pytest.raises(EngineCancelled, match="was cancelled"):
        gated.run(scenario(), cancel=cancel)
    assert time.monotonic() - started < 10.0


def test_a_run_cancelled_before_it_starts_never_reaches_the_engine() -> None:
    import threading

    from pyra.adapters import EngineCancelled

    cancel = threading.Event()
    cancel.set()
    with pytest.raises(EngineCancelled):
        adapter(None, "--hang", timeout_s=30.0).run(scenario(), cancel=cancel)
