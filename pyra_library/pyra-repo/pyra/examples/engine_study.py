"""The whole flow in one file: beginner form, typed scenario, engine, record, compare.

Run it with your project's interpreter:

    python examples/engine_study.py

It drives the fictional test engine that ships with PYRA's test suite, so it runs without
installing anything. Every number is meaningless by construction. Point `ENGINE` at a real
executable and supply a real model card to do actual work.
"""

import sys
from pathlib import Path
from tempfile import mkdtemp

from pyra.adapters import ClaimGateError, EngineCommand, ExternalEngineAdapter
from pyra.schema import ModelCard, ValidationEvidence
from pyra.service.scenario_inputs import FireScenario, ViewSource
from pyra.service.workflow import run_engine_study

# The fictional engine used by PYRA's own tests. Replace with your engine's executable.
ENGINE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "fake_engine.py"


def engine_card() -> ModelCard:
    """A model card describing where this engine's evidence actually reaches.

    The `envelope` is the important part. It says this engine was only ever compared
    against experiments between 0 and 1.1 g, 18-25% oxygen, and 95-105 kPa. PYRA refuses
    to call a result outside that range supported.
    """
    return ModelCard(
        name="fake-engine",
        version="0.1",
        code_hash="sha256:fictional",
        licence="MIT",
        physics_summary="Fictional test engine. Produces arbitrary numbers.",
        limitations=["No evidence below 18% oxygen.", "No evidence above 1.1 g."],
        envelope=[
            ValidationEvidence(
                experiment_ids=["fictional-bench-01"],
                quantity="hrr",
                metric="bias",
                result={"bias": 0.0, "n_cases": 12},
                envelope={
                    "gravity_g": [0.0, 1.1],
                    "o2_mole_fraction": [0.18, 0.25],
                    "pressure": {"min": 95, "max": 105, "unit": "kPa"},
                },
            )
        ],
    )


adapter = ExternalEngineAdapter(
    engine_card(),
    EngineCommand(executable=sys.executable, args=("-I", str(ENGINE)), timeout_s=60.0),
)

print("=== 1. The beginner form ===")
# These are the same fields the Fire Playground window shows.
form = FireScenario(
    fuel="PMMA (example label)",
    gravity_g=1.0,
    oxygen_fraction=0.21,
    pressure_kpa=101.3,
    temperature_k=293.15,
    flow_mode="forced",
    flow_velocity_m_s=0.1,
    fuel_thickness_m=0.003,
    ignition_power_w=5.0,
    ignition_duration_s=2.0,
    oxygen_uncertainty=0.005,
)
print(f"Fuel {form.fuel!r} at {form.gravity_g:g} g, {form.oxygen_fraction:g} oxygen.\n")

print("=== 2. Turned into a validated scenario, with units ===")
scenario = form.to_scenario("bench-study", purpose="hindcast")
conditions = scenario.conditions
print(f"pressure        {conditions.pressure.value:g} {conditions.pressure.unit}")
print(
    f"oxygen          {conditions.o2_mole_fraction.value:g} "
    f"(standard uncertainty {conditions.o2_mole_fraction.u}, "
    f"kind {conditions.o2_mole_fraction.u_kind})"
)
print(f"fuel thickness  {conditions.fuel.thickness.value:g} {conditions.fuel.thickness.unit}")
print(f"notes           {scenario.notes}\n")

print("=== 3. Gate, run, record and compare in one call ===")
workspace = Path(mkdtemp(prefix="pyra-study-"))
study = run_engine_study(
    adapter,
    scenario,
    save_to=workspace,
    compare_channel="hrr",
    observed=2.0,
    tolerance=100.0,
)
print(study.summary())
print()

print("=== 4. The run is reproducible from what was written ===")
for item in sorted(p.name for p in workspace.iterdir()):
    print(f"  {item}")
print()

print("=== 5. The same engine, a scenario its evidence does not reach ===")
thin_air = form.with_changes(oxygen_fraction=0.10).to_scenario("low-oxygen-study")
try:
    run_engine_study(adapter, thin_air)
except ClaimGateError as error:
    print(f"Refused, correctly:\n  {error}\n")

print("=== 6. Exploring outside the envelope is still allowed, and says so ===")
exploratory = run_engine_study(adapter, thin_air, require_support=False)
print(exploratory.summary())
print()

print("=== 7. What the Playground would label these ===")
for source in ViewSource:
    print(f"  {source.headline}: {source.explanation[:72]}...")
