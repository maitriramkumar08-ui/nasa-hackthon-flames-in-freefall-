"""Small standard-library CLI for first programs and local trace demos."""

from __future__ import annotations

import argparse
import json

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
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the CLI; no external services are required for the demo commands."""
    args = _parser().parse_args(argv)
    if args.command in {None, "demo"}:
        args = argparse.Namespace(initial=1.0, rate=0.5, duration=4.0, steps=5, window=False)
    points = simulate_decay(args.initial, args.rate, args.duration, steps=args.steps)
    if args.window:
        show_simulation(points, title="PYRA simulation")
    else:
        print(json.dumps([{"time": time, "value": value} for time, value in points]))
