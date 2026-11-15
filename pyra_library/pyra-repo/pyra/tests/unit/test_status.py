"""P1: Status ordering and join (architecture section 3)."""

import itertools

import pytest

from pyrakit.provenance.status import Status, StatusInputError, enforce_max_input_status, join

ALL = list(Status)


def test_order_is_distance_from_observation() -> None:
    assert [s.name for s in sorted(Status)] == [
        "MEASURED", "DERIVED", "SIMULATED", "SCENARIO", "INTERPRETATION",
    ]


def test_join_is_monotone() -> None:
    for a, b in itertools.product(ALL, ALL):
        assert join(a, b) >= a
        assert join(a, b) >= b


def test_join_is_associative_commutative_idempotent() -> None:
    for a, b, c in itertools.product(ALL, ALL, ALL):
        assert join(join(a, b), c) == join(a, join(b, c))
        assert join(a, b) == join(b, a)
    for a in ALL:
        assert join(a, a) == a


def test_join_returns_a_status_not_an_int() -> None:
    assert type(join(Status.MEASURED, Status.SCENARIO)) is Status


def test_scenario_poisons_measured() -> None:
    assert join(Status.MEASURED, Status.SCENARIO) is Status.SCENARIO


def test_join_rejects_empty_and_plain_ints() -> None:
    with pytest.raises(ValueError):
        join()
    with pytest.raises(TypeError):
        join(Status.MEASURED, 2)  # type: ignore[arg-type]


def test_enforce_max_input_status() -> None:
    enforce_max_input_status([Status.MEASURED, Status.DERIVED], Status.DERIVED, "hrr")
    with pytest.raises(StatusInputError, match="hrr"):
        enforce_max_input_status([Status.MEASURED, Status.SIMULATED], Status.DERIVED, "hrr")
