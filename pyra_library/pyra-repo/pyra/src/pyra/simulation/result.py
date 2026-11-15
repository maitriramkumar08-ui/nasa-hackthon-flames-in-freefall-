"""The shape PYRA expects a simulation engine's output to arrive in.

An engine is adapted, never trusted blindly. Whatever an engine writes is parsed into
a :class:`SimulationOutput`, which fixes the things a caller needs in order to label an
animation honestly and to compare the run against an experiment later: a time base in
seconds, every series tagged with a Pint-parsable unit, optional flame-front geometry,
the mesh the engine used, warnings the engine raised, and where its output files live.

Validation here is structural, not physical. It checks that series lengths match the time
base, that units parse and that time increases. It cannot tell whether the numbers are
right, and a SIMULATED status never becomes evidence on its own.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pyra.provenance import Quantity, Status
from pyra.units import quantity, unit


def _finite_tuple(values: Sequence[Any], label: str) -> tuple[float, ...]:
    out: list[float] = []
    for raw in values:
        if isinstance(raw, bool) or not isinstance(raw, int | float):
            raise ValueError(f"{label} must contain only numbers")
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError(f"{label} must contain only finite numbers")
        out.append(number)
    return tuple(out)


@dataclass(frozen=True)
class Channel:
    """One named time series produced by an engine.

    ``name`` is the key a caller looks it up by. ``unit`` is a Pint-parsable unit string,
    so an animation axis and a later comparison both read the same unit. ``long_name`` is
    the human label for a plot. ``uncertainty`` is the engine's own standard uncertainty
    per sample when it reports one; most engines do not, and ``None`` says so honestly
    rather than implying zero.
    """

    name: str
    unit: str
    values: tuple[float, ...]
    long_name: str = ""
    uncertainty: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("channel name must not be empty")
        unit(self.unit)
        object.__setattr__(self, "values", _finite_tuple(self.values, f"channel {self.name!r}"))
        if not self.values:
            raise ValueError(f"channel {self.name!r} has no samples")
        if self.uncertainty is not None:
            checked = _finite_tuple(self.uncertainty, f"channel {self.name!r} uncertainty")
            if len(checked) != len(self.values):
                raise ValueError(
                    f"channel {self.name!r} uncertainty has {len(checked)} samples "
                    f"but {len(self.values)} values"
                )
            if any(value < 0 for value in checked):
                raise ValueError(f"channel {self.name!r} uncertainty must be non-negative")
            object.__setattr__(self, "uncertainty", checked)

    @property
    def label(self) -> str:
        """The axis label for a plot: long name when given, otherwise the channel name."""
        return f"{self.long_name or self.name} [{self.unit}]"

    def converted_to(self, target: str) -> Channel:
        """Return this channel expressed in ``target``, raising if the units are unrelated."""
        factor_source = quantity(1.0, self.unit).to(target).magnitude
        return Channel(
            name=self.name,
            unit=target,
            values=tuple(value * factor_source for value in self.values),
            long_name=self.long_name,
            uncertainty=(
                None
                if self.uncertainty is None
                else tuple(value * abs(factor_source) for value in self.uncertainty)
            ),
        )

    def quantity_at(self, index: int, *, scenario_input: Quantity, activity: str) -> Quantity:
        """Lift one sample into a SIMULATED :class:`~pyra.provenance.Quantity`.

        The scenario quantity that drove the run is passed as the parent so the result
        carries its lineage, which is what lets the value enter ``pyra.compare`` without
        losing the fact that it came from a model rather than an instrument.
        """
        uncertainty = None if self.uncertainty is None else self.uncertainty[index]
        return Quantity.derive(
            self.values[index],
            self.unit,
            uncertainty,
            "unknown" if uncertainty is None else "type_b",
            parents=[scenario_input],
            activity=activity,
            method_status=Status.SIMULATED,
        )


@dataclass(frozen=True)
class FlameFront:
    """Flame-front geometry sampled on the same time base as the channels.

    ``position_m`` is the leading-edge position along the sample. ``length_m`` and
    ``area_m2`` are optional because not every engine reports them. All of these are
    engine output, never the schematic drawing the beginner Playground shows.
    """

    position_m: tuple[float, ...]
    length_m: tuple[float, ...] | None = None
    area_m2: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "position_m", _finite_tuple(self.position_m, "flame-front position")
        )
        if not self.position_m:
            raise ValueError("flame front has no samples")
        for name in ("length_m", "area_m2"):
            values = getattr(self, name)
            if values is None:
                continue
            checked = _finite_tuple(values, f"flame-front {name}")
            if len(checked) != len(self.position_m):
                raise ValueError(f"flame-front {name} length does not match position_m")
            if any(value < 0 for value in checked):
                raise ValueError(f"flame-front {name} must be non-negative")
            object.__setattr__(self, name, checked)


@dataclass(frozen=True)
class MeshInfo:
    """The spatial discretization an engine used, recorded so a run can be judged.

    A flame-resolved result from a coarse mesh deserves different weight from the same
    result on a fine one, so this travels with the output instead of being forgotten.
    """

    dimensions: int
    cell_count: int
    min_cell_size_m: float
    note: str = ""

    def __post_init__(self) -> None:
        if self.dimensions not in (1, 2, 3):
            raise ValueError("mesh dimensions must be 1, 2 or 3")
        if self.cell_count < 1:
            raise ValueError("mesh cell_count must be positive")
        if not math.isfinite(self.min_cell_size_m) or self.min_cell_size_m <= 0:
            raise ValueError("mesh min_cell_size_m must be a positive, finite length")


@dataclass(frozen=True)
class SimulationOutput:
    """One engine run: its identity, its time base, and everything it produced.

    ``model_card_id`` and ``engine_version`` are required because an output that cannot
    name the model that made it cannot be reproduced or checked against a validation
    envelope. ``artifacts`` maps a short name to a file the engine wrote, so large field
    data stays on disk instead of being copied into memory.
    """

    scenario_id: str
    model_card_id: str
    engine_version: str
    time_s: tuple[float, ...]
    channels: Mapping[str, Channel]
    status: Status = Status.SIMULATED
    flame_front: FlameFront | None = None
    mesh: MeshInfo | None = None
    warnings: tuple[str, ...] = ()
    artifacts: Mapping[str, str] = field(default_factory=dict)
    assumptions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("scenario_id", "model_card_id", "engine_version"):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must not be empty")
        object.__setattr__(self, "time_s", _finite_tuple(self.time_s, "time_s"))
        if len(self.time_s) < 2:
            raise ValueError("time_s needs at least two samples")
        pairs = zip(self.time_s, self.time_s[1:], strict=False)  # offset slices, so not strict
        if any(later <= earlier for earlier, later in pairs):
            raise ValueError("time_s must increase strictly")
        if not self.channels:
            raise ValueError("a simulation output needs at least one channel")
        for key, channel in self.channels.items():
            if key != channel.name:
                raise ValueError(f"channel key {key!r} does not match its name {channel.name!r}")
            if len(channel.values) != len(self.time_s):
                raise ValueError(
                    f"channel {key!r} has {len(channel.values)} samples "
                    f"but the time base has {len(self.time_s)}"
                )
        if self.flame_front is not None and len(self.flame_front.position_m) != len(self.time_s):
            raise ValueError("flame-front samples do not match the time base")
        object.__setattr__(self, "channels", dict(self.channels))
        object.__setattr__(self, "artifacts", dict(self.artifacts))

    @property
    def duration_s(self) -> float:
        return self.time_s[-1] - self.time_s[0]

    def channel(self, name: str) -> Channel:
        """Look one channel up, listing what is available when the name is wrong."""
        try:
            return self.channels[name]
        except KeyError:
            raise KeyError(f"no channel {name!r}; this run has {sorted(self.channels)}") from None

    def sample_at(self, time_s: float) -> int:
        """The index of the sample nearest ``time_s``, for scrubbing a playback timeline."""
        if not math.isfinite(time_s):
            raise ValueError("time_s must be finite")
        return min(range(len(self.time_s)), key=lambda index: abs(self.time_s[index] - time_s))

    def to_dict(self) -> dict[str, Any]:
        """A JSON-ready record of the run, including its limits and warnings."""
        return {
            "scenario_id": self.scenario_id,
            "model_card_id": self.model_card_id,
            "engine_version": self.engine_version,
            "status": self.status.name,
            "time_s": list(self.time_s),
            "channels": {
                name: {
                    "name": channel.name,
                    "unit": channel.unit,
                    "long_name": channel.long_name,
                    "values": list(channel.values),
                    "uncertainty": (
                        None if channel.uncertainty is None else list(channel.uncertainty)
                    ),
                }
                for name, channel in self.channels.items()
            },
            "flame_front": (
                None
                if self.flame_front is None
                else {
                    "position_m": list(self.flame_front.position_m),
                    "length_m": (
                        None
                        if self.flame_front.length_m is None
                        else list(self.flame_front.length_m)
                    ),
                    "area_m2": (
                        None if self.flame_front.area_m2 is None else list(self.flame_front.area_m2)
                    ),
                }
            ),
            "mesh": (
                None
                if self.mesh is None
                else {
                    "dimensions": self.mesh.dimensions,
                    "cell_count": self.mesh.cell_count,
                    "min_cell_size_m": self.mesh.min_cell_size_m,
                    "note": self.mesh.note,
                }
            ),
            "warnings": list(self.warnings),
            "artifacts": dict(self.artifacts),
            "assumptions": list(self.assumptions),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SimulationOutput:
        """Rebuild an output from :meth:`to_dict`, re-running every structural check.

        This is also the parser an adapter uses on an engine's own JSON, so a malformed
        engine result fails here with a specific message instead of halfway through a plot.
        """
        if not isinstance(payload, Mapping):
            raise ValueError("a simulation output must be a JSON object")
        missing = {
            "scenario_id",
            "model_card_id",
            "engine_version",
            "time_s",
            "channels",
        } - set(payload)
        if missing:
            raise ValueError(f"simulation output is missing required keys: {sorted(missing)}")

        raw_channels = payload["channels"]
        if not isinstance(raw_channels, Mapping):
            raise ValueError("'channels' must be a JSON object keyed by channel name")
        channels: dict[str, Channel] = {}
        for name, spec in raw_channels.items():
            if not isinstance(spec, Mapping):
                raise ValueError(f"channel {name!r} must be a JSON object")
            for required in ("unit", "values"):
                if required not in spec:
                    raise ValueError(f"channel {name!r} is missing {required!r}")
            channels[name] = Channel(
                name=str(spec.get("name", name)),
                unit=str(spec["unit"]),
                values=tuple(spec["values"]),
                long_name=str(spec.get("long_name", "")),
                uncertainty=(
                    None if spec.get("uncertainty") is None else tuple(spec["uncertainty"])
                ),
            )

        front = payload.get("flame_front")
        mesh = payload.get("mesh")
        status_name = str(payload.get("status", "SIMULATED"))
        try:
            status = Status[status_name]
        except KeyError:
            raise ValueError(f"unknown status {status_name!r} in simulation output") from None

        return cls(
            scenario_id=str(payload["scenario_id"]),
            model_card_id=str(payload["model_card_id"]),
            engine_version=str(payload["engine_version"]),
            time_s=tuple(payload["time_s"]),
            channels=channels,
            status=status,
            flame_front=(
                None
                if front is None
                else FlameFront(
                    position_m=tuple(front["position_m"]),
                    length_m=(None if front.get("length_m") is None else tuple(front["length_m"])),
                    area_m2=(None if front.get("area_m2") is None else tuple(front["area_m2"])),
                )
            ),
            mesh=(
                None
                if mesh is None
                else MeshInfo(
                    dimensions=int(mesh["dimensions"]),
                    cell_count=int(mesh["cell_count"]),
                    min_cell_size_m=float(mesh["min_cell_size_m"]),
                    note=str(mesh.get("note", "")),
                )
            ),
            warnings=tuple(str(item) for item in payload.get("warnings", ())),
            artifacts={str(k): str(v) for k, v in dict(payload.get("artifacts", {})).items()},
            assumptions=tuple(str(item) for item in payload.get("assumptions", ())),
        )

    def save(self, path: str | Path) -> Path:
        """Write the run to JSON so it can be replayed and compared later."""
        destination = Path(path)
        destination.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return destination

    @classmethod
    def load(cls, path: str | Path) -> SimulationOutput:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


__all__ = ["Channel", "FlameFront", "MeshInfo", "SimulationOutput"]
