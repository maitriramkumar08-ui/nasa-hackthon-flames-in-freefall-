import pytest

from pyrakit import FireScenario, run_fire_test, simulate_fire_scenario


def test_playground_scenario_outputs_oxygen_trace_and_keeps_scope_explicit() -> None:
    scenario = FireScenario(
        gravity_g=0.00001,
        oxygen_fraction=0.21,
        air_exchange_per_s=0.02,
        oxygen_sink_per_s=0.001,
    )
    result = simulate_fire_scenario(scenario)
    assert result.status == "SIMULATED"
    assert result.concentration[-1] < result.concentration[0]
    assert "well-mixed single zone" in result.assumptions


def test_playground_validates_environment_and_fuel() -> None:
    with pytest.raises(ValueError, match="pressure and temperature"):
        simulate_fire_scenario(FireScenario(pressure_kpa=0))
    with pytest.raises(ValueError, match="fuel label"):
        simulate_fire_scenario(FireScenario(fuel=" "))


def test_run_fire_test_returns_trace_and_plain_summary() -> None:
    run = run_fire_test(fuel="PMMA", gravity_g=0.0, duration_s=5)
    assert run.status == "SIMULATED"
    assert "PMMA" in run.summary()
    assert "not a flame solver" in run.summary()
