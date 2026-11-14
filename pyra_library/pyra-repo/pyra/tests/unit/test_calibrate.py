"""Small UQ resampling utility contracts."""

import pytest

from pyra.uq import bootstrap_mean


def test_bootstrap_mean_is_seeded_and_bounded() -> None:
    first = bootstrap_mean([1, 2, 3, 4], n_resamples=200, seed=4)
    second = bootstrap_mean([1, 2, 3, 4], n_resamples=200, seed=4)
    assert first == second
    assert first.estimate == 2.5
    assert first.lower <= first.estimate <= first.upper


def test_bootstrap_rejects_nonfinite_values() -> None:
    with pytest.raises(ValueError):
        bootstrap_mean([1, float("nan")])
