"""P2 schema and unit contracts."""

import pytest

from pyra.schema import Conditions, FuelSpec, Measure, ModelCard, Scenario, SourceRef


def conditions() -> Conditions:
    return Conditions(
        gravity_g=Measure(value=1e-5, unit="dimensionless", u=1e-6, u_kind="type_a"),
        pressure=Measure(value=101.3, unit="kPa", u=0.1, u_kind="type_b"),
        o2_mole_fraction=Measure(value=0.21, unit="mole_fraction", u=0.001, u_kind="type_b"),
        diluent="nitrogen",
        flow_velocity=Measure(value=2, unit="cm/s", u=0.1, u_kind="type_b"),
        flow_mode="forced",
        temperature=Measure(value=300, unit="K", u=1, u_kind="type_b"),
        fuel=FuelSpec(material="PMMA", thickness=Measure(value=2, unit="mm")),
        configuration="concurrent",
        length_scale=Measure(value=2, unit="cm"),
    )


def test_conditions_round_trip_and_microgravity_is_residual() -> None:
    scenario = Scenario(scenario_id="synthetic-1", conditions=conditions())
    restored = Scenario.model_validate_json(scenario.model_dump_json())
    assert restored == scenario
    assert restored.conditions.gravity_g.value == 1e-5


def test_incompatible_units_are_rejected() -> None:
    with pytest.raises(ValueError, match="compatible"):
        Conditions(
            gravity_g=Measure(value=1, unit="second"),
            pressure=Measure(value=1, unit="kPa"),
            o2_mole_fraction=Measure(value=0.2, unit="dimensionless"),
            diluent="nitrogen",
            fuel=FuelSpec(material="PMMA"),
            configuration="other",
            length_scale=Measure(value=1, unit="m"),
        )


def test_measure_uncertainty_kind_is_explicit() -> None:
    with pytest.raises(ValueError, match="u is None"):
        Measure(value=1, unit="kPa", u=0.1)


def test_schema_models_expose_json_schema() -> None:
    card = ModelCard(
        name="synthetic", version="0", code_hash="unknown", licence="unknown",
        physics_summary="fictional test model",
    )
    assert "properties" in card.model_json_schema()
    assert SourceRef(source_id="doi:10.0000/example").source_id.startswith("doi:")
