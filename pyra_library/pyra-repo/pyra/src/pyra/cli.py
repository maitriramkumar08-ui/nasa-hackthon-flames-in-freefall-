"""Small standard-library CLI for first programs and local trace demos."""

from __future__ import annotations

import argparse
import json

from pyra.physics.zone import simulate_zone
from pyra.provenance import inspect_ledger
from pyra.service.simple import show_simulation, simulate_decay


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyra", description="PYRA spacecraft fire-safety evidence tools"
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("demo", help="print a small fictional decay trace")
    simulate = commands.add_parser("simulate", help="generate a fictional trace")
    simulate.add_argument("--initial", type=float, default=1.0)
    simulate.add_argument("--rate", type=float, default=0.5)
    simulate.add_argument("--duration", type=float, default=4.0)
    simulate.add_argument("--steps", type=int, default=25)
    simulate.add_argument("--window", action="store_true", help="open the Tkinter plot window")
    zone = commands.add_parser(
        "zone", help="run the simplified single-zone concentration teaching model"
    )
    zone.add_argument("--initial", type=float, default=0.21, help="initial concentration (0 to 1)")
    zone.add_argument("--inlet", type=float, default=0.21, help="inlet concentration (0 to 1)")
    zone.add_argument("--exchange-rate", type=float, default=0.0, help="air exchange rate in 1/s")
    zone.add_argument(
        "--source-rate", type=float, default=0.0, help="concentration source rate in 1/s"
    )
    zone.add_argument("--duration", type=float, default=60.0, help="duration in seconds")
    zone.add_argument("--steps", type=int, default=21)
    zone.add_argument("--window", action="store_true", help="plot the trace in a Tkinter window")
    replay = commands.add_parser("replay", help="parse a JSONL provenance ledger")
    replay.add_argument("ledger")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the CLI; no external services are required for the demo commands."""
    args = _parser().parse_args(argv)
    if args.command == "replay":
        result = inspect_ledger(args.ledger)
        print(json.dumps({"checked": result.checked, "ok": result.ok}))
        return
    if args.command == "zone":
        trace = simulate_zone(
            initial_concentration=args.initial,
            inlet_concentration=args.inlet,
            exchange_rate_per_s=args.exchange_rate,
            source_rate_per_s=args.source_rate,
            duration_s=args.duration,
            steps=args.steps,
        )
        if args.window:
            show_simulation(
                tuple(zip(trace.time_s, trace.concentration, strict=True)),
                title="PYRA zone exercise",
            )
        else:
            print(
                json.dumps(
                    {
                        "status": trace.status,
                        "assumptions": trace.assumptions,
                        "points": [
                            {"time_s": t, "concentration": c}
                            for t, c in zip(trace.time_s, trace.concentration, strict=True)
                        ],
                    }
                )
            )
        return
    if args.command in {None, "demo"}:
        args = argparse.Namespace(initial=1.0, rate=0.5, duration=4.0, steps=5, window=False)
    points = simulate_decay(args.initial, args.rate, args.duration, steps=args.steps)
    if args.window:
        show_simulation(points, title="PYRA simulation")
    else:
        print(json.dumps([{"time": time, "value": value} for time, value in points]))
