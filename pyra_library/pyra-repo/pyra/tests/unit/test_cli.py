"""P12 beginner CLI contracts."""

import json

import pyra.cli as cli
from pyra.cli import main


def test_demo_command_prints_json(capsys) -> None:
    main(["demo"])
    output = json.loads(capsys.readouterr().out)
    assert output[0] == {"time": 0.0, "value": 1.0}
    assert len(output) == 5


def test_simulate_command_accepts_parameters(capsys) -> None:
    main(["simulate", "--initial", "2", "--rate", "1", "--duration", "2", "--steps", "3"])
    output = json.loads(capsys.readouterr().out)
    assert output[-1]["time"] == 2.0


def test_zone_command_prints_assumptions_and_trace(capsys) -> None:
    main(["zone", "--duration", "2", "--steps", "3"])
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "SIMULATED"
    assert output["points"][-1]["time_s"] == 2.0
    assert "well-mixed single zone" in output["assumptions"]


def test_playground_command_opens_gui(monkeypatch) -> None:
    opened = []
    monkeypatch.setattr(cli, "fire_playground", lambda: opened.append(True))
    main(["playground"])
    assert opened == [True]
