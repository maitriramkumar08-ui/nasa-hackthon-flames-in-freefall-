"""Run a locally installed simulation engine without importing it.

PYRA has no dependency on any engine. This adapter talks to one as a child process over
a documented JSON contract: the validated scenario goes out on stdin, a
:class:`~pyrakit.simulation.SimulationOutput` comes back on stdout. An engine can therefore
be written in any language, installed separately, and swapped without touching PYRA.

The contract, version "1":

*Sent to the engine on stdin* -- a JSON object with ``pyra_contract``, ``scenario_id``,
``purpose`` and ``conditions``. ``conditions`` is the validated
:class:`~pyrakit.schema.Conditions` dumped to JSON, so each physical input arrives as
``{"value": ..., "unit": ..., "u": ..., "u_kind": ...}`` and the engine never has to guess
a unit.

*Expected back on stdout* -- a JSON object matching
:meth:`~pyrakit.simulation.SimulationOutput.from_dict`: ``scenario_id``, ``model_card_id``,
``engine_version``, ``time_s`` and ``channels`` are required; ``flame_front``, ``mesh``,
``warnings``, ``artifacts`` and ``assumptions`` are optional. Anything the engine writes
to stderr is treated as diagnostics and surfaced on failure.

Running an engine is not the same as supporting a claim with it. :meth:`run` executes the
engine for exploration; :meth:`run_supported` additionally requires the scenario to fall
inside the model card's recorded validation envelope.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event

from pyrakit.adapters.base import require_in_envelope
from pyrakit.adapters.envelope import EnvelopeCheck, EnvelopeGatePolicy
from pyrakit.schema import Conditions, ModelCard, Scenario
from pyrakit.simulation import SimulationOutput

CONTRACT_VERSION = "1"

# How long each poll slice waits before re-checking cancellation and the deadline.
_POLL_SECONDS = 0.1


class EngineError(RuntimeError):
    """Base class for every failure of an external engine."""


class EngineNotFoundError(EngineError):
    """The configured executable could not be started."""


class EngineFailedError(EngineError):
    """The engine ran but exited non-zero, or did not finish in time."""


class EngineOutputError(EngineError):
    """The engine finished but did not return a usable simulation output."""


class EngineCancelled(EngineError):
    """The caller cancelled the run before the engine finished."""


@dataclass(frozen=True)
class EngineCommand:
    """How to invoke one locally installed engine.

    ``executable`` is a path or a name on PATH. ``args`` are passed before the contract is
    written to stdin, for engines that need a subcommand or a config flag. ``timeout_s``
    bounds the run so a hung solver cannot block a caller forever.
    """

    executable: str
    args: tuple[str, ...] = ()
    timeout_s: float = 300.0
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.executable.strip():
            raise ValueError("executable must not be empty")
        if self.timeout_s <= 0:
            raise ValueError("timeout_s must be positive")

    def argv(self) -> list[str]:
        return [self.executable, *self.args]


def scenario_payload(scenario: Scenario) -> dict[str, object]:
    """Build the JSON object an engine receives for one scenario.

    The conditions are dumped straight from the validated schema, so every value carries
    its unit and, where known, its uncertainty.
    """
    return {
        "pyra_contract": CONTRACT_VERSION,
        "scenario_id": scenario.scenario_id,
        "purpose": scenario.purpose,
        "notes": scenario.notes,
        "conditions": scenario.conditions.model_dump(mode="json"),
    }


class ExternalEngineAdapter:
    """Adapt one external engine executable to PYRA's simulation contract."""

    def __init__(
        self,
        card: ModelCard,
        command: EngineCommand,
        *,
        policy: EnvelopeGatePolicy | None = None,
    ) -> None:
        self.card = card
        self.command = command
        self.policy = policy

    @property
    def model_card_id(self) -> str:
        return f"{self.card.name}:{self.card.version}"

    def _start(self) -> subprocess.Popen[str]:
        try:
            return subprocess.Popen(
                self.command.argv(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.command.cwd,
                env={**self.command.env} or None,
            )
        except FileNotFoundError as error:
            raise EngineNotFoundError(
                f"could not start engine {self.command.executable!r}: {error}. "
                "Install the engine, or point EngineCommand.executable at it."
            ) from error
        except OSError as error:
            raise EngineNotFoundError(
                f"could not start engine {self.command.executable!r}: {error}"
            ) from error

    def _invoke(self, scenario: Scenario, cancel: Event | None = None) -> str:
        """Run the engine, honouring a cancellation request while it works.

        The child is polled in short slices rather than waited on in one block, so a GUI
        can stop a long solve promptly. A cancelled or timed-out engine is killed and
        reaped, never left running in the background.
        """
        payload: str | None = json.dumps(scenario_payload(scenario))
        process = self._start()
        deadline = time.monotonic() + self.command.timeout_s

        while True:
            if cancel is not None and cancel.is_set():
                self._terminate(process)
                raise EngineCancelled(f"engine {self.command.executable!r} was cancelled")
            if time.monotonic() > deadline:
                self._terminate(process)
                raise EngineFailedError(
                    f"engine {self.command.executable!r} did not finish within "
                    f"{self.command.timeout_s:g} s"
                )
            try:
                stdout, stderr = process.communicate(input=payload, timeout=_POLL_SECONDS)
                break
            except subprocess.TimeoutExpired:
                payload = None  # stdin was already written on the first attempt
                continue

        if process.returncode != 0:
            diagnostics = (stderr or "").strip() or "(no stderr)"
            raise EngineFailedError(
                f"engine {self.command.executable!r} exited with code "
                f"{process.returncode}. Engine diagnostics: {diagnostics}"
            )
        return stdout

    @staticmethod
    def _terminate(process: subprocess.Popen[str]) -> None:
        """Stop a child process and reap it, so no engine is left running."""
        process.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.communicate(timeout=_POLL_SECONDS * 10)

    def _parse(self, raw: str, scenario: Scenario) -> SimulationOutput:
        if not raw.strip():
            raise EngineOutputError(
                f"engine {self.command.executable!r} wrote nothing to stdout; "
                "it must return the simulation output as JSON"
            )
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as error:
            raise EngineOutputError(
                f"engine {self.command.executable!r} did not return valid JSON: {error}"
            ) from error
        try:
            output = SimulationOutput.from_dict(document)
        except (ValueError, KeyError, TypeError) as error:
            raise EngineOutputError(
                f"engine {self.command.executable!r} returned an unusable output: {error}"
            ) from error

        # An engine that answers about a different scenario, or claims to be a different
        # model than its card, cannot be reproduced from this run's record.
        if output.scenario_id != scenario.scenario_id:
            raise EngineOutputError(
                f"engine returned scenario_id {output.scenario_id!r} "
                f"but was asked about {scenario.scenario_id!r}"
            )
        if output.model_card_id != self.model_card_id:
            raise EngineOutputError(
                f"engine reported model_card_id {output.model_card_id!r} "
                f"but its card says {self.model_card_id!r}"
            )
        return output

    def run(self, scenario: Scenario, *, cancel: Event | None = None) -> SimulationOutput:
        """Run the engine for exploration, with no claim of validity attached.

        The result is a model output. It is not evidence, and it is not checked against
        the model's validation envelope; use :meth:`run_supported` for that.
        """
        return self._parse(self._invoke(scenario, cancel), scenario)

    def run_supported(
        self, scenario: Scenario, *, cancel: Event | None = None
    ) -> tuple[SimulationOutput, EnvelopeCheck]:
        """Run the engine only when its recorded evidence covers this scenario.

        The envelope is checked first, so an unsupported scenario fails immediately
        instead of after a long solve. Returns the output together with the check that
        permitted it, so a caller can record which evidence backed the claim.
        """
        check = require_in_envelope(self.card, scenario, policy=self.policy)
        return self.run(scenario, cancel=cancel), check

    def at(self, conditions: Conditions, base: Scenario) -> Scenario:
        """Create a hindcast scenario that replays measured conditions through the engine."""
        return base.model_copy(update={"conditions": conditions, "purpose": "hindcast"})


def python_engine_command(script: str | Path, **kwargs: object) -> EngineCommand:
    """Build a command that runs a Python engine script with the current interpreter.

    Convenience for a reference or test engine. ``-I`` is used so the engine cannot pick
    up modules from the caller's working directory.
    """
    import sys

    return EngineCommand(
        executable=sys.executable,
        args=("-I", str(script)),
        **kwargs,  # type: ignore[arg-type]
    )


__all__ = [
    "CONTRACT_VERSION",
    "EngineCancelled",
    "EngineCommand",
    "EngineError",
    "EngineFailedError",
    "EngineNotFoundError",
    "EngineOutputError",
    "ExternalEngineAdapter",
    "python_engine_command",
    "scenario_payload",
]
