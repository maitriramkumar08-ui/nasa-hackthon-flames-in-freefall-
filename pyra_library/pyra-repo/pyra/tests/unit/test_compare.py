"""P7 comparison contracts."""

import pytest

from pyrakit.compare import bias, first_order_lag, relative_difference, z_score
from pyrakit.provenance import Quantity

SRC = "doi:10.0000/example|synthetic"


def measured(value: float, uncertainty: float) -> Quantity:
    return Quantity.measured(value, "kW", uncertainty, "type_b", source_ref=SRC)


def test_lag_operator_has_closed_form_first_step() -> None:
    trace = first_order_lag((0.0, 1.0, 1.0), dt=1.0, tau=1.0)
    assert trace[0] == 0.0
    assert trace[1] == pytest.approx(1 - 2.718281828459045**-1)
    assert trace[2] > trace[1]


def test_metrics_keep_units_and_uncertainty() -> None:
    observed, simulated = measured(10, 0.5), measured(12, 0.4)
    assert bias(observed, simulated).value == 2
    assert relative_difference(observed, simulated).value == 0.2
    assert z_score(observed, simulated).value == pytest.approx(2 / 0.6403124237)


def test_relative_difference_rejects_zero_baseline() -> None:
    with pytest.raises(ZeroDivisionError):
        relative_difference(measured(0, 0.1), measured(1, 0.1))
