"""P2 Pint registry contracts."""

import pytest

from pyrakit.units import quantity, require_compatible, unit


def test_domain_units_parse() -> None:
    assert str(unit("kPa")) == "kilopascal"
    assert quantity(2, "cm/s").to("m/s").magnitude == 0.02


def test_dimension_mismatch_fails() -> None:
    with pytest.raises(ValueError, match="not compatible"):
        require_compatible("second", "meter")
