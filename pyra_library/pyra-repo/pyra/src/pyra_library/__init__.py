"""Beginner-friendly import surface for the PYRA library.

Start with ``import pyra_library as pk`` and use the short helpers. Advanced
users can continue importing the full PYRA modules from ``pyra``.
"""

from __future__ import annotations

from pathlib import Path


def _shadowing_hint() -> str:
    """Explain the common cause when ``pyra`` resolves to the wrong package.

    Python puts the current directory ahead of installed packages on ``sys.path``.
    A local folder named ``pyra`` therefore wins over the installed library, and the
    resulting ImportError names a missing attribute rather than the real cause.
    """
    import pyra

    found = getattr(pyra, "__file__", None)
    location = str(Path(found).parent) if found else "an unknown location"
    return (
        f"'import pyra' resolved to {location}, which is not the PYRA library.\n"
        "A directory named 'pyra' in your current working directory shadows the "
        "installed library, because Python searches the current directory first.\n"
        "Run your script from a different directory, or start Python with -I "
        "(isolated mode) so the current directory is not searched."
    )


try:
    import pyra as advanced
    from pyra import (
        FireScenario,
        FireTestRun,
        compare_values,
        fire_playground,
        heat_release,
        measured,
        run_fire_test,
        scenario,
        show_simulation,
        simulate_decay,
        simulate_fire_scenario,
        simulate_zone,
    )
except ImportError as error:  # pragma: no cover - exercised in a subprocess test
    raise ImportError(f"{error}\n\n{_shadowing_hint()}") from error

__version__ = advanced.__version__

# Friendly short forms for common first steps.
playground = fire_playground
compare = compare_values

__all__ = [
    "FireScenario",
    "FireTestRun",
    "advanced",
    "compare",
    "compare_values",
    "fire_playground",
    "heat_release",
    "measured",
    "playground",
    "scenario",
    "run_fire_test",
    "show_simulation",
    "simulate_decay",
    "simulate_fire_scenario",
    "simulate_zone",
]
