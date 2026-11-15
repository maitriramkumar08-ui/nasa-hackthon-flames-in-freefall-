"""Epistemic status as a type, plus Provenance and Quantity (architecture section 3).

Rules enforced here:

* The status of a result is the maximum (``join``) over its inputs and over the status of the
  method that produced it. It can never be lower than any input.
* ``Quantity.derive`` cannot produce MEASURED; only ``Quantity.measured`` can, and it requires a
  source reference. Nothing that touches a SCENARIO can come out as measured.
* A derived method may declare the highest input status it accepts; violations raise at call time.
* ``artifact_id`` hashes content, parents, activity, parameters and source reference. It excludes
  code version, environment hash and timestamp, so ids are reproducible across machines and time.
  Changing any parent changes the child id. See docs/adr/0001 and 0002.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from typing import Any

from pyrakit.provenance.hashing import sha256_hex


class Status(IntEnum):
    """Epistemic status, ordered by distance from direct observation (higher = weaker)."""

    MEASURED = 0
    DERIVED = 1
    SIMULATED = 2
    SCENARIO = 3
    INTERPRETATION = 4


class StatusError(ValueError):
    """A status rule was violated."""


class StatusInputError(StatusError):
    """An input has a higher status than the method accepts."""


def join(*statuses: Status) -> Status:
    """Status of a result: never more certain than the weakest input."""
    if not statuses:
        raise ValueError("join() needs at least one status")
    for s in statuses:
        if not isinstance(s, Status):
            raise TypeError(f"expected Status, got {type(s).__name__}")
    return Status(max(statuses))


def enforce_max_input_status(inputs: Iterable[Status], max_allowed: Status, method: str) -> None:
    """Raise StatusInputError if any input is above ``max_allowed`` (call-time method guard)."""
    for s in inputs:
        if s > max_allowed:
            raise StatusInputError(
                f"{method}: input status {s.name} exceeds the maximum allowed {max_allowed.name}"
            )


U_KINDS = ("type_a", "type_b", "assumed", "unknown")


def _utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Provenance:
    """Where an artifact came from: parents, activity, parameters, source and environment."""

    artifact_id: str             # sha256 of canonical content (see make_artifact_id)
    parents: tuple[str, ...]     # lineage: artifact ids of inputs, in call order
    activity: str                # function id + version
    params: dict[str, Any]
    source_ref: str | None       # DOI / URL / PSI id + file hash + location
    code_version: str            # git commit, or "unknown"
    env_hash: str                # hash of resolved dependency set, or "unknown"
    created_utc: str

    def to_dict(self) -> dict[str, Any]:
        """Plain-dict form used by the ledger."""
        return {
            "artifact_id": self.artifact_id,
            "parents": list(self.parents),
            "activity": self.activity,
            "params": dict(self.params),
            "source_ref": self.source_ref,
            "code_version": self.code_version,
            "env_hash": self.env_hash,
            "created_utc": self.created_utc,
        }

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> Provenance:
        """Inverse of ``to_dict``; raises KeyError if a field is missing."""
        return cls(
            artifact_id=str(d["artifact_id"]),
            parents=tuple(str(p) for p in d["parents"]),
            activity=str(d["activity"]),
            params=dict(d["params"]),
            source_ref=None if d["source_ref"] is None else str(d["source_ref"]),
            code_version=str(d["code_version"]),
            env_hash=str(d["env_hash"]),
            created_utc=str(d["created_utc"]),
        )


def make_artifact_id(
    *,
    content: Any,
    parents: Sequence[str],
    activity: str,
    params: Mapping[str, Any],
    source_ref: str | None,
) -> str:
    return sha256_hex(
        {
            "content": content,
            "parents": list(parents),
            "activity": activity,
            "params": params,
            "source_ref": source_ref,
        }
    )


def _content(value: Any, unit: str, u: Any, u_kind: str, status: Status) -> dict[str, Any]:
    return {"value": value, "unit": unit, "u": u, "u_kind": u_kind, "status": int(status)}


def _check_uncertainty(u: Any) -> None:
    if u is None:
        return
    if isinstance(u, float) and math.isnan(u):
        raise ValueError("uncertainty must not be NaN; use u=None with u_kind='unknown'")
    negative = u < 0
    if hasattr(negative, "any"):         # numpy-like arrays
        negative = negative.any()
    if bool(negative):
        raise ValueError("uncertainty must be non-negative")


@dataclass(frozen=True)
class Quantity:
    """A value with a unit, an uncertainty, an epistemic status and its provenance.

    Build one with ``Quantity.measured``, ``Quantity.scenario`` or ``Quantity.derive``; direct
    construction is for deserialization. Quantities are immutable.
    """

    value: Any                   # float or array-like (xarray support is verified at P3/P4)
    unit: str                    # pint-validated from P2; non-empty string for now
    u: Any | None                # standard uncertainty; None only with u_kind == "unknown"
    u_kind: str                  # 'type_a' | 'type_b' | 'assumed' | 'unknown'
    status: Status
    prov: Provenance

    def __post_init__(self) -> None:
        if not isinstance(self.status, Status):
            raise TypeError(f"status must be a Status, got {type(self.status).__name__}")
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise ValueError("unit must be a non-empty string")
        if self.u_kind not in U_KINDS:
            raise ValueError(f"u_kind must be one of {U_KINDS}, got {self.u_kind!r}")
        if (self.u is None) != (self.u_kind == "unknown"):
            raise ValueError("u is None exactly when u_kind == 'unknown'")
        _check_uncertainty(self.u)

    # -- identity ---------------------------------------------------------------------------
    def expected_id(self) -> str:
        """The artifact id this content should have, recomputed from the current fields."""
        return make_artifact_id(
            content=_content(self.value, self.unit, self.u, self.u_kind, self.status),
            parents=self.prov.parents,
            activity=self.prov.activity,
            params=self.prov.params,
            source_ref=self.prov.source_ref,
        )

    def verify(self) -> bool:
        """True if the stored artifact id matches the current content (detects tampering)."""
        return self.expected_id() == self.prov.artifact_id

    # -- constructors -----------------------------------------------------------------------
    @classmethod
    def _build(
        cls,
        *,
        value: Any,
        unit: str,
        u: Any | None,
        u_kind: str,
        status: Status,
        parents: tuple[str, ...],
        activity: str,
        params: Mapping[str, Any] | None,
        source_ref: str | None,
        code_version: str,
        env_hash: str,
        created_utc: str | None,
    ) -> Quantity:
        p = dict(params or {})
        artifact_id = make_artifact_id(
            content=_content(value, unit, u, u_kind, status),
            parents=parents,
            activity=activity,
            params=p,
            source_ref=source_ref,
        )
        prov = Provenance(
            artifact_id=artifact_id,
            parents=parents,
            activity=activity,
            params=p,
            source_ref=source_ref,
            code_version=code_version,
            env_hash=env_hash,
            created_utc=created_utc or _utc_now(),
        )
        return cls(value=value, unit=unit, u=u, u_kind=u_kind, status=status, prov=prov)

    @classmethod
    def measured(
        cls,
        value: Any,
        unit: str,
        u: Any | None,
        u_kind: str,
        *,
        source_ref: str,
        activity: str = "read",
        params: Mapping[str, Any] | None = None,
        code_version: str = "unknown",
        env_hash: str = "unknown",
        created_utc: str | None = None,
    ) -> Quantity:
        """A value read from a source file or channel. Requires a source reference."""
        if not source_ref or not source_ref.strip():
            raise ValueError("MEASURED requires a source_ref (DOI/URL, file hash, location)")
        return cls._build(
            value=value, unit=unit, u=u, u_kind=u_kind, status=Status.MEASURED, parents=(),
            activity=activity, params=params, source_ref=source_ref,
            code_version=code_version, env_hash=env_hash, created_utc=created_utc,
        )

    @classmethod
    def scenario(
        cls,
        value: Any,
        unit: str,
        u: Any | None,
        u_kind: str,
        *,
        activity: str,
        params: Mapping[str, Any] | None = None,
        source_ref: str | None = None,
        code_version: str = "unknown",
        env_hash: str = "unknown",
        created_utc: str | None = None,
    ) -> Quantity:
        """User-specified or hypothetical conditions (status SCENARIO)."""
        return cls._build(
            value=value, unit=unit, u=u, u_kind=u_kind, status=Status.SCENARIO, parents=(),
            activity=activity, params=params, source_ref=source_ref,
            code_version=code_version, env_hash=env_hash, created_utc=created_utc,
        )

    @classmethod
    def derive(
        cls,
        value: Any,
        unit: str,
        u: Any | None,
        u_kind: str,
        *,
        parents: Sequence[Quantity],
        activity: str,
        params: Mapping[str, Any] | None = None,
        method_status: Status = Status.DERIVED,
        max_input_status: Status | None = None,
        source_ref: str | None = None,
        code_version: str = "unknown",
        env_hash: str = "unknown",
        created_utc: str | None = None,
    ) -> Quantity:
        """A value computed from other quantities.

        The result status is ``join(method_status, *parent statuses)``; it cannot be lowered.
        ``method_status`` says what kind of step this is (DERIVED, SIMULATED, INTERPRETATION...)
        and must be at least DERIVED.
        """
        if not parents:
            raise ValueError("derive() needs at least one parent; use measured() or scenario()")
        if method_status < Status.DERIVED:
            raise StatusError("a derived quantity cannot have status MEASURED")
        parent_statuses = [p.status for p in parents]
        if max_input_status is not None:
            enforce_max_input_status(parent_statuses, max_input_status, activity)
        status = join(method_status, *parent_statuses)
        return cls._build(
            value=value, unit=unit, u=u, u_kind=u_kind, status=status,
            parents=tuple(p.prov.artifact_id for p in parents),
            activity=activity, params=params, source_ref=source_ref,
            code_version=code_version, env_hash=env_hash, created_utc=created_utc,
        )
