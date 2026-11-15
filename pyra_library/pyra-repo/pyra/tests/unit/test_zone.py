import pytest

from pyrakit.physics.zone import simulate_zone


def test_zone_no_exchange_has_linear_source_solution() -> None:
    trace = simulate_zone(
        initial_concentration=0.2,
        exchange_rate_per_s=0,
        source_rate_per_s=0.01,
        duration_s=10,
        steps=3,
    )
    assert trace.concentration == pytest.approx((0.2, 0.25, 0.3))
    assert trace.status == "SIMULATED"


def test_zone_rejects_out_of_range_concentration() -> None:
    with pytest.raises(ValueError, match=r"valid \[0, 1\]"):
        simulate_zone(initial_concentration=0.9, source_rate_per_s=0.1, duration_s=2)


def test_zone_requires_at_least_two_steps() -> None:
    with pytest.raises(ValueError, match="steps >= 2"):
        simulate_zone(steps=1)
