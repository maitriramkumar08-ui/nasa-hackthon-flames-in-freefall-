"""Experiment records and source references."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pyrakit.schema.conditions import Conditions, Measure


class SourceRef(BaseModel):
    """Stable pointer to the evidence used for a measured record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str = Field(min_length=1)
    uri: str | None = None
    file_sha256: str | None = None
    locator: str | None = None


class ExperimentRecord(BaseModel):
    """A schema-validated experiment metadata record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    experiment_id: str = Field(min_length=1)
    investigation: str = Field(min_length=1)
    source: SourceRef
    conditions: Conditions
    measurements: dict[str, Measure] = Field(default_factory=dict)
    platform: str | None = None
    notes: str | None = None
