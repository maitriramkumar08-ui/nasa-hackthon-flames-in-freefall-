"""S0 calorimetry transforms with uncertainty propagation.

The formulas follow the oxygen-consumption and enthalpy-balance signatures in
the architecture guide.  The oxygen energy equivalence is always supplied by
the caller; PYRA deliberately does not hide a universal constant.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
from scipy.special import ndtri  # type: ignore[import-untyped]
from scipy.stats import qmc  # type: ignore[import-untyped]

from pyrakit.provenance.status import Quantity
from pyrakit.units import quantity


def _value(item: Quantity, target: str) -> float:
    converted = quantity(item.value, item.unit).to(target)
    return float(converted.magnitude)


def _uncertainty(item: Quantity, target: str) -> float | None:
    if item.u is None:
        return None
    uncertainty = quantity(item.u, item.unit).to(target)
    return float(uncertainty.magnitude)


def _canonical(item: Quantity, target: str) -> Quantity:
    return Quantity.derive(
        _value(item, target), target, _uncertainty(item, target), item.u_kind,
        parents=[item], activity="units.convert", max_input_status=item.status,
    ) if item.unit != target else item


def _sample_result(
    function: Callable[[tuple[float, ...]], float],
    inputs: list[Quantity],
    *,
    output_unit: str,
    n: int,
    seed: int,
    activity: str,
) -> Quantity:
    """Physics-local Sobol propagation, keeping layer 1 independent of pyrakit.uq."""
    if n < 2 or any(item.u is None for item in inputs):
        raise ValueError("calorimetry propagation needs n >= 2 and known uncertainties")

    def sample_value(item: Quantity, probability: float) -> float:
        if item.u is None:
            raise ValueError("calorimetry propagation needs known uncertainties")
        return float(item.value) + float(item.u) * float(ndtri(probability))

    exponent = max(1, math.ceil(math.log2(n)))
    sampler = qmc.Sobol(d=len(inputs), scramble=True, seed=seed)
    cube = np.clip(sampler.random_base2(exponent)[:n], np.finfo(float).eps, 1 - np.finfo(float).eps)
    samples: list[tuple[float, ...]] = [
        tuple(
            sample_value(item, float(prob))
            for item, prob in zip(inputs, row, strict=False)
        )
        for row in cube
    ]
    values = np.asarray([function(row) for row in samples], dtype=float)
    if not np.all(np.isfinite(values)):
        raise ValueError("calorimetry function returned a non-finite sample")
    return Quantity.derive(
        float(np.mean(values)), output_unit, float(np.std(values, ddof=1)), "type_a",
        parents=inputs, activity=activity, params={"n": n, "seed": seed},
    )


def hrr_oxygen_consumption(
    o2_in: Quantity,
    o2_out: Quantity,
    mass_flow: Quantity,
    e_per_kg_o2: Quantity,
    *,
    n: int = 4096,
    seed: int = 0,
) -> Quantity:
    """Return heat-release rate from oxygen consumption.

    Formula: ``(Y_O2,in - Y_O2,out) * m_dot * E_O2``.  See the architecture
    guide section 17.2; ``E_O2`` is an explicit input because its accepted
    literature value is a human decision.
    """
    o2_in = _canonical(o2_in, "dimensionless")
    o2_out = _canonical(o2_out, "dimensionless")
    mass_flow = _canonical(mass_flow, "kg / s")
    e_per_kg_o2 = _canonical(e_per_kg_o2, "J / kg")
    parents = [o2_in, o2_out, mass_flow, e_per_kg_o2]
    return _sample_result(
        lambda x: (x[0] - x[1]) * x[2] * x[3],
        parents,
        output_unit="W",
        n=n,
        seed=seed,
        activity="physics.hrr_oxygen_consumption",
    )


def hrr_enthalpy_balance(
    t_in: Quantity,
    t_out: Quantity,
    mass_flow: Quantity,
    cp: Quantity,
    loss_model: Callable[[float], float] | None = None,
) -> Quantity:
    """Return ``m_dot * cp * (T_out - T_in)`` minus an optional loss term.

    The loss callable receives the uncorrected heat-release rate in watts and
    must return watts.  No default loss model is assumed.
    """
    t_in = _canonical(t_in, "K")
    t_out = _canonical(t_out, "K")
    mass_flow = _canonical(mass_flow, "kg / s")
    cp = _canonical(cp, "J / kg / K")
    value = _value(mass_flow, "kg / s") * _value(cp, "J / kg / K") * (
        _value(t_out, "K") - _value(t_in, "K")
    )
    if loss_model is not None:
        value -= float(loss_model(value))
    return Quantity.derive(
        value, "W", None, "unknown", parents=[t_in, t_out, mass_flow, cp],
        activity="physics.hrr_enthalpy_balance",
    )


def species_generation(c_in: Quantity, c_out: Quantity, mass_flow: Quantity) -> Quantity:
    """Return a species mass source rate: ``(c_out - c_in) * m_dot``."""
    c_in = _canonical(c_in, "dimensionless")
    c_out = _canonical(c_out, "dimensionless")
    mass_flow = _canonical(mass_flow, "kg / s")
    value = (_value(c_out, "dimensionless") - _value(c_in, "dimensionless")) * _value(
        mass_flow, "kg / s"
    )
    return Quantity.derive(
        value, "kg / s", None, "unknown", parents=[c_in, c_out, mass_flow],
        activity="physics.species_generation",
    )


__all__ = ["hrr_enthalpy_balance", "hrr_oxygen_consumption", "species_generation"]
