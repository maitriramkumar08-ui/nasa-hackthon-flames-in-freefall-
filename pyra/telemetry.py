"""Scripted, made-up cabin telemetry for the demo views. Every value is SIMULATED.

Nothing here is NASA data. Each scenario starts from a baseline cabin and adds
a drift per second and some random sensor noise. The random generator is seeded,
so the same seed always gives the same stream, and a recorded stream can be
saved as JSON lines and replayed for a demo.

The nominal 8.2 psia / 34% O2 atmosphere is the scenario input given in the
PYRA Master Prompt Pack (Prompt 16). We have not checked it against a source.
The other baseline numbers (CO, CO2, temperature, flow) are our own round
numbers chosen so the demo looks plausible.
"""

import json
import random

from . import units

CHANNELS = ["o2_percent", "total_pressure_kpa", "co_ppm", "co2_ppm",
            "smoke_level", "temperature_c", "flow_cm_s"]

BASELINE = {
    "o2_percent": 34.0,
    "total_pressure_kpa": round(units.convert(8.2, "psia", "kPa"), 2),
    "co_ppm": 1.0,
    "co2_ppm": 2000.0,
    "smoke_level": 0.0,
    "temperature_c": 22.0,
    "flow_cm_s": 10.0,
}

# Standard deviation of the sensor noise, per channel, before the noise multiplier.
NOISE = {
    "o2_percent": 0.1,
    "total_pressure_kpa": 0.2,
    "co_ppm": 0.2,
    "co2_ppm": 20.0,
    "smoke_level": 0.005,
    "temperature_c": 0.1,
    "flow_cm_s": 0.3,
}

# drift is change per second; stuck names a channel that freezes at its first reading.
SCENARIOS = {
    "nominal": {"drift": {}},
    "o2_drift_fan_slowing": {"drift": {"o2_percent": 0.01, "flow_cm_s": -0.02}},
    "overheating_wire": {"drift": {"smoke_level": 0.004, "co_ppm": 0.3, "temperature_c": 0.02}},
    "stuck_sensor": {"drift": {}, "stuck": "o2_percent"},
}

LIMITS = {"smoke_level": (0.0, 1.0)}


def _clamp(channel, value):
    low, high = LIMITS.get(channel, (0.0, None))
    value = max(low, value)
    return value if high is None else min(high, value)


def stream(scenario, seed=0, steps=60, dt=1.0, compartment="habitat", noise=1.0, drift=1.0):
    """Yield one SIMULATED message per step. noise and drift scale the defaults (0 turns them off)."""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario {scenario!r}, pick one of {sorted(SCENARIOS)}")
    script = SCENARIOS[scenario]
    rng = random.Random(seed)
    stuck = {}
    for step in range(steps):
        t = round(step * dt, 6)
        message = {"source": "SIMULATED", "scenario": scenario, "compartment": compartment, "t": t}
        for channel in CHANNELS:
            true_value = BASELINE[channel] + script["drift"].get(channel, 0.0) * drift * t
            reading = _clamp(channel, true_value + rng.gauss(0.0, NOISE[channel] * noise))
            if channel == script.get("stuck"):
                reading = stuck.setdefault(channel, reading)
            message[channel] = round(reading, 4)
        yield message


def record(scenario, seed=0, steps=60, dt=1.0, compartment="habitat", noise=1.0, drift=1.0):
    """The whole stream as a list."""
    return list(stream(scenario, seed, steps, dt, compartment, noise, drift))


def save(messages, path):
    """Write messages as JSON lines so the demo can replay them."""
    with open(path, "w", encoding="utf-8") as out:
        for message in messages:
            out.write(json.dumps(message) + "\n")


def replay(path):
    """Yield the messages from a saved JSON-lines file, in order."""
    with open(path, encoding="utf-8") as saved:
        for number, line in enumerate(saved, 1):
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError as err:
                raise ValueError(f"{path} line {number} is not valid JSON: {err}") from None
            if message.get("source") != "SIMULATED":
                raise ValueError(f"{path} line {number} is not marked SIMULATED")
            yield message
