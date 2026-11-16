/**
 * flame-model.js: the physics behind the demo flame. No DOM, no three.js.
 * Loads as a classic <script> (sets window.PyraFlame) or with require() in Node for tests.
 *
 * Model (Phase 1): a steady laminar diffusion flame around a point source of gaseous fuel
 * (the pyrolysing sample) in a uniform oxidiser stream. All units SI unless named otherwise.
 *
 *   Conserved scalar (mixture fraction) for a point source of strength mdot in a uniform
 *   stream U, constant rho*D (classic advection-diffusion point-source solution):
 *       Z(r, theta) = mdot / (4 pi rho D r) * exp(-U r (1 - cos theta) / (2 D))
 *   theta is measured from the flow direction (theta = 0 is downstream).
 *   The flame sheet is the surface Z = Z_st (Burke-Schumann, infinitely fast chemistry):
 *       Z_st = Y_O2 / (s + Y_O2)       s = kg O2 per kg fuel
 *       T_f  = T_amb + Z_st * dHc / cp  (adiabatic, no dissociation: an upper bound)
 *   With U = 0 the flame is a sphere of radius r0 = mdot / (4 pi rho D Z_st).
 *   Nothing in the shape is prescribed: elongation, narrowing and tilt all come from U and D.
 *
 *   Convective velocity U = forced flow (along +x) + buoyant velocity (along +y, against g):
 *       u_b = sqrt(g * beta * dT * L),  beta = 1 / T_film (ideal gas),  L = r0
 *   This is the velocity scale behind the Grashof number (Gr = (u_b L / nu)^2).
 *   Gas properties are evaluated at the film temperature (T_amb + T_f) / 2:
 *       rho ideal gas, mu Sutherland (air), D_O2 = 2.0e-5 (T/293.15)^1.75 (101.325/P) m2/s.
 *
 * Known limits (stated so nobody reads more into it):
 *   - One velocity scale for the whole flame; real buoyant flow accelerates from zero at the base.
 *   - Mixed convection is a vector sum of u_b and the forced flow, not a solved flow field.
 *   - Fuel supply mdot is an input; it does not yet respond to heat feedback.
 *   - No finite-rate chemistry, radiation or heat loss, so no physical extinction yet.
 *   - Fuel properties are textbook values (Drysdale, SFPE Handbook), not from the PYRA dataset;
 *     the repository's factsheets hold no verified flame measurements to calibrate against.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PyraFlame = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const G0 = 9.80665;        // m/s2, standard gravity
  const R_U = 8.314462;      // J/(mol K)
  const CP = 1400;           // J/(kg K), mean cp of hot products over ~300-2300 K
  const D_REF = 2.0e-5;      // m2/s, O2 into N2 at 293.15 K, 101.325 kPa

  // s: kg O2 per kg fuel (complete combustion), dHc: J/kg (net). Pyrolysate treated as gas.
  const FUELS = {
    fabric: { label: 'cellulose (cotton)', s: 1.185, dHc: 16.1e6 },
    paper: { label: 'cellulose (paper)', s: 1.185, dHc: 16.1e6 },
    plastic: { label: 'PMMA', s: 1.92, dHc: 25.2e6 },
    wire: { label: 'polyethylene insulation', s: 3.43, dHc: 43.3e6 },
  };

  const DEFAULTS = { gravity: G0, flow: 0, o2: 21, pressure: 101.325, tAmb: 295, fuel: 'fabric', mdot: 0.7e-6 };
  // [min, max] accepted; values outside are clamped and reported in warnings.
  const RANGES = { gravity: [0, 50], flow: [0, 3], o2: [5, 100], pressure: [1, 500], tAmb: [150, 600], mdot: [1e-9, 1e-4] };
  const UNITS = { gravity: 'm/s2', flow: 'm/s', o2: '% vol', pressure: 'kPa', tAmb: 'K', mdot: 'kg/s' };

  function clean(input) {
    const p = {};
    const warnings = [];
    for (const k of Object.keys(RANGES)) {
      let v = input && input[k] != null ? Number(input[k]) : DEFAULTS[k];
      if (!Number.isFinite(v)) { warnings.push(`${k} was not a number; used default ${DEFAULTS[k]} ${UNITS[k]}`); v = DEFAULTS[k]; }
      const [lo, hi] = RANGES[k];
      if (v < lo || v > hi) { warnings.push(`${k} ${v} ${UNITS[k]} is outside ${lo}-${hi}; clamped`); v = Math.min(hi, Math.max(lo, v)); }
      p[k] = v;
    }
    p.fuel = input && FUELS[input.fuel] ? input.fuel : DEFAULTS.fuel;
    if (input && input.fuel && !FUELS[input.fuel]) warnings.push(`unknown fuel '${input.fuel}'; used ${p.fuel}`);
    return { p, warnings };
  }

  function gas(T, P_kPa, xO2) {
    const M = 0.032 * xO2 + 0.028 * (1 - xO2);                 // kg/mol, O2/N2 mixture
    const rho = (P_kPa * 1e3 * M) / (R_U * T);
    const mu = 1.716e-5 * Math.pow(T / 273.15, 1.5) * (273.15 + 110.4) / (T + 110.4);
    const D = D_REF * Math.pow(T / 293.15, 1.75) * (101.325 / P_kPa);
    return { T, rho, mu, nu: mu / rho, D };
  }

  // Solve ln(rq / r) = c r for r in (0, rq], rq = A / Zlevel. Newton from the left converges
  // monotonically because the residual is convex and decreasing.
  function isoRadius(rq, c) {
    if (!(c > 0)) return rq;
    let r = rq / (1 + c * rq);
    for (let i = 0; i < 40; i++) {
      const f = Math.log(rq / r) - c * r;
      const step = f / (1 / r + c);
      r += step;
      if (Math.abs(step) < 1e-10 * rq) break;
    }
    return r;
  }

  /**
   * Radius of the iso-surface Z = ratio * Z_st at n angles from downstream (theta = 0) to
   * upstream (theta = pi). ratio = 1 is the flame sheet; ratio > 1 lies on the fuel side.
   */
  function surface(state, ratio = 1, n = 33) {
    const rq = state.r0 / ratio;
    const out = new Float64Array(n);
    const k = state.U / (2 * state.D);
    for (let i = 0; i < n; i++) {
      const theta = (Math.PI * i) / (n - 1);
      out[i] = isoRadius(rq, k * (1 - Math.cos(theta)));
    }
    return out;
  }

  function solve(input) {
    const { p, warnings } = clean(input);
    const fuel = FUELS[p.fuel];
    const xO2 = p.o2 / 100;
    const yO2 = (xO2 * 32) / (xO2 * 32 + (1 - xO2) * 28);
    const Zst = yO2 / (fuel.s + yO2);
    const dT = (Zst * fuel.dHc) / CP;
    const Tf = p.tAmb + dT;
    const Tfilm = (p.tAmb + Tf) / 2;
    const film = gas(Tfilm, p.pressure, xO2);
    const amb = gas(p.tAmb, p.pressure, xO2);
    const rhoD = film.rho * film.D;
    const r0 = p.mdot / (4 * Math.PI * rhoD * Zst);
    const beta = 1 / Tfilm;
    const L = r0;
    const ub = Math.sqrt(p.gravity * beta * dT * L);
    const ux = p.flow, uy = ub;
    const U = Math.hypot(ux, uy);
    const dir = U > 0 ? [ux / U, uy / U] : [0, 1];
    const Pe = (U * L) / film.D;

    const state = { r0, U, D: film.D };
    const sheet = surface(state, 1);
    const n = sheet.length;
    let halfWidth = 0;
    for (let i = 0; i < n; i++) halfWidth = Math.max(halfWidth, sheet[i] * Math.sin((Math.PI * i) / (n - 1)));
    const downstream = sheet[0], upstream = sheet[n - 1];

    return {
      inputs: { ...p, fuelLabel: fuel.label },
      warnings,
      properties: { yO2, Zst, s: fuel.s, dHc: fuel.dHc, cp: CP, film, ambient: amb, rhoD, beta },
      results: {
        gravity: p.gravity,
        gravityG: p.gravity / G0,
        flameTemp: Tf,                      // K, adiabatic estimate
        deltaT: dT,
        r0,                                  // m, quiescent flame radius
        buoyantVelocity: ub,                 // m/s
        forcedVelocity: ux,                  // m/s
        convectiveVelocity: U,               // m/s
        direction: dir,                      // unit vector (x along flow, y up)
        peclet: Pe,
        buoyantShare: U > 0 ? ub / (ub + ux) : 0,
        length: downstream + upstream,       // m, along the convective direction
        width: 2 * halfWidth,                // m, across it
        upstreamStandoff: upstream,          // m
        heatRelease: p.mdot * fuel.dHc,      // W, complete combustion of the supplied fuel
        // Buoyant flicker, puffing correlation f = 1.5 D^-0.5 Hz at 1 g (D in m), scaled as sqrt(g/D).
        flickerHz: p.gravity > 0 ? 0.479 * Math.sqrt(p.gravity / (2 * r0)) : 0,
      },
      state,
      sheet,
    };
  }

  return { G0, FUELS, DEFAULTS, RANGES, UNITS, solve, surface, gas, isoRadius };
});
