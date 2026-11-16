"""Compact canvas view for PYRA's simplified fire-learning model."""

from __future__ import annotations

import math

from pyrakit.service.playground import run_fire_test


def show_fire_simulation(
    *,
    fuel: str = "PMMA (example label)",
    gravity_g: float = 1.0,
    oxygen_fraction: float = 0.21,
    pressure_kpa: float = 101.3,
    temperature_k: float = 293.15,
    air_exchange_per_s: float = 0.02,
    oxygen_sink_per_s: float = 0.001,
    duration_s: float = 60.0,
) -> None:
    """Show an animated conceptual flame alongside PYRA's oxygen trace.

    The flame is decorative, not solver output. PYRA computes only the
    well-mixed oxygen curve; this visualization is not a fire-safety prediction.
    """
    import tkinter as tk

    run = run_fire_test(
        fuel=fuel,
        gravity_g=gravity_g,
        oxygen_fraction=oxygen_fraction,
        pressure_kpa=pressure_kpa,
        temperature_k=temperature_k,
        air_exchange_per_s=air_exchange_per_s,
        oxygen_sink_per_s=oxygen_sink_per_s,
        duration_s=duration_s,
    )
    trace = run.trace
    root = tk.Tk()
    root.title("PYRA | Fire-learning simulation")
    root.geometry("1000x650")
    root.configure(background="#101827")

    canvas = tk.Canvas(
        root, width=1000, height=610, background="#101827", highlightthickness=0
    )
    canvas.pack(fill="both", expand=True)
    canvas.create_text(
        24, 24, text="PYRA FIRE-LEARNING SIMULATION",
        anchor="w", fill="#f3f6fb", font=("Segoe UI", 16, "bold"),
    )
    canvas.create_text(
        24, 51, text="Animated flame is illustrative; the plotted oxygen trace is calculated.",
        anchor="w", fill="#bdc9d9", font=("Segoe UI", 10),
    )

    # A perspective floor gives the flame a 3D-style scene without implying 3D physics.
    floor = [(80, 460), (430, 460), (350, 370), (160, 370)]
    canvas.create_polygon(*[v for point in floor for v in point],
                          fill="#19263a", outline="#64758d", width=2)
    for index in range(1, 5):
        x = 80 + index * 70
        canvas.create_line(x, 460, 160 + index * 38, 370, fill="#304158")
    for index in range(1, 4):
        y: float = 460 - index * 22
        canvas.create_line(80 + index * 35, y, 430 - index * 28, y, fill="#304158")
    canvas.create_rectangle(223, 424, 287, 448, fill="#805b42", outline="#bc916b")
    canvas.create_polygon(223, 424, 243, 410, 307, 410, 287, 424,
                          fill="#a87a55", outline="#d1a37c")
    canvas.create_line(80, 460, 80, 310, fill="#44566f", dash=(5, 5))
    canvas.create_line(430, 460, 430, 310, fill="#44566f", dash=(5, 5))

    flame_shapes = []
    flame_specs = (
        (0.0, "#e64b1b", 150, 56),
        (1.7, "#ff8c2f", 125, 43),
        (3.4, "#ffe36a", 93, 29),
    )
    for phase, color, height, half_width in flame_specs:
        shape = canvas.create_polygon(
            255, 420, 255, 420, 255, 420,
            fill=color, outline=color, smooth=True,
        )
        flame_shapes.append((shape, phase, color, height, half_width))

    chart = (535, 135, 955, 395)
    left, top, right, bottom = chart
    canvas.create_text(
        left, 112, text="OXYGEN FRACTION vs TIME",
        anchor="w", fill="#f3f6fb", font=("Segoe UI", 12, "bold"),
    )
    canvas.create_rectangle(left, top, right, bottom, fill="#172337", outline="#52647d")
    low, high = min(trace.concentration), max(trace.concentration)
    padding = max((high - low) * 0.15, 0.005)
    low, high = low - padding, high + padding
    plot_left, plot_top = left + 46, top + 20
    plot_right, plot_bottom = right - 16, bottom - 34

    for fraction in (0.0, 0.5, 1.0):
        y = plot_bottom - fraction * (plot_bottom - plot_top)
        value = low + fraction * (high - low)
        canvas.create_line(plot_left, y, plot_right, y, fill="#304158")
        canvas.create_text(
            plot_left - 8, y, text=f"{value:.3f}", anchor="e",
            fill="#bdc9d9", font=("Segoe UI", 8),
        )

    def chart_point(index: int) -> tuple[float, float]:
        x = plot_left + (plot_right - plot_left) * index / (len(trace.time_s) - 1)
        y = plot_bottom - (plot_bottom - plot_top) * (
            trace.concentration[index] - low
        ) / (high - low)
        return x, y

    line = [coordinate for i in range(len(trace.time_s)) for coordinate in chart_point(i)]
    canvas.create_line(*line, fill="#65c7d0", width=3)
    canvas.create_text(
        (plot_left + plot_right) / 2, bottom - 15,
        text=f"time (s), 0 to {trace.time_s[-1]:g}",
        fill="#bdc9d9", font=("Segoe UI", 9),
    )
    marker = canvas.create_oval(0, 0, 10, 10, fill="white", outline="")
    readout = canvas.create_text(
        left, bottom + 20, anchor="w", fill="#f3f6fb",
        font=("Segoe UI", 10, "bold"),
    )

    canvas.create_text(
        535, 465,
        text=f"Fuel label: {fuel} | Gravity: {gravity_g:g} g | "
             f"Pressure: {pressure_kpa:g} kPa | Temperature: {temperature_k:g} K",
        anchor="w", fill="#bdc9d9", font=("Segoe UI", 9),
    )
    canvas.create_text(
        535, 490,
        text=f"Air exchange: {air_exchange_per_s:g}/s | Oxygen sink: "
             f"{oxygen_sink_per_s:g}/s | Duration: {duration_s:g}s",
        anchor="w", fill="#bdc9d9", font=("Segoe UI", 9),
    )
    canvas.create_text(
        535, 535, text="WHY THIS DEMO IS LIGHTWEIGHT",
        anchor="w", fill="#f2bc62", font=("Segoe UI", 11, "bold"),
    )
    canvas.create_text(
        535, 560,
        text=(
            "PYRA solves one well-mixed oxygen equation exactly at each sample. "
            "A 3D CFD fire solver must calculate many interacting cells and physics. "
            "That makes this reduced model cheaper to run, but it cannot predict "
            "flame shape, heat, buoyancy, chemistry, or spatial gradients."
        ),
        anchor="nw", width=420, fill="#d5deea", font=("Segoe UI", 9),
    )
    canvas.create_text(
        24, 590,
        text=(
            "SIMULATED oxygen trace + conceptual flame artwork — not a "
            "3D fire solver or safety prediction."
        ),
        anchor="w", fill="#f2bc62", font=("Segoe UI", 9, "bold"),
    )

    frame = 0

    def animate() -> None:
        nonlocal frame
        phase = frame * 0.14
        for shape, offset, _color, height, half_width in flame_shapes:
            flicker = math.sin(phase + offset)
            sway = math.sin(phase * 0.7 + offset) * 9
            tip_x = 255 + sway
            tip_y = 420 - height - flicker * 9
            canvas.coords(
                shape,
                255 - half_width, 420,
                255 - half_width * 0.65, 420 - height * 0.43,
                tip_x, tip_y,
                255 + half_width * 0.65, 420 - height * 0.43,
                255 + half_width, 420,
            )
        sample = frame % len(trace.time_s)
        x, y = chart_point(sample)
        canvas.coords(marker, x - 5, y - 5, x + 5, y + 5)
        canvas.itemconfigure(
            readout,
            text=f"t = {trace.time_s[sample]:.1f} s   oxygen = "
                 f"{trace.concentration[sample]:.4f}",
        )
        frame += 1
        root.after(60, animate)

    animate()
    root.mainloop()


__all__ = ["show_fire_simulation"]
