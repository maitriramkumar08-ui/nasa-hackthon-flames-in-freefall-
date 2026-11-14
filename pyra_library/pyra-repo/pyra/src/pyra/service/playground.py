"""Interactive, educational stationary-flame scenario playground.

The flame drawing is a schematic. The plotted line is only the single-zone oxygen
concentration model; fuel, gravity, pressure and temperature are recorded for
exploration but are not inputs to that simplified concentration equation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from pyra.physics.zone import ZoneTrace, simulate_zone


@dataclass(frozen=True)
class FireScenario:
    """Learner-entered environment for a stationary-flame concept sketch."""

    fuel: str = "PMMA (example fuel)"
    gravity_g: float = 1.0
    oxygen_fraction: float = 0.21
    pressure_kpa: float = 101.3
    temperature_k: float = 293.15
    air_exchange_per_s: float = 0.02
    oxygen_sink_per_s: float = 0.001
    duration_s: float = 60.0


PRESETS: dict[str, FireScenario] = {
    "Earth lab example": FireScenario(),
    "Microgravity thought experiment": FireScenario(gravity_g=0.00001),
    "Low-oxygen thought experiment": FireScenario(oxygen_fraction=0.17),
}


def simulate_fire_scenario(scenario: FireScenario) -> ZoneTrace:
    """Run the limited oxygen-concentration calculation for one teaching scenario.

    Fuel, gravity, pressure and temperature remain descriptive scenario values. They do
    not alter this oxygen-only equation because PYRA has no validated fire-flame solver.
    """
    if not scenario.fuel.strip():
        raise ValueError("fuel label must not be empty")
    environment = (
        scenario.gravity_g,
        scenario.oxygen_fraction,
        scenario.pressure_kpa,
        scenario.temperature_k,
        scenario.air_exchange_per_s,
        scenario.oxygen_sink_per_s,
    )
    if not all(math.isfinite(value) for value in environment):
        raise ValueError("environment settings must be finite numbers")
    if scenario.gravity_g < 0 or scenario.pressure_kpa <= 0 or scenario.temperature_k <= 0:
        raise ValueError("gravity must be non-negative; pressure and temperature must be positive")
    if scenario.air_exchange_per_s < 0 or scenario.oxygen_sink_per_s < 0:
        raise ValueError("air exchange and oxygen sink rates must be non-negative")
    return simulate_zone(
        initial_concentration=scenario.oxygen_fraction,
        inlet_concentration=scenario.oxygen_fraction,
        exchange_rate_per_s=scenario.air_exchange_per_s,
        source_rate_per_s=-scenario.oxygen_sink_per_s,
        duration_s=scenario.duration_s,
        steps=61,
    )


def fire_playground() -> None:
    """Open a beginner GUI for changing a stationary-fire scenario and plotting oxygen.

    The static flame is an illustration, not a computed flame shape. Environmental
    settings are shown for scenario exploration; only oxygen, ventilation, oxygen-sink
    rate and duration enter the plotted single-zone calculation.
    """
    import tkinter as tk
    from tkinter import messagebox, ttk

    root = tk.Tk()
    root.title("PYRA Fire Playground — learning model")
    root.geometry("940x680")
    root.minsize(820, 600)

    panel = ttk.Frame(root, padding=14)
    panel.pack(fill="both", expand=True)
    ttk.Label(panel, text="Fire Playground", font=("Segoe UI", 18, "bold")).grid(
        row=0, column=0, columnspan=2, sticky="w"
    )
    ttk.Label(
        panel,
        text=(
            "Concept sketch only: the flame is a static illustration. The graph shows a "
            "simplified well-mixed oxygen balance, not a fire or flame prediction."
        ),
        wraplength=870,
    ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 12))

    form = ttk.LabelFrame(panel, text="Scenario settings", padding=10)
    form.grid(row=2, column=0, sticky="nsw", padx=(0, 12))
    fields: dict[str, tk.StringVar] = {}
    definitions = [
        ("fuel", "Fuel label", "PMMA (example fuel)"),
        ("gravity_g", "Gravity (g)", "1.0"),
        ("oxygen_fraction", "Oxygen fraction (0–1)", "0.21"),
        ("pressure_kpa", "Pressure (kPa)", "101.3"),
        ("temperature_k", "Temperature (K)", "293.15"),
        ("air_exchange_per_s", "Air exchange rate (1/s)", "0.02"),
        ("oxygen_sink_per_s", "Oxygen sink rate (1/s)", "0.001"),
        ("duration_s", "Duration (s)", "60"),
    ]
    for row, (key, label, default) in enumerate(definitions):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
        variable = tk.StringVar(value=default)
        fields[key] = variable
        ttk.Entry(form, textvariable=variable, width=24).grid(
            row=row, column=1, sticky="ew", pady=3
        )

    ttk.Label(form, text="Preset").grid(row=len(definitions), column=0, sticky="w", pady=3)
    preset = tk.StringVar(value="Earth lab example")
    preset_box = ttk.Combobox(form, textvariable=preset, values=tuple(PRESETS), state="readonly")
    preset_box.grid(row=len(definitions), column=1, sticky="ew", pady=3)

    def apply_preset(_event: tk.Event[tk.Misc] | None = None) -> None:
        selected = PRESETS[preset.get()]
        for name in fields:
            value = getattr(selected, name)
            fields[name].set(str(value))

    preset_box.bind("<<ComboboxSelected>>", apply_preset)

    visual = ttk.Frame(panel)
    visual.grid(row=2, column=1, sticky="nsew")
    visual.columnconfigure(0, weight=1)
    visual.rowconfigure(1, weight=1)
    ttk.Label(visual, text="Static flame illustration", font=("Segoe UI", 11, "bold")).grid(
        row=0, column=0
    )
    flame = tk.Canvas(visual, width=300, height=180, background="#202638", highlightthickness=0)
    flame.grid(row=1, column=0, sticky="ew", pady=(6, 12))
    flame.create_oval(126, 76, 174, 160, fill="#ff8c32", outline="")
    flame.create_oval(137, 98, 163, 160, fill="#ffe46b", outline="")
    flame.create_text(150, 20, text="schematic only", fill="white", font=("Segoe UI", 10))

    graph = tk.Canvas(visual, height=260, background="white", highlightthickness=1)
    graph.grid(row=2, column=0, sticky="nsew")
    note = tk.StringVar(value="Choose settings, then click Run scenario.")
    ttk.Label(visual, textvariable=note, wraplength=560).grid(row=3, column=0, sticky="w", pady=8)

    def run_scenario() -> None:
        try:
            scenario = FireScenario(
                fuel=fields["fuel"].get(),
                gravity_g=float(fields["gravity_g"].get()),
                oxygen_fraction=float(fields["oxygen_fraction"].get()),
                pressure_kpa=float(fields["pressure_kpa"].get()),
                temperature_k=float(fields["temperature_k"].get()),
                air_exchange_per_s=float(fields["air_exchange_per_s"].get()),
                oxygen_sink_per_s=float(fields["oxygen_sink_per_s"].get()),
                duration_s=float(fields["duration_s"].get()),
            )
            trace = simulate_fire_scenario(scenario)
        except (TypeError, ValueError) as error:
            messagebox.showerror("Check the scenario inputs", str(error), parent=root)
            return
        graph.delete("all")
        width = max(graph.winfo_width(), 420)
        height = max(graph.winfo_height(), 220)
        pad = 42
        graph.create_line(pad, pad, pad, height - pad, fill="#333")
        graph.create_line(pad, height - pad, width - pad, height - pad, fill="#333")
        graph.create_text(pad, pad - 12, text="O₂ fraction", anchor="w")
        graph.create_text(width - pad, height - 12, text="time (s)", anchor="e")
        coordinates = [
            (
                pad + t / scenario.duration_s * (width - 2 * pad),
                height - pad - c * (height - 2 * pad),
            )
            for t, c in zip(trace.time_s, trace.concentration, strict=True)
        ]
        graph.create_line(
            *[coordinate for point in coordinates for coordinate in point], fill="#1769aa", width=3
        )
        note.set(
            f"Fuel: {scenario.fuel} | gravity: {scenario.gravity_g:g} g | "
            f"pressure: {scenario.pressure_kpa:g} kPa | temperature: {scenario.temperature_k:g} K. "
            "These are displayed scenario settings; they do not drive the oxygen-only model."
        )

    ttk.Button(form, text="Run scenario", command=run_scenario).grid(
        row=len(definitions) + 1, column=0, columnspan=2, sticky="ew", pady=(10, 2)
    )
    panel.columnconfigure(1, weight=1)
    panel.rowconfigure(2, weight=1)
    root.mainloop()


__all__ = ["FireScenario", "PRESETS", "fire_playground", "simulate_fire_scenario"]
