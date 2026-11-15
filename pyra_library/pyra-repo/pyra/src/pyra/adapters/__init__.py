"""Simulator adapters and the validation claim gate.

Two gates are available. ``require_validated`` only asks whether a model card records
any validation evidence at all. ``require_in_envelope`` additionally checks that the
scenario being claimed falls inside the recorded envelope, which is what a claim
about particular conditions needs.
"""

from pyra.adapters.base import (
    ClaimGateError,
    SimulationResult,
    require_in_envelope,
    require_validated,
)
from pyra.adapters.callable import CallableAdapter
from pyra.adapters.envelope import (
    AxisCheck,
    EnvelopeCheck,
    EnvelopeGatePolicy,
    EvidenceCheck,
    check_envelope,
    parse_envelope,
)
from pyra.adapters.external import (
    EngineCancelled,
    EngineCommand,
    EngineError,
    EngineFailedError,
    EngineNotFoundError,
    EngineOutputError,
    ExternalEngineAdapter,
    python_engine_command,
    scenario_payload,
)

__all__ = [
    "AxisCheck",
    "CallableAdapter",
    "ClaimGateError",
    "EngineCancelled",
    "EngineCommand",
    "EngineError",
    "EngineFailedError",
    "EngineNotFoundError",
    "EngineOutputError",
    "EnvelopeCheck",
    "EnvelopeGatePolicy",
    "EvidenceCheck",
    "ExternalEngineAdapter",
    "SimulationResult",
    "check_envelope",
    "parse_envelope",
    "python_engine_command",
    "require_in_envelope",
    "require_validated",
    "scenario_payload",
]
