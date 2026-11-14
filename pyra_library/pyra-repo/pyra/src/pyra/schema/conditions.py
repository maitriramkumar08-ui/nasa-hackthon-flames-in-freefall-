"""Pydantic condition models and the unit-bearing schema measure."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from pyra.units import require_compatible, unit

UKind = Literal["type_a", "type_b", "assumed", "unknown"]
FlowMode = Literal["quiescent", "forced", "buoyant", "unknown"]
Configuration = Literal["concurrent", "opposed", "droplet", "jet", "enclosed", "other"]


class Measure(BaseModel):
    """A scalar value with a Pint-parsable unit and explicit uncertainty."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: float
    unit: str
    u: float | None = Field(default=None, ge=0)
    u_kind: UKind = "unknown"

    @field_validator("unit")
    @classmethod
    def _unit_exists(cls, value: str) -> str:
        unit(value)
        return value

    @model_validator(mode="after")
    def _uncertainty_pair(self) -> Measure:
        if (self.u is None) != (self.u_kind == "unknown"):
            raise ValueError("u is None exactly when u_kind is 'unknown'")
        return self

    def compatible_with(self, expected: str) -> Measure:
        require_compatible(self.unit, expected)
        return self


class FuelSpec(BaseModel):
    """Material and geometry metadata for a tested fuel sample."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    material: str = Field(min_length=1)
    thickness: Measure | None = None
    width: Measure | None = None
    length: Measure | None = None
    density: Measure | None = None
    treatment: str | None = None

    @model_validator(mode="after")
    def _dimensions(self) -> FuelSpec:
        for name in ("thickness", "width", "length"):
            value = getattr(self, name)
            if value is not None:
                value.compatible_with("meter")
        if self.density is not None:
            self.density.compatible_with("kg / meter ** 3")
        return self


class Conditions(BaseModel):
    """Experimental or scenario conditions used for matching and reporting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gravity_g: Measure
    pressure: Measure
    o2_mole_fraction: Measure
    diluent: str = Field(min_length=1)
    flow_velocity: Measure | None = None
    flow_mode: FlowMode = "unknown"
    temperature: Measure | None = None
    fuel: FuelSpec
    configuration: Configuration
    length_scale: Measure

    @model_validator(mode="after")
    def _validate_dimensions(self) -> Conditions:
        self.gravity_g.compatible_with("dimensionless")
        self.pressure.compatible_with("pascal")
        self.o2_mole_fraction.compatible_with("dimensionless")
        if not 0 <= self.o2_mole_fraction.value <= 1:
            raise ValueError("o2_mole_fraction must be between 0 and 1")
        if self.gravity_g.value < 0:
            raise ValueError("gravity_g must be non-negative; microgravity is a residual, not zero")
        if self.flow_velocity is not None:
            self.flow_velocity.compatible_with("meter / second")
        if self.temperature is not None:
            self.temperature.compatible_with("kelvin")
        self.length_scale.compatible_with("meter")
        return self
