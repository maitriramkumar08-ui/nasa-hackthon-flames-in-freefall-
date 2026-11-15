"""The engine output contract must reject malformed runs before anything plots them.

Every number here is a fictional fixture, not a physical result.
"""

from pathlib import Path
from typing import Any

import pytest

from pyra.provenance import Quantity, Status
from pyra.simulation import Channel, FlameFront, MeshInfo, SimulationOutput


def output(**overrides: Any) -> SimulationOutput:
    payload: dict[str, Any] = {
        "scenario_id": "demo",
        "model_card_id": "fake-engine:0.1",
        "engine_version": "0.1.0",
        "time_s": (0.0, 1.0, 2.0),
        "channels": {
            "hrr": Channel(
                name="hrr", unit="kW", values=(0.0, 5.0, 7.5), long_name="Heat release rate"
            )
        },
    }
    payload.update(overrides)
    return SimulationOutput(**payload)


def test_a_well_formed_run_exposes_its_time_base_and_channels() -> None:
    run = output()
    assert run.status is Status.SIMULATED
    assert run.duration_s == 2.0
    assert run.channel("hrr").label == "Heat release rate [kW]"
    assert run.sample_at(1.4) == 1
    assert run.sample_at(-10.0) == 0


def test_channel_length_must_match_the_time_base() -> None:
    with pytest.raises(ValueError, match="but the time base has 3"):
        output(channels={"hrr": Channel(name="hrr", unit="kW", values=(0.0, 1.0))})


def test_time_base_must_increase_strictly() -> None:
    with pytest.raises(ValueError, match="must increase strictly"):
        output(time_s=(0.0, 1.0, 1.0))
    with pytest.raises(ValueError, match="at least two samples"):
        output(time_s=(0.0,), channels={"hrr": Channel(name="hrr", unit="kW", values=(1.0,))})


def test_an_unparsable_unit_is_refused() -> None:
    with pytest.raises(ValueError, match="unknown unit"):
        Channel(name="hrr", unit="kilowottage", values=(1.0,))


def test_non_finite_and_non_numeric_samples_are_refused() -> None:
    for bad in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="finite"):
            Channel(name="hrr", unit="kW", values=(0.0, bad))
    with pytest.raises(ValueError, match="only numbers"):
        Channel(name="hrr", unit="kW", values=(0.0, "hot"))


def test_channel_key_must_agree_with_channel_name() -> None:
    with pytest.raises(ValueError, match="does not match its name"):
        output(channels={"heat": Channel(name="hrr", unit="kW", values=(0.0, 1.0, 2.0))})


def test_uncertainty_must_match_length_and_be_non_negative() -> None:
    with pytest.raises(ValueError, match="uncertainty has 2 samples"):
        Channel(name="hrr", unit="kW", values=(1.0, 2.0, 3.0), uncertainty=(0.1, 0.1))
    with pytest.raises(ValueError, match="non-negative"):
        Channel(name="hrr", unit="kW", values=(1.0,), uncertainty=(-0.1,))


def test_a_run_needs_identity_before_it_can_be_trusted_to_be_reproducible() -> None:
    for blank in ("scenario_id", "model_card_id", "engine_version"):
        with pytest.raises(ValueError, match=f"{blank} must not be empty"):
            output(**{blank: "  "})


def test_channel_conversion_preserves_values_and_uncertainty() -> None:
    channel = Channel(name="hrr", unit="kW", values=(1.0, 2.0), uncertainty=(0.1, 0.2))
    converted = channel.converted_to("W")
    assert converted.unit == "W"
    assert converted.values == pytest.approx((1000.0, 2000.0))
    assert converted.uncertainty == pytest.approx((100.0, 200.0))


