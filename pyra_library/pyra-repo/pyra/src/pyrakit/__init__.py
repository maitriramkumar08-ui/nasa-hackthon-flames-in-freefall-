"""PYRA: Predictive Hazard & Reliability Atlas for spacecraft fire safety evidence.

The most-used names are importable straight from the top level::

    from pyrakit import Quantity, Status, Ledger, LedgerEntry, LineageGraph

Everything else lives in the sub-packages (see the API reference in ``docs/api.md``).
Only dependency-free modules are imported here, so ``import pyrakit`` stays fast.
"""

from pyrakit.physics.zone import simulate_zone
from pyrakit.provenance import (
    Ledger,
    LedgerEntry,
    LineageGraph,
    Provenance,
    Quantity,
    Status,
    join,
    sha256_hex,
)
from pyrakit.service.fire_visualization import show_fire_simulation
from pyrakit.service.playground import (
    FireScenario,
    FireTestRun,
    PlaybackTimeline,
    ViewSource,
    fire_playground,
    run_fire_test,
    simulate_fire_scenario,
)
from pyrakit.service.simple import (
    compare_values,
    heat_release,
    measured,
    scenario,
    show_simulation,
    simulate_decay,
)

__version__ = "0.0.0"

# Friendly short form for a first program. `compare` is deliberately NOT aliased:
# `pyrakit.compare` is the advanced comparison subpackage, and the quick scalar
# helper keeps its explicit name `compare_values`.
playground = fire_playground

__all__ = [
    "Ledger",
    "LedgerEntry",
    "LineageGraph",
    "FireScenario",
    "FireTestRun",
    "PlaybackTimeline",
    "Provenance",
    "Quantity",
    "Status",
    "ViewSource",
    "__version__",
    "join",
    "compare_values",
    "fire_playground",
    "playground",
    "run_fire_test",
    "heat_release",
    "measured",
    "scenario",
    "show_fire_simulation",
    "show_simulation",
    "simulate_decay",
    "simulate_zone",
    "simulate_fire_scenario",
    "sha256_hex",
]
