"""Beginner-facing convenience API tests."""

from pyrakit import compare_values, heat_release, simulate_decay


def test_simple_heat_release_keeps_derived_status() -> None:
    result = heat_release(
        0.21,
        0.20,
        0.01,
        13_100_000,
        source_ref="doi:10.0000/example|synthetic",
        n=128,
        seed=1,
    )
    assert result.status.name == "DERIVED"
    assert round(result.value) == 1310


def test_toy_simulation_is_deterministic() -> None:
    points = simulate_decay(1.0, 0.5, 4.0, steps=5)
    assert points[0] == (0.0, 1.0)
    assert points[-1][0] == 4.0
    assert points[-1][1] < points[0][1]


def test_quick_comparison_is_plain_and_tolerance_based() -> None:
    result = compare_values(100, 104, unit="W", tolerance=5)
    assert result.difference == 4
    assert result.within_tolerance
    assert result.relative_difference_percent == 4
    assert result.status == "INTERPRETATION"


def test_quick_comparison_rejects_negative_tolerance() -> None:
    import pytest

    with pytest.raises(ValueError, match="non-negative"):
        compare_values(1, 2, unit="W", tolerance=-1)
