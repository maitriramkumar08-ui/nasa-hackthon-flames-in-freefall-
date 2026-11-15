"""The Fire Playground: change a scenario, run it, and see where the picture came from.

The Playground can show three different kinds of thing, and they are never mixed silently:

* a **schematic** flame, which is a drawing and responds to nothing;
* the **simplified learning model**, PYRA's well-mixed oxygen balance, which uses only
  starting oxygen, air exchange, oxygen sink rate and duration;
* **solver output** from an external engine reached through
  :class:`~pyra.adapters.ExternalEngineAdapter`.

Every view carries a :class:`~pyra.service.scenario_inputs.ViewSource` banner saying which
of the three it is. The schematic is replaced by real geometry only when an engine actually
returns a flame front.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread

from pyra.physics.zone import ZoneTrace, simulate_zone
from pyra.service.scenario_inputs import PRESETS, TEACHING_EXAMPLE, FireScenario, ViewSource
from pyra.service.simple import show_simulation
from pyra.simulation import SimulationOutput


@dataclass(frozen=True)
class PlaybackTimeline:
    """Maps a playback position onto the samples of a run, for scrubbing a time slider.

    Kept free of any GUI toolkit so the stepping logic can be tested on its own.
    """

    times_s: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.times_s) < 2:
            raise ValueError("a timeline needs at least two samples")
        pairs = zip(self.times_s, self.times_s[1:], strict=False)
        if any(later <= earlier for earlier, later in pairs):
            raise ValueError("timeline samples must increase strictly")

    @property
    def frames(self) -> int:
        return len(self.times_s)

    @property
    def duration_s(self) -> float:
        return self.times_s[-1] - self.times_s[0]

    def index_at(self, time_s: float) -> int:
        """The frame nearest a wall-clock position, clamped to the ends of the run."""
        if not math.isfinite(time_s):
            raise ValueError("time_s must be finite")
        return min(range(self.frames), key=lambda index: abs(self.times_s[index] - time_s))

    def step(self, index: int, delta: int = 1, *, loop: bool = True) -> int:
        """Advance a frame index, wrapping at the end when looping."""
        if self.frames == 0:  # pragma: no cover - forbidden by __post_init__
            return 0
        moved = index + delta
        if loop:
            return moved % self.frames
        return max(0, min(self.frames - 1, moved))


@dataclass(frozen=True)
class FireTestRun:
    """One reproducible run of the simplified learning model.

    ``view_source`` is always ``LEARNING_MODEL``: this object never holds solver output.
    An engine run is a :class:`~pyra.simulation.SimulationOutput` instead, which carries
    the engine's identity and its own assumptions.
    """

    scenario: FireScenario
    trace: ZoneTrace
    model_name: str = "PYRA single-zone learning model"
    view_source: ViewSource = ViewSource.LEARNING_MODEL

    @property
    def status(self) -> str:
        return self.trace.status

    def summary(self) -> str:
        """A short plain-text summary for a beginner script."""
        return (
            f"{self.model_name} ({self.status})\n"
            f"View source: {self.view_source.headline}\n"
            f"Fuel label: {self.scenario.fuel}\n"
            f"Environment: gravity={self.scenario.gravity_g:g} g, "
            f"oxygen={self.scenario.oxygen_fraction:g}, "
            f"pressure={self.scenario.pressure_kpa:g} kPa, "
            f"temperature={self.scenario.temperature_k:g} K\n"
            f"Oxygen fraction: {self.trace.concentration[0]:.4f} to "
            f"{self.trace.concentration[-1]:.4f}\n"
            "Scope: simplified well-mixed oxygen balance; not a flame solver or safety prediction."
        )

    def timeline(self) -> PlaybackTimeline:
        return PlaybackTimeline(tuple(self.trace.time_s))

    def show(self) -> None:
        """Open the oxygen trace in a graph window."""
        show_simulation(
            tuple(zip(self.trace.time_s, self.trace.concentration, strict=True)),
            title="PYRA learning simulation",
        )

    def save(self, path: str | Path) -> Path:
        """Save inputs, assumptions, and the simulated trace as readable JSON."""
        destination = Path(path)
        payload = {
            "model": self.model_name,
            "status": self.status,
            "view_source": self.view_source.value,
            "scope": "educational oxygen balance; not a flame solver or safety prediction",
            "scenario": {
                "fuel": self.scenario.fuel,
                "gravity_g": self.scenario.gravity_g,
                "oxygen_fraction": self.scenario.oxygen_fraction,
                "pressure_kpa": self.scenario.pressure_kpa,
                "temperature_k": self.scenario.temperature_k,
                "air_exchange_per_s": self.scenario.air_exchange_per_s,
                "oxygen_sink_per_s": self.scenario.oxygen_sink_per_s,
                "duration_s": self.scenario.duration_s,
                "diluent": self.scenario.diluent,
                "flow_mode": self.scenario.flow_mode,
                "flow_velocity_m_s": self.scenario.flow_velocity_m_s,
                "configuration": self.scenario.configuration,
                "length_scale_m": self.scenario.length_scale_m,
                "source_note": self.scenario.source_note,
            },
            "assumptions": list(self.trace.assumptions),
            "points": [
                {"time_s": time_s, "oxygen_fraction": oxygen}
                for time_s, oxygen in zip(self.trace.time_s, self.trace.concentration, strict=True)
            ],
        }
        destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return destination


def simulate_fire_scenario(scenario: FireScenario) -> ZoneTrace:
    """Run the limited oxygen-concentration calculation for one teaching scenario.

    Fuel, gravity, pressure and temperature remain descriptive scenario values. They do
    not alter this oxygen-only equation because PYRA has no validated fire-flame solver.
    """
    return simulate_zone(
        initial_concentration=scenario.oxygen_fraction,
        inlet_concentration=scenario.oxygen_fraction,
        exchange_rate_per_s=scenario.air_exchange_per_s,
        source_rate_per_s=-scenario.oxygen_sink_per_s,
        duration_s=scenario.duration_s,
        steps=61,
    )


def run_fire_test(
    *,
    fuel: str = "PMMA (example fuel)",
    gravity_g: float = 1.0,
    oxygen_fraction: float = 0.21,
    pressure_kpa: float = 101.3,
    temperature_k: float = 293.15,
    air_exchange_per_s: float = 0.02,
    oxygen_sink_per_s: float = 0.001,
    duration_s: float = 60.0,
    **scenario_fields: object,
) -> FireTestRun:
    """Run PYRA's built-in learning simulation in one call.

    This is a convenience wrapper around the simple oxygen-zone equation, not a
    flame-resolved fire model, and it does not run an external engine. To drive a real
    engine, build a scenario with :meth:`FireScenario.to_scenario` and send it through
    :class:`~pyra.adapters.ExternalEngineAdapter`.

    Extra keyword arguments are passed to :class:`FireScenario`, so the flow, geometry and
    ignition fields can be recorded here too even though the learning model ignores them.
    """
    scenario = FireScenario(
        fuel=fuel,
        gravity_g=gravity_g,
        oxygen_fraction=oxygen_fraction,
        pressure_kpa=pressure_kpa,
        temperature_k=temperature_k,
        air_exchange_per_s=air_exchange_per_s,
        oxygen_sink_per_s=oxygen_sink_per_s,
        duration_s=duration_s,
        **scenario_fields,  # type: ignore[arg-type]
    )
    return FireTestRun(scenario=scenario, trace=simulate_fire_scenario(scenario))


# -- the window -------------------------------------------------------------------------

FORM_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("fuel", "Fuel label", "PMMA (example fuel)"),
    ("gravity_g", "Gravity (multiple of Earth g)", "1.0"),
    ("oxygen_fraction", "Oxygen mole fraction (0-1)", "0.21"),
    ("pressure_kpa", "Pressure (kPa)", "101.3"),
    ("temperature_k", "Temperature (K)", "293.15"),
    ("diluent", "Diluent gas", "nitrogen"),
    ("flow_mode", "Flow mode", "quiescent"),
    ("flow_velocity_m_s", "Flow velocity (m/s, blank if none)", ""),
    ("configuration", "Configuration", "concurrent"),
    ("length_scale_m", "Length scale (m)", "0.02"),
    ("fuel_thickness_m", "Fuel thickness (m, blank if none)", ""),
    ("ignition_power_w", "Ignition power (W, blank if none)", ""),
    ("ignition_duration_s", "Ignition duration (s, blank if none)", ""),
    ("air_exchange_per_s", "Air exchange rate (1/s, learning model)", "0.02"),
    ("oxygen_sink_per_s", "Oxygen sink rate (1/s, learning model)", "0.001"),
    ("duration_s", "Duration (s)", "60"),
)

TEXT_FIELDS = frozenset({"fuel", "diluent", "flow_mode", "configuration"})
OPTIONAL_FIELDS = frozenset(
    {"flow_velocity_m_s", "fuel_thickness_m", "ignition_power_w", "ignition_duration_s"}
)


def scenario_from_form(values: dict[str, str]) -> FireScenario:
    """Build a validated :class:`FireScenario` from the raw strings a form holds.

    Blank optional fields become ``None`` rather than zero, because "not set" and "zero"
    are different statements about an experiment.
    """
    fields: dict[str, object] = {}
    for name, raw in values.items():
        text = raw.strip()
        if name in TEXT_FIELDS:
            fields[name] = text
            continue
        if not text:
            if name in OPTIONAL_FIELDS:
                fields[name] = None
                continue
            raise ValueError(f"{name} needs a value")
        try:
            fields[name] = float(text)
        except ValueError:
            raise ValueError(f"{name} must be a number, got {raw!r}") from None
    return FireScenario(**fields)  # type: ignore[arg-type]


def fire_playground() -> None:  # pragma: no cover - interactive window
    """Open the Playground window.

    Requires Tk, which ships with most CPython installations. The window is not covered by
    the test suite; the logic it calls (:func:`scenario_from_form`, :class:`FireScenario`,
    :class:`PlaybackTimeline`) is tested directly.
    """
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("PYRA Fire Playground")
    root.geometry("1120x760")
    root.minsize(960, 680)

    panel = ttk.Frame(root, padding=14)
    panel.pack(fill="both", expand=True)
    panel.columnconfigure(1, weight=1)
    panel.rowconfigure(2, weight=1)

    ttk.Label(panel, text="Fire Playground", font=("Segoe UI", 18, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w"
    )

    banner = tk.StringVar()
    banner_detail = tk.StringVar()
    banner_frame = ttk.LabelFrame(panel, text="What you are looking at", padding=8)
    banner_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 12))
    ttk.Label(banner_frame, textvariable=banner, font=("Segoe UI", 11, "bold")).pack(anchor="w")
    ttk.Label(banner_frame, textvariable=banner_detail, wraplength=1040).pack(anchor="w")

    def set_view(source: ViewSource, extra: str = "") -> None:
        banner.set(source.headline)
        banner_detail.set(f"{source.explanation} {extra}".strip())

    set_view(ViewSource.SCHEMATIC, "Choose settings, then run a scenario.")

    # -- scenario form
    form = ttk.LabelFrame(panel, text="Scenario", padding=10)
    form.grid(row=2, column=0, sticky="nsw", padx=(0, 12))
    fields: dict[str, tk.StringVar] = {}
    for row, (key, label, default) in enumerate(FORM_FIELDS):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=2)
        variable = tk.StringVar(value=default)
        fields[key] = variable
        entry = ttk.Entry(form, textvariable=variable, width=26)
        entry.grid(row=row, column=1, sticky="ew", pady=2)

    preset_row = len(FORM_FIELDS)
    ttk.Label(form, text="Preset").grid(row=preset_row, column=0, sticky="w", pady=(8, 2))
    preset = tk.StringVar(value="Earth lab example")
    preset_box = ttk.Combobox(form, textvariable=preset, values=tuple(PRESETS), state="readonly")
    preset_box.grid(row=preset_row, column=1, sticky="ew", pady=(8, 2))

    def apply_preset(_event: object = None) -> None:
        chosen = PRESETS[preset.get()]
        for name in fields:
            value = getattr(chosen, name, None)
            fields[name].set("" if value is None else str(value))

    preset_box.bind("<<ComboboxSelected>>", apply_preset)
    ttk.Label(
        form, text=f"Presets are {TEACHING_EXAMPLE}.", wraplength=300, foreground="#555"
    ).grid(row=preset_row + 1, column=0, columnspan=2, sticky="w", pady=(4, 8))

    # -- engine configuration
    engine_frame = ttk.LabelFrame(form, text="External engine (optional)", padding=8)
    engine_frame.grid(row=preset_row + 2, column=0, columnspan=2, sticky="ew", pady=(4, 8))
    engine_path = tk.StringVar()
    ttk.Label(engine_frame, text="Executable").grid(row=0, column=0, sticky="w")
    ttk.Entry(engine_frame, textvariable=engine_path, width=24).grid(row=0, column=1, sticky="ew")
    ttk.Label(
        engine_frame,
        text="Leave blank to use the simplified learning model.",
        wraplength=280,
        foreground="#555",
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

    # -- view area
    visual = ttk.Frame(panel)
    visual.grid(row=2, column=1, sticky="nsew")
    visual.columnconfigure(0, weight=1)
    visual.rowconfigure(2, weight=1)

    flame = tk.Canvas(visual, width=320, height=170, background="#202638", highlightthickness=0)
    flame.grid(row=0, column=0, sticky="ew")
    graph = tk.Canvas(visual, height=280, background="white", highlightthickness=1)
    graph.grid(row=2, column=0, sticky="nsew", pady=(10, 0))

    status = tk.StringVar(value="Ready.")
    ttk.Label(visual, textvariable=status, wraplength=700).grid(row=3, column=0, sticky="w", pady=6)

    timeline_row = ttk.Frame(visual)
    timeline_row.grid(row=4, column=0, sticky="ew")
    timeline_row.columnconfigure(1, weight=1)
    ttk.Label(timeline_row, text="Time").grid(row=0, column=0, sticky="w")
    position = tk.DoubleVar(value=0.0)
    slider = ttk.Scale(timeline_row, from_=0.0, to=1.0, variable=position, orient="horizontal")
    slider.grid(row=0, column=1, sticky="ew", padx=8)
    frame_label = tk.StringVar(value="--")
    ttk.Label(timeline_row, textvariable=frame_label, width=22).grid(row=0, column=2, sticky="e")

    state: dict[str, object] = {"output": None, "timeline": None}
    pending_cancel: list[Event] = []  # holds at most the one in-flight engine run

    def draw_schematic_flame(note: str) -> None:
        flame.delete("all")
        flame.create_oval(136, 70, 184, 156, fill="#ff8c32", outline="")
        flame.create_oval(147, 94, 173, 156, fill="#ffe46b", outline="")
        flame.create_text(160, 18, text=note, fill="white", font=("Segoe UI", 10))

    def draw_front(output: SimulationOutput, index: int) -> None:
        """Draw the engine's own flame-front position, replacing the schematic."""
        flame.delete("all")
        front = output.flame_front
        if front is None:
            draw_schematic_flame("engine reported no flame geometry")
            return
        span = max(front.position_m) or 1.0
        x = 20 + (front.position_m[index] / span) * 280
        flame.create_line(20, 150, 300, 150, fill="#6f7a99")
        flame.create_oval(x - 12, 108, x + 12, 152, fill="#ff8c32", outline="")
        flame.create_text(160, 18, text="solver flame front", fill="white", font=("Segoe UI", 10))
        flame.create_text(
            160,
            40,
            text=f"{front.position_m[index]:.4g} m",
            fill="#cfd6ee",
            font=("Segoe UI", 9),
        )

    def plot(points: list[tuple[float, float]], y_label: str, highlight: int | None = None) -> None:
        graph.delete("all")
        width = max(graph.winfo_width(), 460)
        height = max(graph.winfo_height(), 240)
        pad = 48
        xs = [x for x, _ in points]
        ys = [y for _, y in points]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        if x_max == x_min:
            x_max = x_min + 1.0
        if y_max == y_min:
            y_max = y_min + 1.0
        graph.create_line(pad, pad - 10, pad, height - pad, fill="#333")
        graph.create_line(pad, height - pad, width - pad + 10, height - pad, fill="#333")
        graph.create_text(pad, pad - 22, text=y_label, anchor="w")
        graph.create_text(width - pad, height - 14, text="time (s)", anchor="e")

        def project(x: float, y: float) -> tuple[float, float]:
            px = pad + (x - x_min) / (x_max - x_min) * (width - 2 * pad)
            py = height - pad - (y - y_min) / (y_max - y_min) * (height - 2 * pad)
            return px, py

        coordinates = [project(x, y) for x, y in points]
        graph.create_line(
            *[value for point in coordinates for value in point], fill="#1769aa", width=3
        )
        if highlight is not None:
            hx, hy = coordinates[highlight]
            graph.create_oval(hx - 5, hy - 5, hx + 5, hy + 5, fill="#d1495b", outline="")

    def refresh_frame(_event: object = None) -> None:
        output = state.get("output")
        timeline = state.get("timeline")
        if not isinstance(output, SimulationOutput) or not isinstance(timeline, PlaybackTimeline):
            return
        index = timeline.index_at(position.get() * timeline.duration_s + timeline.times_s[0])
        channel_name = next(iter(output.channels))
        channel = output.channel(channel_name)
        plot(
            list(zip(output.time_s, channel.values, strict=True)),
            channel.label,
            highlight=index,
        )
        draw_front(output, index)
        frame_label.set(f"t = {output.time_s[index]:.3g} s  ({index + 1}/{timeline.frames})")

    slider.configure(command=lambda _value: refresh_frame())

    def run_learning_model(scenario: FireScenario) -> None:
        trace = simulate_fire_scenario(scenario)
        state["output"] = None
        state["timeline"] = None
        draw_schematic_flame("schematic only")
        plot(list(zip(trace.time_s, trace.concentration, strict=True)), "O2 fraction [-]")
        frame_label.set(f"{len(trace.time_s)} samples")
        set_view(ViewSource.LEARNING_MODEL)
        status.set(
            f"Learning model finished. Fuel {scenario.fuel!r}, gravity {scenario.gravity_g:g} g, "
            f"pressure {scenario.pressure_kpa:g} kPa and temperature "
            f"{scenario.temperature_k:g} K were recorded but did not affect this curve."
        )

    def finish_engine_run(output: SimulationOutput) -> None:
        state["output"] = output
        state["timeline"] = PlaybackTimeline(output.time_s)
        position.set(0.0)
        refresh_frame()
        set_view(
            ViewSource.SOLVER,
            f"Engine {output.engine_version}, model card {output.model_card_id}.",
        )
        warnings = "  Engine warnings: " + "; ".join(output.warnings) if output.warnings else ""
        status.set(f"Solver run finished with {len(output.time_s)} samples.{warnings}")

    def run_engine(scenario: FireScenario, executable: str) -> None:
        from pyra.adapters import EngineCommand, EngineError, ExternalEngineAdapter
        from pyra.schema import ModelCard

        card = ModelCard(
            name=Path(executable).stem or "external-engine",
            version="unknown",
            code_hash="unknown",
            licence="unknown",
            physics_summary="Model card not supplied; this run cannot support a claim.",
        )
        adapter = ExternalEngineAdapter(card, EngineCommand(executable=executable))
        cancel = Event()
        pending_cancel.clear()
        pending_cancel.append(cancel)
        result: dict[str, object] = {}

        def work() -> None:
            try:
                result["output"] = adapter.run(
                    scenario.to_scenario("playground-run"), cancel=cancel
                )
            except (EngineError, ValueError) as error:
                result["error"] = error

        worker = Thread(target=work, daemon=True)
        worker.start()
        run_button.configure(state="disabled")
        cancel_button.configure(state="normal")
        status.set(f"Running {executable}...")

        def poll() -> None:
            if worker.is_alive():
                status.set(status.get().rstrip(".") + ".")
                root.after(200, poll)
                return
            run_button.configure(state="normal")
            cancel_button.configure(state="disabled")
            pending_cancel.clear()
            if "error" in result:
                set_view(ViewSource.SCHEMATIC, "The engine run did not finish.")
                status.set(f"Engine error: {result['error']}")
                draw_schematic_flame("no solver output")
                return
            finish_engine_run(result["output"])  # type: ignore[arg-type]

        root.after(200, poll)

    def run_scenario() -> None:
        try:
            scenario = scenario_from_form({name: var.get() for name, var in fields.items()})
        except ValueError as error:
            messagebox.showerror("Check the scenario inputs", str(error), parent=root)
            return
        executable = engine_path.get().strip()
        if executable:
            run_engine(scenario, executable)
        else:
            run_learning_model(scenario)

    def cancel_run() -> None:
        for cancel in pending_cancel:
            cancel.set()
            status.set("Cancelling the engine run...")

    buttons = ttk.Frame(form)
    buttons.grid(row=preset_row + 3, column=0, columnspan=2, sticky="ew", pady=(6, 2))
    buttons.columnconfigure((0, 1), weight=1)
    run_button = ttk.Button(buttons, text="Run scenario", command=run_scenario)
    run_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
    cancel_button = ttk.Button(buttons, text="Cancel", command=cancel_run, state="disabled")
    cancel_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))

    draw_schematic_flame("schematic only")
    root.mainloop()


__all__ = [
    "PRESETS",
    "FireScenario",
    "FireTestRun",
    "PlaybackTimeline",
    "ViewSource",
    "fire_playground",
    "run_fire_test",
    "scenario_from_form",
    "simulate_fire_scenario",
]
