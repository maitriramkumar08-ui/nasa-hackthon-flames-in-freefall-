"""PYRA: Predictive Hazard & Reliability Atlas for spacecraft fire safety evidence.

The most-used names are importable straight from the top level::

    from pyra import Quantity, Status, Ledger, LedgerEntry, LineageGraph

Everything else lives in the sub-packages (see the API reference in ``docs/api.md``).
Only dependency-free modules are imported here, so ``import pyra`` stays fast.
"""

from pyra.provenance import (
    Ledger,
    LedgerEntry,
    LineageGraph,
    Provenance,
    Quantity,
    Status,
    join,
    sha256_hex,
)
from pyra.service.simple import heat_release, measured, scenario, show_simulation, simulate_decay
from pyra.physics.zone import simulate_zone

__version__ = "0.0.0"

__all__ = [
    "Ledger",
    "LedgerEntry",
    "LineageGraph",
    "Provenance",
    "Quantity",
    "Status",
    "__version__",
    "join",
    "heat_release",
    "measured",
    "scenario",
    "show_simulation",
    "simulate_decay",
    "simulate_zone",
    "sha256_hex",
]
