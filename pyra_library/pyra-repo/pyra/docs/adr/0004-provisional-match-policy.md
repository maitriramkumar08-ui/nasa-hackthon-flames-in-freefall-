# ADR 0004: Provisional matching policy

Status: provisional

Date: 2026-11-15

## Context

The architecture requires hard gates for configuration, fuel class, and flow mode; log-space
comparison for pressure and gravity; a floor near zero gravity; and a retained per-dimension mismatch
vector. It does not prescribe weights or tolerances.

## Decision

The first executable policy uses equal weights, a gravity log tolerance of 0.25, pressure log
tolerance of 0.02, oxygen-fraction tolerance of 0.01, flow-velocity tolerance of 0.05 m/s,
length-scale tolerance of 0.01 m, `g_floor=1e-4`, `d_max=3`, and aggregate threshold 3. These are
provisional engineering defaults for exercising the code and must be reviewed against the data audit
before scientific conclusions are drawn.

The engine returns `NONE` with explicit gate names when configuration, fuel material, or flow mode
differs. It never reduces the mismatch vector to the aggregate distance alone. Pareto ranking is
available separately.

## Consequences

Matching is deterministic and testable now. Changing the policy is explicit and versioned. The
defaults do not authorize extrapolation, analog matching, or claims about physical equivalence.
