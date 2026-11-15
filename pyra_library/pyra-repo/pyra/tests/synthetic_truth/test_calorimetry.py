"""Synthetic truth checks for the S0 calorimetry transforms."""

from pyrakit.physics.calorimetry import (
    hrr_enthalpy_balance,
    hrr_oxygen_consumption,
    species_generation,
)
from pyrakit.provenance import Quantity

SRC = "doi:10.0000/example|file-sha256:00|synthetic"


def measured(value: float, unit: str, u: float) -> Quantity:
    return Quantity.measured(value, unit, u, "type_b", source_ref=SRC)


def test_oxygen_consumption_recovers_known_source_term() -> None:
    result = hrr_oxygen_consumption(
        measured(0.21, "dimensionless", 1e-6),
        measured(0.20, "dimensionless", 1e-6),
        measured(0.01, "kg/s", 1e-6),
        measured(13_100_000, "J/kg", 100),
        n=1024,
        seed=7,
    )
    assert result.status.name == "DERIVED"
    assert abs(result.value - 1310) < 3
    assert result.u is not None and result.u > 0


def test_oxygen_consumption_is_reproducible_for_a_seed() -> None:
    args = (
        measured(0.21, "dimensionless", 1e-4),
        measured(0.20, "dimensionless", 1e-4),
        measured(0.01, "kg/s", 1e-5),
        measured(13_100_000, "J/kg", 100),
    )
    a = hrr_oxygen_consumption(*args, n=256, seed=3)
    b = hrr_oxygen_consumption(*args, n=256, seed=3)
    assert a.value == b.value
    assert a.u == b.u


def test_enthalpy_balance_and_species_generation() -> None:
    hrr = hrr_enthalpy_balance(
        measured(300, "K", 0.1), measured(400, "K", 0.1),
        measured(0.02, "kg/s", 1e-4), measured(1000, "J/kg/K", 1),
    )
    source = species_generation(
        measured(0.1, "dimensionless", 0.001),
        measured(0.2, "dimensionless", 0.001),
        measured(0.02, "kg/s", 1e-4),
    )
    assert hrr.value == 2000
    assert source.value == 0.002
