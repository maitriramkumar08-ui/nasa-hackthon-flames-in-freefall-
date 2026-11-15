"""The beginner form must become a validated scenario, or be refused with a reason.

All values are fictional teaching examples.
"""

import pytest

from pyra.service.playground import PlaybackTimeline, scenario_from_form
from pyra.service.scenario_inputs import PRESETS, TEACHING_EXAMPLE, FireScenario, ViewSource


def form(**overrides: str) -> dict[str, str]:
    values = {
        "fuel": "PMMA",
        "gravity_g": "1.0",
        "oxygen_fraction": "0.21",
        "pressure_kpa": "101.3",
        "temperature_k": "293.15",
        "diluent": "nitrogen",
        "flow_mode": "quiescent",
        "flow_velocity_m_s": "",
        "configuration": "concurrent",
        "length_scale_m": "0.02",
        "fuel_thickness_m": "",
        "ignition_power_w": "",
        "ignition_duration_s": "",
        "air_exchange_per_s": "0.02",
        "oxygen_sink_per_s": "0.001",
        "duration_s": "60",
    }
    values.update(overrides)
    return values


def test_the_form_becomes_a_validated_scenario_with_units() -> None:
    built = scenario_from_form(form(fuel_thickness_m="0.003"))
    scenario = built.to_scenario("demo")
    assert scenario.scenario_id == "demo"
    assert scenario.conditions.pressure.unit == "kPa"
    assert scenario.conditions.pressure.value == 101.3
    assert scenario.conditions.o2_mole_fraction.value == 0.21
    assert scenario.conditions.fuel.material == "PMMA"
    assert scenario.conditions.fuel.thickness is not None
    assert scenario.conditions.fuel.thickness.unit == "m"


def test_a_blank_optional_field_means_not_set_rather_than_zero() -> None:
    built = scenario_from_form(form())
    assert built.flow_velocity_m_s is None
    assert built.fuel_thickness_m is None
    assert built.to_scenario("demo").conditions.flow_velocity is None


def test_a_blank_required_field_and_a_non_number_are_both_refused() -> None:
    with pytest.raises(ValueError, match="pressure_kpa needs a value"):
        scenario_from_form(form(pressure_kpa=""))
    with pytest.raises(ValueError, match="must be a number, got 'warm'"):
        scenario_from_form(form(temperature_k="warm"))


def test_known_uncertainty_reaches_the_schema_and_unknown_stays_unknown() -> None:
    known = FireScenario(oxygen_uncertainty=0.005).to_scenario("demo")
    assert known.conditions.o2_mole_fraction.u == 0.005
    assert known.conditions.o2_mole_fraction.u_kind == "type_b"

    unknown = FireScenario().to_scenario("demo")
    assert unknown.conditions.o2_mole_fraction.u is None
    assert unknown.conditions.o2_mole_fraction.u_kind == "unknown"


def test_physically_impossible_inputs_are_refused_with_plain_reasons() -> None:
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        FireScenario(oxygen_fraction=1.4)
    with pytest.raises(ValueError, match="gravity_g must be non-negative"):
        FireScenario(gravity_g=-1.0)
    with pytest.raises(ValueError, match="pressure and temperature must be positive"):
        FireScenario(pressure_kpa=0.0)
    with pytest.raises(ValueError, match="duration_s must be positive"):
        FireScenario(duration_s=0.0)
    with pytest.raises(ValueError, match="fuel label must not be empty"):
        FireScenario(fuel="   ")
    with pytest.raises(ValueError, match="must not be negative"):
        FireScenario(oxygen_uncertainty=-0.01)


def test_forced_flow_requires_a_velocity() -> None:
    with pytest.raises(ValueError, match="needs a flow_velocity_m_s"):
        FireScenario(flow_mode="forced")
    assert FireScenario(flow_mode="forced", flow_velocity_m_s=0.1).flow_velocity_m_s == 0.1


def test_ignition_settings_are_preserved_in_the_scenario_notes() -> None:
    scenario = FireScenario(ignition_power_w=5.0, ignition_duration_s=2.0).to_scenario("demo")
    assert scenario.notes is not None
    assert "ignition power: 5 W" in scenario.notes
    assert "ignition duration: 2 s" in scenario.notes
    assert TEACHING_EXAMPLE in scenario.notes


def test_every_preset_is_marked_as_a_teaching_example_and_is_valid() -> None:
    assert PRESETS
    for name, preset in PRESETS.items():
        assert preset.source_note == TEACHING_EXAMPLE, name
        assert preset.to_scenario("preset-check").conditions.gravity_g.value >= 0


def test_scenario_id_must_not_be_blank() -> None:
    with pytest.raises(ValueError, match="scenario_id must not be empty"):
        FireScenario().to_scenario("  ")


def test_with_changes_revalidates_rather_than_trusting_the_caller() -> None:
    base = FireScenario()
    assert base.with_changes(oxygen_fraction=0.18).oxygen_fraction == 0.18
    with pytest.raises(ValueError, match="between 0 and 1"):
        base.with_changes(oxygen_fraction=2.0)


def test_each_view_source_states_plainly_what_it_is() -> None:
    assert ViewSource.SCHEMATIC.headline == "Illustration only"
    assert "Nothing here was computed" in ViewSource.SCHEMATIC.explanation
    assert "not a flame solver" in ViewSource.LEARNING_MODEL.explanation
    assert "validation envelope" in ViewSource.SOLVER.explanation
    assert len({source.headline for source in ViewSource}) == len(ViewSource)


def test_timeline_maps_positions_to_frames_and_steps_with_wrapping() -> None:
    timeline = PlaybackTimeline((0.0, 1.0, 2.0, 3.0))
    assert timeline.frames == 4
    assert timeline.duration_s == 3.0
    assert timeline.index_at(1.4) == 1
    assert timeline.index_at(-5.0) == 0
    assert timeline.index_at(99.0) == 3
    assert timeline.step(3) == 0
    assert timeline.step(3, loop=False) == 3
    assert timeline.step(0, -1, loop=False) == 0


def test_a_timeline_needs_an_increasing_time_base() -> None:
    with pytest.raises(ValueError, match="at least two samples"):
        PlaybackTimeline((0.0,))
    with pytest.raises(ValueError, match="must increase strictly"):
        PlaybackTimeline((0.0, 1.0, 1.0))
