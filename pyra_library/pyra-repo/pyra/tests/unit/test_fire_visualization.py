from __future__ import annotations

from types import SimpleNamespace

from pyrakit import show_fire_simulation
from pyrakit.service import fire_visualization


class FakeWidget:
    _next_id = 0
    texts: list[str] = []

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    def __getattr__(self, name: str):
        if name.startswith("create_"):
            def create(*args: object, **kwargs: object) -> int:
                FakeWidget._next_id += 1
                text = kwargs.get("text")
                if isinstance(text, str):
                    FakeWidget.texts.append(text)
                return FakeWidget._next_id

            return create
        return lambda *args, **kwargs: None


def test_fire_visualization_uses_pyra_trace_and_discloses_model_scope(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run_fire_test(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            trace=SimpleNamespace(
                time_s=(0.0, 1.0, 2.0),
                concentration=(0.21, 0.20, 0.19),
            )
        )

    fake_tk = SimpleNamespace(Tk=FakeWidget, Canvas=FakeWidget)
    monkeypatch.setitem(__import__("sys").modules, "tkinter", fake_tk)
    monkeypatch.setattr(fire_visualization, "run_fire_test", fake_run_fire_test)
    FakeWidget.texts.clear()

    show_fire_simulation(oxygen_fraction=0.2, duration_s=2.0)

    assert captured["oxygen_fraction"] == 0.2
    assert captured["duration_s"] == 2.0
    assert "WHY THIS DEMO IS LIGHTWEIGHT" in FakeWidget.texts
    assert any("not a 3D fire solver" in text for text in FakeWidget.texts)
