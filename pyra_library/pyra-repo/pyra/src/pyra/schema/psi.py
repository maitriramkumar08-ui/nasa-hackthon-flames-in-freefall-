"""PSI investigation condition records that preserve source values without guessing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pyra.schema.conditions import Conditions


class PSIConditionRecord(BaseModel):
    """Raw PSI condition fields plus optional reviewed, normalized common conditions.

    Raw fields retain their original labels and text. Normalized conditions are optional
    because a PSI field should only be mapped after its units and meaning are verified.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    investigation_id: str = Field(pattern=r"^PSI-[0-9]+$")
    source_id: str = Field(min_length=1)
    source_uri: str | None = None
    test_point_id: str | None = None
    raw_fields: dict[str, str] = Field(default_factory=dict)
    normalized_conditions: Conditions | None = None
    mapping_status: Literal["raw", "reviewed"] = "raw"
    mapping_note: str | None = None

    @model_validator(mode="after")
    def _mapping_state_is_explicit(self) -> PSIConditionRecord:
        if self.mapping_status == "reviewed" and self.normalized_conditions is None:
            raise ValueError("reviewed PSI conditions require normalized_conditions")
        if self.normalized_conditions is not None and self.mapping_status != "reviewed":
            raise ValueError("normalized_conditions require mapping_status='reviewed'")
        return self


__all__ = ["PSIConditionRecord"]
