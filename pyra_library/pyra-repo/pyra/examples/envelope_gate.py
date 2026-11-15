"""Why "this model is validated" is not enough to support a claim about a scenario.

Copy this file into your own project folder and run it with that project's
interpreter:

    python examples/envelope_gate.py

Every identifier, limit and number below is a fictional placeholder. Nothing here is
a real dataset, a real model, or a fire-safety claim.
"""

from pyra.adapters import (
    ClaimGateError,
    EnvelopeGatePolicy,
    check_envelope,
    require_in_envelope,
    require_validated,
)
from pyra.schema import Conditions, FuelSpec, Measure, ModelCard, Scenario, ValidationEvidence


def bench_card() -> ModelCard:
    """A fictional model whose only evidence was gathered on an Earth-gravity bench.

    The `envelope` mapping is the important part: it records the conditions the
    comparison actually spanned. `gravity_g` is bounded to roughly Earth gravity,
    oxygen to 18-25%, and pressure to 95-105 kPa (written in kPa, compared in Pa).
    """
    return ModelCard(
        name="bench-flame",
        version="0.3",
        code_hash="sha256:fictional",
        licence="MIT",
        physics_summary="Fictional bench-scale correlation used only as an example.",
        limitations=["No microgravity evidence.", "No evidence below 18% oxygen."],
        envelope=[
            ValidationEvidence(
                experiment_ids=["fictional-bench-01"],
                quantity="flame_length",
                metric="bias",
                result={"bias": 0.0, "n_cases": 12},
                envelope={
                    "gravity_g": [0.9, 1.1],
                    "o2_mole_fraction": [0.18, 0.25],
                    "pressure": {"min": 95, "max": 105, "unit": "kPa"},
                },
            )
        ],
    )


def scenario_at(scenario_id: str, gravity_g: float) -> Scenario:
    """Build one scenario that differs from the others only in gravity.

    `gravity_g` is a multiple of Earth gravity, so 1.0 is a laboratory bench and
    1e-5 is the residual acceleration typical of an orbiting vehicle. Microgravity
    is a small residual, never exactly zero.
    """
    return Scenario(
        scenario_id=scenario_id,
        purpose="example",
        conditions=Conditions(
            gravity_g=Measure(value=gravity_g, unit="dimensionless"),
            pressure=Measure(value=101.3, unit="kPa"),
            o2_mole_fraction=Measure(value=0.21, unit="dimensionless"),
            diluent="nitrogen",
            flow_mode="forced",
            fuel=FuelSpec(material="PMMA"),
            configuration="concurrent",
            length_scale=Measure(value=0.02, unit="m"),
        ),
    )


card = bench_card()
earth = scenario_at("earth-bench", 1.0)
microgravity = scenario_at("microgravity-demo", 1e-5)

print("=== 1. The presence-only gate ===")
require_validated(card)
print("require_validated passed: the card records at least one piece of evidence.")
print("That says nothing about whether the evidence reaches your scenario.\n")

print("=== 2. The scenario-aware gate, inside the envelope ===")
inside = require_in_envelope(card, earth)
print(f"Scenario {earth.scenario_id!r} is covered by: {inside.covering[0].experiment_ids}\n")

print("=== 3. The same model, a microgravity scenario ===")
report = check_envelope(card, microgravity)
print(report.explain())
print()

try:
    require_in_envelope(card, microgravity)
except ClaimGateError as error:
    print(f"ClaimGateError (this is the correct outcome):\n  {error}\n")

print("=== 4. An entry that records no limits covers nothing ===")
vague = card.model_copy(
    update={
        "envelope": [
            ValidationEvidence(
                experiment_ids=["fictional-bench-02"],
                quantity="flame_length",
                metric="bias",
                result={"bias": 0.0},
                envelope={},
            )
        ]
    }
)
require_validated(vague)  # still passes: evidence is present
print("require_validated passed, but check_envelope reports:")
print(f"  inside = {check_envelope(vague, earth).inside}")
print(f"  reason = {check_envelope(vague, earth).reasons()[0]}\n")

print("=== 5. Required axes are a policy you can state explicitly ===")
gravity_only = card.model_copy(
    update={
        "envelope": [
            ValidationEvidence(
                experiment_ids=["fictional-bench-03"],
                quantity="flame_length",
                metric="bias",
                result={"bias": 0.0},
                envelope={"gravity_g": [0.9, 1.1]},
            )
        ]
    }
)
default_check = check_envelope(gravity_only, earth)
print(f"With the default policy, inside = {default_check.inside}")
print(f"  missing: {default_check.evidence[0].missing_required_axes}")
relaxed = check_envelope(gravity_only, earth, policy=EnvelopeGatePolicy(("gravity_g",)))
print(f"Declaring gravity alone sufficient, inside = {relaxed.inside}")
print("Widening a policy is a scientific decision you record, not a default.")
