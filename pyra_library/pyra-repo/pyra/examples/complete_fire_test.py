"""One complete PYRA beginner workflow; all inputs and outputs are illustrative."""

from pathlib import Path

import pyra_library as pk

run = pk.run_fire_test(
    fuel="PMMA (example label)",
    gravity_g=0.0,
    oxygen_fraction=0.21,
    pressure_kpa=101.3,
    temperature_k=293.15,
    air_exchange_per_s=0.02,
    oxygen_sink_per_s=0.001,
    duration_s=60,
)
print(run.summary())
print("Saved result:", run.save(Path("fire_test_result.json")))

# This compares two values in the same unit with a tolerance chosen for the exercise.
comparison = pk.compare(
    observed=0.20,
    predicted=run.trace.concentration[-1],
    unit="dimensionless",
    tolerance=0.02,
)
print("Within comparison tolerance:", comparison.within_tolerance)

# To open the chart locally, uncomment:
# run.show()
