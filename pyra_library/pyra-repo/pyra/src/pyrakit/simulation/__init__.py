"""The contract between PYRA and an external simulation engine.

:class:`SimulationOutput` is what every adapter returns, whatever the engine underneath
looks like. Keeping one shape here is what lets the Playground label a view as real solver
output rather than illustration, and lets ``pyrakit.compare`` line a run up against an
experiment without guessing at units or time bases.
"""

from pyrakit.simulation.result import Channel, FlameFront, MeshInfo, SimulationOutput

__all__ = ["Channel", "FlameFront", "MeshInfo", "SimulationOutput"]
