"""Model cards and validation envelopes for external simulators."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ValidationEvidence(BaseModel):
    """One comparison result supporting a model's declared validity envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    experiment_ids: list[str] = Field(min_length=1)
    quantity: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    result: dict[str, Any]
    envelope: dict[str, Any]


class ModelCard(BaseModel):
    """Identity, limitations and validation evidence for a simulation model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = "1"
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    code_hash: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    physics_summary: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    envelope: list[ValidationEvidence] = Field(default_factory=list)

    @property
    def validated(self) -> bool:
        """Whether at least one validation result has been recorded."""
        return bool(self.envelope)
