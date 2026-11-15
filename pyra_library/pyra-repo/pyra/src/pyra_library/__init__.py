"""Beginner-friendly import surface for the PYRA library.

Start with ``import pyra_library as pk`` and use the short helpers. Advanced
users can continue importing the full PYRA modules from ``pyra``.
"""

from __future__ import annotations

import pyra as advanced
from pyra import (
    FireScenario,
    compare_values,
    fire_playground,
    heat_release,
    measured,
    scenario,
    show_simulation,
    simulate_decay,
    simulate_fire_scenario,
    simulate_zone,
)

__version__ = advanced.__version__

# Friendly short forms for common first steps.
playground = fire_playground
compare = compare_values

__all__ = [
    "FireScenario",
    "advanced",
    "compare",
    "compare_values",
    "fire_playground",
    "heat_release",
    "measured",
    "playground",
    "scenario",
    "show_simulation",
    "simulate_decay",
    "simulate_fire_scenario",
    "simulate_zone",
]
