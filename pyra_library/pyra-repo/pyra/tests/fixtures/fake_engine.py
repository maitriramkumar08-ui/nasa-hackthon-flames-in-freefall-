"""A deliberately fictional engine that satisfies PYRA's contract, for testing the bridge.

It reads a scenario on stdin and writes a simulation output on stdout. The numbers come
from an arbitrary closed-form expression chosen to be reproducible; they carry no physical
meaning whatsoever and must never be presented as a fire prediction.

Behaviour can be steered for tests through argv:

    --exit-code N        exit with N after writing diagnostics to stderr
    --emit-garbage       write text that is not JSON
    --emit-nothing       write nothing at all
    --wrong-scenario     answer about a different scenario_id
    --wrong-card         report a model_card_id the card does not match
    --drop-unit          omit a channel's unit, to exercise contract validation
    --hang               sleep well past any sane test timeout
"""

from __future__ import annotations

import json
import math
import sys
import time

ENGINE_VERSION = "0.1.0-fictional"
MODEL_CARD_ID = "fake-engine:0.1"


def main() -> int:
    flags = set(sys.argv[1:])

    if "--hang" in flags:
        time.sleep(60)

    for flag in flags:
        if flag.startswith("--exit-code="):
            print("fictional engine: simulated failure", file=sys.stderr)
            return int(flag.split("=", 1)[1])

    request = json.loads(sys.stdin.read())
    conditions = request["conditions"]
    scenario_id = request["scenario_id"]

    if "--emit-nothing" in flags:
        return 0
    if "--emit-garbage" in flags:
        sys.stdout.write("this is not json")
        return 0

    # An arbitrary but deterministic shape driven by the inputs, so tests can prove the
    # scenario actually reached the engine. This is not a physical model.
    oxygen = float(conditions["o2_mole_fraction"]["value"])
    gravity = float(conditions["gravity_g"]["value"])
    steps = 11
    duration = 10.0
    times = [duration * index / (steps - 1) for index in range(steps)]
    scale = 10.0 * oxygen
    growth = 0.3 + gravity
    hrr = [scale * (1.0 - math.exp(-growth * t)) for t in times]
    front = [0.001 * scale * t for t in times]

    channel: dict[str, object] = {
        "name": "hrr",
        "unit": "kW",
        "long_name": "Heat release rate",
        "values": hrr,
        "uncertainty": [0.05 * value for value in hrr],
    }
    if "--drop-unit" in flags:
        del channel["unit"]

    document = {
        "scenario_id": "some-other-scenario" if "--wrong-scenario" in flags else scenario_id,
        "model_card_id": "other-engine:9" if "--wrong-card" in flags else MODEL_CARD_ID,
        "engine_version": ENGINE_VERSION,
        "status": "SIMULATED",
        "time_s": times,
        "channels": {"hrr": channel},
        "flame_front": {"position_m": front},
        "mesh": {
            "dimensions": 2,
            "cell_count": 4096,
            "min_cell_size_m": 0.0005,
            "note": "fictional uniform mesh",
        },
        "warnings": ["fictional engine: outputs carry no physical meaning"],
        "assumptions": ["closed-form test expression", "no chemistry, radiation or buoyancy"],
    }
    json.dump(document, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
