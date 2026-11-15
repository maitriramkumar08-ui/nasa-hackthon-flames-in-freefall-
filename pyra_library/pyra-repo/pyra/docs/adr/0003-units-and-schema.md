# ADR 0003: Pint units and pydantic metadata schemas

Status: accepted

Date: 2026-11-15

## Context

PYRA needs unit-bearing metadata that can be serialized to JSON while preserving the provenance
layer's immutable `Quantity` objects. The architecture calls for Pint for dimensional checks and
pydantic for published metadata schemas. Microgravity must remain a measured residual rather than
being represented as an exact zero.

## Decision

Use a shared Pint `UnitRegistry` in `pyrakit.units`, with `g0` and `mole_fraction` domain units. Use a
small pydantic `Measure` model inside `Conditions`, `FuelSpec`, and experiment metadata. A measure
must declare either a non-negative standard uncertainty and its kind, or `u_kind="unknown"` with
`u=None`. Conditions validate dimensionality and oxygen fraction bounds at construction time.

The schema layer uses versioned JSON-compatible pydantic models: `SourceRef`, `ExperimentRecord`,
`Scenario`, `ValidationEvidence`, and `ModelCard`. A model card is considered validated only when
it contains at least one validation evidence record; an empty envelope remains an explicit refusal
boundary for later adapters and claim gates.

## Dependency versions checked

The implementation was checked with Pint 0.26.2, pydantic 2.13.4, and xarray 2026.9.0. These are
environment observations for this checkpoint, not a promise that future releases are compatible.

## Consequences

Schemas reject unit-inconsistent inputs early and round-trip through JSON. The core `Quantity` API
remains unchanged, so status and artifact identity rules continue to apply. Matching defaults,
calorimetry constants, and investigation-specific field mappings remain deliberately undecided.