def test_a_sample_driven_by_a_hypothetical_input_stays_scenario_status() -> None:
    """Status can only weaken: a run fed a hypothetical input cannot claim SIMULATED."""
    hypothetical = Quantity.scenario(0.21, "dimensionless", None, "unknown", activity="user_input")
    value = output().channel("hrr").quantity_at(2, scenario_input=hypothetical, activity="fake@1")
    assert value.status is Status.SCENARIO
    assert value.value == 7.5
    assert hypothetical.prov.artifact_id in value.prov.parents


def test_a_sample_driven_by_a_measured_input_is_simulated() -> None:
    observed = Quantity.measured(
        0.21, "dimensionless", 0.001, "type_b", source_ref="fictional-bench-01|row 3"
    )
    value = output().channel("hrr").quantity_at(1, scenario_input=observed, activity="fake@1")
    assert value.status is Status.SIMULATED
    assert value.value == 5.0


def test_engine_reported_uncertainty_reaches_the_lifted_quantity() -> None:
    channel = Channel(name="hrr", unit="kW", values=(1.0, 2.0), uncertainty=(0.1, 0.25))
    observed = Quantity.measured(1.0, "kW", 0.01, "type_b", source_ref="fictional|row 1")
    value = channel.quantity_at(1, scenario_input=observed, activity="fake@1")
    assert value.u == 0.25
    assert value.u_kind == "type_b"


def test_unknown_channel_names_what_is_available() -> None:
    with pytest.raises(KeyError, match="this run has"):
        output().channel("temperature")


def test_round_trip_through_json_preserves_limits_warnings_and_geometry(tmp_path: Path) -> None:
    run = output(
        flame_front=FlameFront(position_m=(0.0, 0.01, 0.02), length_m=(0.0, 0.005, 0.01)),
        mesh=MeshInfo(dimensions=2, cell_count=4096, min_cell_size_m=0.0005, note="uniform"),
        warnings=("coarse mesh near the inlet",),
        artifacts={"field_data": "run/fields.nc"},
        assumptions=("fictional engine", "no radiation model"),
    )
    restored = SimulationOutput.load(run.save(tmp_path / "run.json"))
    assert restored.to_dict() == run.to_dict()
    assert restored.warnings == ("coarse mesh near the inlet",)
    assert restored.artifacts == {"field_data": "run/fields.nc"}
    assert restored.mesh is not None and restored.mesh.cell_count == 4096
    assert restored.flame_front is not None
    assert restored.flame_front.length_m == (0.0, 0.005, 0.01)


def test_malformed_engine_json_names_the_missing_piece() -> None:
    with pytest.raises(ValueError, match="missing required keys"):
        SimulationOutput.from_dict({"scenario_id": "demo"})
    with pytest.raises(ValueError, match="is missing 'unit'"):
        SimulationOutput.from_dict(
            {
                "scenario_id": "d",
                "model_card_id": "m:1",
                "engine_version": "1",
                "time_s": [0.0, 1.0],
                "channels": {"hrr": {"values": [1.0, 2.0]}},
            }
        )
    with pytest.raises(ValueError, match="unknown status"):
        SimulationOutput.from_dict(
            {
                "scenario_id": "d",
                "model_card_id": "m:1",
                "engine_version": "1",
                "status": "VALIDATED",
                "time_s": [0.0, 1.0],
                "channels": {"hrr": {"unit": "kW", "values": [1.0, 2.0]}},
            }
        )


def test_flame_front_and_mesh_are_structurally_checked() -> None:
    with pytest.raises(ValueError, match="do not match the time base"):
        output(flame_front=FlameFront(position_m=(0.0, 0.01)))
    with pytest.raises(ValueError, match="length_m length does not match"):
        FlameFront(position_m=(0.0, 0.1), length_m=(0.0,))
    with pytest.raises(ValueError, match="dimensions must be 1, 2 or 3"):
        MeshInfo(dimensions=4, cell_count=10, min_cell_size_m=0.01)
    with pytest.raises(ValueError, match="min_cell_size_m must be a positive"):
        MeshInfo(dimensions=2, cell_count=10, min_cell_size_m=0.0)
