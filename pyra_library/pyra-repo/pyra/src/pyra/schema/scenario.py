"""User-specified scenario metadata."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from pyra.schema.conditions import Conditions


class Scenario(BaseModel):
    """A hypothetical or proposed set of fire conditions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    scenario_id: str = Field(min_length=1)
    conditions: Conditions
    purpose: str | None = None
    notes: str | None = None
