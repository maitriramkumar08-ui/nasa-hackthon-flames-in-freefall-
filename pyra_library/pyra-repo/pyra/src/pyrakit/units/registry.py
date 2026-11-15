"""Shared Pint registry and dimensionality checks used by PYRA schemas."""

from __future__ import annotations

from typing import Any

import pint

ureg = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)
Q_ = ureg.Quantity

# ``g0`` is Pint's named standard-gravity unit.  It is intentionally a unit,
# rather than a numeric value, so residual microgravity is represented as a
# measured multiple of g0 and is never silently replaced by exact zero.
try:
    ureg.Unit("g0")
except pint.errors.UndefinedUnitError:
    ureg.define("g0 = standard_gravity")

try:
    ureg.Unit("mole_fraction")
except pint.errors.UndefinedUnitError:
    ureg.define("mole_fraction = []")


def unit(unit_name: str) -> pint.Unit:
    """Return a parsed unit, raising ``ValueError`` with a useful message."""
    if not isinstance(unit_name, str) or not unit_name.strip():
        raise ValueError("unit must be a non-empty string")
    try:
        return ureg.Unit(unit_name)
    except (pint.errors.UndefinedUnitError, pint.errors.PintError) as exc:
        raise ValueError(f"unknown unit: {unit_name!r}") from exc


def quantity(value: Any, unit_name: str) -> pint.Quantity:
    """Construct a quantity through the shared registry."""
    return Q_(value, unit(unit_name))


def require_compatible(unit_name: str, expected: str) -> None:
    """Require two unit expressions to have compatible dimensionality."""
    actual = unit(unit_name)
    target = unit(expected)
    if actual.dimensionality != target.dimensionality:
        raise ValueError(
            f"unit {unit_name!r} is not compatible with {expected!r} "
            f"({actual.dimensionality} != {target.dimensionality})"
        )


__all__ = ["Q_", "quantity", "require_compatible", "unit", "ureg"]
