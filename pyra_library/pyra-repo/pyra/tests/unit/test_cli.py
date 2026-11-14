"""P12 beginner CLI contracts."""

import json

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
