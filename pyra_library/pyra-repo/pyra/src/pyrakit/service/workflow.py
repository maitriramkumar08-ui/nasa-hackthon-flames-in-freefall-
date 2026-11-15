"""One call that runs a study end to end: gate, simulate, record, compare.

The individual pieces already exist -- the claim gate in :mod:`pyrakit.adapters`, the engine
bridge in :mod:`pyrakit.adapters.external`, the output contract in :mod:`pyrakit.simulation`, the
comparison helpers in :mod:`pyrakit.service.simple` and :mod:`pyrakit.compare`. This module is
the coordinating step that uses them in the right order and keeps the result together, so
a caller does not have to remember that the envelope is checked before the solve and that
a saved run is worthless without the scenario that produced it.

Running a study is not the same as establishing a fact. The returned
:class:`EngineStudy` records what was run and what it was compared against; whether that
amounts to evidence is a judgement the status fields and the envelope check inform, not
one this function makes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from threading import Event

from pyrakit.adapters.envelope import EnvelopeCheck
from pyrakit.adapters.external import ExternalEngineAdapter
from pyrakit.schema import Scenario
from pyrakit.service.simple import QuickComparison, compare_values
from pyrakit.simulation import SimulationOutput


@dataclass(frozen=True)
class EngineStudy:
    """Everything one engine study produced, kept together so it can be reproduced."""

    scenario: Scenario
    output: SimulationOutput
    envelope: EnvelopeCheck | None
    comparison: QuickComparison | None = None
    compared_channel: str | None = None
    saved_to: Path | None = None

    @property
    def supported(self) -> bool:
        """Whether a recorded validation envelope covers this scenario."""
        return self.envelope is not None and self.envelope.inside

    def summary(self) -> str:
        """A plain-language account of what ran, and what it does and does not show."""
        lines = [
            f"Scenario: {self.scenario.scenario_id}",
            f"Engine: {self.output.model_card_id} (version {self.output.engine_version})",
            f"Result status: {self.output.status.name}",
            f"Samples: {len(self.output.time_s)} over {self.output.duration_s:g} s",
            f"Channels: {', '.join(sorted(self.output.channels))}",
        ]
        if self.envelope is None:
            lines.append(
                "Validation envelope: not checked. This run is exploration only and "
                "cannot support a claim about these conditions."
            )
        elif self.envelope.inside:
            backing = ", ".join(
                source for entry in self.envelope.covering for source in entry.experiment_ids
            )
            lines.append(f"Validation envelope: covered by {backing}.")
        else:
            lines.append(f"Validation envelope: NOT covered. {self.envelope.reasons()[0]}")

        if self.comparison is not None and self.compared_channel is not None:
            verdict = "within" if self.comparison.within_tolerance else "outside"
            lines.append(
                f"Comparison on {self.compared_channel!r}: predicted "
                f"{self.comparison.predicted:g} vs observed {self.comparison.observed:g} "
                f"{self.comparison.unit}, {verdict} the tolerance of "
                f"{self.comparison.tolerance:g}."
            )
            lines.append(
                "That tolerance was chosen by you. It is a single-point check, not an "
                "uncertainty-aware validation; use pyrakit.compare for that."
            )
        if self.output.warnings:
            lines.append("Engine warnings: " + "; ".join(self.output.warnings))
        if self.saved_to is not None:
            lines.append(f"Saved to: {self.saved_to}")
        return "\n".join(lines)

    def save(self, directory: str | Path) -> Path:
        """Write the scenario and the engine output side by side into ``directory``.

        Both are needed: an output without its scenario cannot be reproduced, and a
        scenario without its output records nothing.
        """
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        (target / "scenario.json").write_text(
            json.dumps(self.scenario.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        self.output.save(target / "simulation_output.json")
        return target


def run_engine_study(
    adapter: ExternalEngineAdapter,
    scenario: Scenario,
    *,
    require_support: bool = True,
    save_to: str | Path | None = None,
    compare_channel: str | None = None,
    observed: float | None = None,
    tolerance: float | None = None,
    cancel: Event | None = None,
) -> EngineStudy:
    """Run one engine study and keep its scenario, output, gate result and comparison.

    With ``require_support`` left at ``True`` the model card's validation envelope must
    cover the scenario, and :class:`~pyrakit.adapters.ClaimGateError` is raised when it does
    not -- before the engine is started, so an unsupported study fails fast. Set it to
    ``False`` to explore an engine outside its evidence; the result then records that the
    envelope was not checked.

    When ``compare_channel``, ``observed`` and ``tolerance`` are all given, the channel's
    final sample is compared against ``observed`` in that channel's own unit.
    """
    if (compare_channel, observed, tolerance).count(None) not in (0, 3):
        raise ValueError(
            "compare_channel, observed and tolerance must be given together or not at all"
        )

    envelope: EnvelopeCheck | None = None
    if require_support:
        output, envelope = adapter.run_supported(scenario, cancel=cancel)
    else:
        output = adapter.run(scenario, cancel=cancel)

    comparison: QuickComparison | None = None
    if compare_channel is not None and observed is not None and tolerance is not None:
        channel = output.channel(compare_channel)
        comparison = compare_values(
            observed=observed,
            predicted=channel.values[-1],
            unit=channel.unit,
            tolerance=tolerance,
        )

    study = EngineStudy(
        scenario=scenario,
        output=output,
        envelope=envelope,
        comparison=comparison,
        compared_channel=compare_channel,
    )
    if save_to is None:
        return study
    return EngineStudy(
        scenario=study.scenario,
        output=study.output,
        envelope=study.envelope,
        comparison=study.comparison,
        compared_channel=study.compared_channel,
        saved_to=study.save(save_to),
    )


__all__ = ["EngineStudy", "run_engine_study"]
