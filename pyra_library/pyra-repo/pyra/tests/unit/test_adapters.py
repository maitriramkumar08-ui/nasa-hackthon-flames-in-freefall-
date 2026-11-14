"""P8 adapter contracts."""

import pytest

from pyra.adapters import CallableAdapter, ClaimGateError, require_validated
from pyra.provenance import Status
from pyra.schema import Conditions, FuelSpec, Measure, ModelCard, Scenario, ValidationEvidence


def conditions() -> Conditions:
    return Conditions(
        gravity_g=Measure(value=1e-5, unit="dimensionless"),
        pressure=Measure(value=101, unit="kPa"),
        o2_mole_fraction=Measure(value=0.21, unit="dimensionless"),
        diluent="nitrogen",
        flow_mode="forced",
        fuel=FuelSpec(material="PMMA"),
        configuration="concurrent",
        length_scale=Measure(value=0.02, unit="m"),
    )


def card(validated: bool = False) -> ModelCard:
    evidence = ValidationEvidence(
        experiment_ids=["synthetic"],
        quantity="value",
        metric="bias",
        result={"bias": 0},
        envelope={"gravity_g": [0, 1]},
    )
    return ModelCard(
        name="toy",
        version="1",
        code_hash="abc",
        licence="MIT",
        physics_summary="fictional test model",
        envelope=[evidence] if validated else [],
    )


def test_callable_adapter_returns_simulated_result_and_hindcast() -> None:
    scenario = Scenario(scenario_id="s", conditions=conditions())
    adapter = CallableAdapter(card(True), lambda s: {"pressure": s.conditions.pressure.value})
    result = adapter.run(scenario)
    assert result.status is Status.SIMULATED
    assert result.model_card_id == "toy:1"
    assert result.outputs["pressure"] == 101
    assert adapter.at(conditions(), scenario).purpose == "hindcast"


def test_claim_gate_refuses_empty_validation_envelope() -> None:
    with pytest.raises(ClaimGateError):
        require_validated(card(False))
    require_validated(card(True))
