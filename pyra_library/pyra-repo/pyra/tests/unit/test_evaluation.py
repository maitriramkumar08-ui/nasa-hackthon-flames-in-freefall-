"""Benchmark evaluator contracts."""

import pytest

from pyrakit.compare import evaluate_model
from pyrakit.provenance import Quantity, Status

SRC = "doi:10.0000/example|synthetic"


def q(value: float, u: float = 0.1) -> Quantity:
    return Quantity.measured(value, "kW", u, "type_b", source_ref=SRC)


def test_evaluation_score_is_explicit_and_source_aware() -> None:
    result = evaluate_model(
        [q(10), q(20), q(30)], [q(10.1), q(22), q(40)], tolerance=1.0, source_ids=["a", "b", "a"]
    )
    assert result.score == pytest.approx(100 / 3)
    assert result.passed_cases == 1
    assert result.independent_sources == 2
    assert result.status is Status.INTERPRETATION
    assert "universal" not in " ".join(result.caveats)


def test_evaluation_requires_an_explicit_tolerance() -> None:
    with pytest.raises(ValueError):
        evaluate_model([q(1)], [q(1)], tolerance=0)
