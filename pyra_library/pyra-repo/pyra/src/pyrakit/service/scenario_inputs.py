"""The beginner-facing scenario form, and its bridge to PYRA's validated schema.

:class:`FireScenario` is deliberately plain: flat fields, plain floats, SI-ish units named
in the field name, so a first program can be written without reading the schema layer. It
is a form, not evidence.

:meth:`FireScenario.to_scenario` converts that form into a real
:class:`~pyrakit.schema.Scenario`, where every physical input carries a unit and, where the
learner knows it, an uncertainty. That conversion is the seam an external engine is driven
through: the Playground collects plain numbers, the schema validates them, and the adapter
sends the validated scenario onward.

Nothing here simulates anything, and nothing here is a physical claim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum

from pyrakit.schema import Conditions, FuelSpec, Measure, Scenario

TEACHING_EXAMPLE = "teaching example; not taken from a cited experiment"


class ViewSource(Enum):
    """Where a thing shown on screen actually came from.

    Every view in the Playground is tagged with one of these, because the three are not
    interchangeable and a learner cannot tell them apart by looking.
    """

    SCHEMATIC = "schematic"
    LEARNING_MODEL = "learning model"
    SOLVER = "solver output"

    @property
    def headline(self) -> str:
        return {
            ViewSource.SCHEMATIC: "Illustration only",
            ViewSource.LEARNING_MODEL: "Simplified learning model",
            ViewSource.SOLVER: "External solver output",
        }[self]

    @property
    def explanation(self) -> str:
        return {
            ViewSource.SCHEMATIC: (
                "A drawing. Nothing here was computed, and the shape does not respond to "
                "any setting you change."
            ),
            ViewSource.LEARNING_MODEL: (
                "Computed by PYRA's well-mixed oxygen balance. Only starting oxygen, air "
                "exchange, oxygen sink rate and duration affect it. Fuel, gravity, "
                "pressure and temperature are recorded but do not enter this equation. "
                "It is not a flame solver and not a safety prediction."
            ),
            ViewSource.SOLVER: (
                "Produced by an external simulation engine through a PYRA adapter. Its "
                "trustworthiness depends on that engine's model card, and on whether this "
                "scenario falls inside the engine's recorded validation envelope."
            ),
        }[self]


@dataclass(frozen=True)
class FireScenario:
    """One stationary-fire scenario as a learner enters it.

    Units live in the field names. ``gravity_g`` is a multiple of Earth gravity, so 1.0 is
    a laboratory bench and 1e-5 is the residual acceleration of an orbiting vehicle;
    microgravity is a small residual, never exactly zero. ``oxygen_fraction`` is a mole
    fraction between 0 and 1, where 0.21 is ordinary air.

    The ``*_uncertainty`` fields are optional standard uncertainties. Leaving one at
    ``None`` records "not known", which is honest; it does not mean zero.

    ``air_exchange_per_s`` and ``oxygen_sink_per_s`` belong to the simplified learning
    model only. An external solver receives the physical conditions instead.
    """

    fuel: str = "PMMA (example fuel)"
    gravity_g: float = 1.0
    oxygen_fraction: float = 0.21
    pressure_kpa: float = 101.3
    temperature_k: float = 293.15

    # Learning-model knobs; not sent to a solver.
    air_exchange_per_s: float = 0.02
    oxygen_sink_per_s: float = 0.001
    duration_s: float = 60.0

    # Flow and geometry, needed by any real flame solver.
    diluent: str = "nitrogen"
    flow_mode: str = "quiescent"
    flow_velocity_m_s: float | None = None
    configuration: str = "concurrent"
    length_scale_m: float = 0.02
    fuel_thickness_m: float | None = None
    fuel_width_m: float | None = None

    # Ignition, recorded so a run can be reproduced.
    ignition_power_w: float | None = None
    ignition_duration_s: float | None = None

    # Known uncertainties, where the learner has them.
    oxygen_uncertainty: float | None = None
    pressure_uncertainty_kpa: float | None = None
    temperature_uncertainty_k: float | None = None

    source_note: str = TEACHING_EXAMPLE

    def __post_init__(self) -> None:
        if not self.fuel.strip():
            raise ValueError("fuel label must not be empty")
        if not self.diluent.strip():
            raise ValueError("diluent must not be empty")

        required = {
            "gravity_g": self.gravity_g,
            "oxygen_fraction": self.oxygen_fraction,
            "pressure_kpa": self.pressure_kpa,
            "temperature_k": self.temperature_k,
            "air_exchange_per_s": self.air_exchange_per_s,
            "oxygen_sink_per_s": self.oxygen_sink_per_s,
            "duration_s": self.duration_s,
            "length_scale_m": self.length_scale_m,
        }
        for name, value in required.items():
            if not isinstance(value, int | float) or isinstance(value, bool):
                raise ValueError(f"{name} must be a number")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be a finite number")

        optional = {
            "flow_velocity_m_s": self.flow_velocity_m_s,
            "fuel_thickness_m": self.fuel_thickness_m,
            "fuel_width_m": self.fuel_width_m,
            "ignition_power_w": self.ignition_power_w,
            "ignition_duration_s": self.ignition_duration_s,
            "oxygen_uncertainty": self.oxygen_uncertainty,
            "pressure_uncertainty_kpa": self.pressure_uncertainty_kpa,
            "temperature_uncertainty_k": self.temperature_uncertainty_k,
        }
        for name, maybe in optional.items():
            if maybe is None:
                continue
            if not isinstance(maybe, int | float) or isinstance(maybe, bool):
                raise ValueError(f"{name} must be a number or None")
            if not math.isfinite(float(maybe)):
                raise ValueError(f"{name} must be finite when given")
            if maybe < 0:
                raise ValueError(f"{name} must not be negative")

        if self.gravity_g < 0:
            raise ValueError("gravity_g must be non-negative; microgravity is a small residual")
        if not 0 <= self.oxygen_fraction <= 1:
            raise ValueError("oxygen_fraction is a mole fraction and must be between 0 and 1")
        if self.pressure_kpa <= 0 or self.temperature_k <= 0:
            raise ValueError("pressure and temperature must be positive")
        if self.air_exchange_per_s < 0 or self.oxygen_sink_per_s < 0:
            raise ValueError("air exchange and oxygen sink rates must be non-negative")
        if self.duration_s <= 0:
            raise ValueError("duration_s must be positive")
        if self.length_scale_m <= 0:
            raise ValueError("length_scale_m must be positive")
        if self.flow_mode == "forced" and not self.flow_velocity_m_s:
            raise ValueError("flow_mode 'forced' needs a flow_velocity_m_s above zero")

    def with_changes(self, **changes: object) -> FireScenario:
        """Return a copy with some fields replaced, re-running every check."""
        return replace(self, **changes)  # type: ignore[arg-type]

    def _measure(self, value: float, unit: str, uncertainty: float | None) -> Measure:
        if uncertainty is None:
            return Measure(value=value, unit=unit)
        return Measure(value=value, unit=unit, u=uncertainty, u_kind="type_b")

    def to_conditions(self) -> Conditions:
        """Build the validated, unit-bearing conditions this form describes."""
        fuel = FuelSpec(
            material=self.fuel,
            thickness=(
                None
                if self.fuel_thickness_m is None
                else Measure(value=self.fuel_thickness_m, unit="m")
            ),
            width=(
                None if self.fuel_width_m is None else Measure(value=self.fuel_width_m, unit="m")
            ),
        )
        return Conditions(
            gravity_g=Measure(value=self.gravity_g, unit="dimensionless"),
            pressure=self._measure(self.pressure_kpa, "kPa", self.pressure_uncertainty_kpa),
            o2_mole_fraction=self._measure(
                self.oxygen_fraction, "dimensionless", self.oxygen_uncertainty
            ),
            diluent=self.diluent,
            flow_velocity=(
                None
                if self.flow_velocity_m_s is None
                else Measure(value=self.flow_velocity_m_s, unit="m/s")
            ),
            flow_mode=self.flow_mode,  # type: ignore[arg-type]
            temperature=self._measure(self.temperature_k, "K", self.temperature_uncertainty_k),
            fuel=fuel,
            configuration=self.configuration,  # type: ignore[arg-type]
            length_scale=Measure(value=self.length_scale_m, unit="m"),
        )

    def to_scenario(self, scenario_id: str, *, purpose: str = "exploration") -> Scenario:
        """Turn this form into a validated scenario an adapter can send to an engine.

        The ignition settings and the source note travel in ``notes``, so a saved run still
        says how it was set up even though the condition schema has no field for them.
        """
        if not scenario_id.strip():
            raise ValueError("scenario_id must not be empty")
        notes = [f"source: {self.source_note}"]
        if self.ignition_power_w is not None:
            notes.append(f"ignition power: {self.ignition_power_w:g} W")
        if self.ignition_duration_s is not None:
            notes.append(f"ignition duration: {self.ignition_duration_s:g} s")
        return Scenario(
            scenario_id=scenario_id,
            conditions=self.to_conditions(),
            purpose=purpose,
            notes="; ".join(notes),
        )


PRESETS: dict[str, FireScenario] = {
    "Earth lab example": FireScenario(),
    "Microgravity thought experiment": FireScenario(gravity_g=0.00001),
    "Low-oxygen thought experiment": FireScenario(oxygen_fraction=0.17),
    "Forced-flow thought experiment": FireScenario(
        flow_mode="forced", flow_velocity_m_s=0.1, configuration="concurrent"
    ),
}

__all__ = ["PRESETS", "TEACHING_EXAMPLE", "FireScenario", "ViewSource"]
