"""P5 matching contracts."""

from pyra.matching import MatchPolicy, match_conditions, pareto_front
from pyra.schema import Conditions, FuelSpec, Measure


def conditions(*, configuration="concurrent", gravity=1e-5, fuel="PMMA") -> Conditions:
    return Conditions(
        gravity_g=Measure(value=gravity, unit="dimensionless", u=1e-6, u_kind="type_a"),
        pressure=Measure(value=101, unit="kPa", u=0.1, u_kind="type_b"),
        o2_mole_fraction=Measure(value=0.21, unit="dimensionless", u=0.001, u_kind="type_b"),
        diluent="nitrogen",
        flow_velocity=Measure(value=0.02, unit="m/s", u=0.001, u_kind="type_b"),
        flow_mode="forced",
        fuel=FuelSpec(material=fuel),
        configuration=configuration,
        length_scale=Measure(value=0.02, unit="m", u=0.001, u_kind="type_b"),
    )


def test_matching_retains_dimensions_and_exact_tier() -> None:
    result = match_conditions(conditions(), conditions(), MatchPolicy())
    assert result.tier == "EXACT"
    assert set(result.dimensions) == {
        "gravity_g",
        "pressure",
        "o2_mole_fraction",
        "flow_velocity",
        "length_scale",
    }
    assert result.aggregate == 0


def test_hard_gates_block_different_configurations_and_fuels() -> None:
    result = match_conditions(
        conditions(), conditions(configuration="opposed", fuel="cotton"), MatchPolicy()
    )
    assert result.tier == "NONE"
    assert set(result.blocked_by) == {"configuration", "fuel"}


def test_gravity_floor_keeps_small_values_finite() -> None:
    result = match_conditions(conditions(gravity=1e-5), conditions(gravity=1e-3), MatchPolicy())
    assert result.dimensions["gravity_g"] < float("inf")


def test_pareto_front_does_not_collapse_the_vector() -> None:
    policy = MatchPolicy()
    a = match_conditions(conditions(), conditions(gravity=1e-5, fuel="PMMA"), policy)
    b = match_conditions(conditions(), conditions(gravity=1e-5, configuration="concurrent"), policy)
    assert pareto_front([a, b]) == [0, 1]
