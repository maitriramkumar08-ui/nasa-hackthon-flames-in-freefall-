// node --test tests/   (Node 18+, no packages)
const test = require('node:test');
const assert = require('node:assert/strict');
const F = require('../demo/flame-model.js');

const G = { micro: 0, moon: 1.62, mars: 3.71, earth: 9.81 };
const run = (o) => F.solve(o).results;

test('quiescent microgravity flame is a sphere of radius r0', () => {
  const out = F.solve({ gravity: 0, flow: 0 });
  assert.equal(out.results.buoyantVelocity, 0);
  assert.equal(out.results.peclet, 0);
  for (const r of out.sheet) assert.ok(Math.abs(r - out.results.r0) < 1e-12);
  assert.ok(Math.abs(out.results.length - out.results.width) < 1e-12);
});

test('r0 matches the point-source formula mdot / (4 pi rho D Z_st)', () => {
  const out = F.solve({ gravity: 0 });
  const { rhoD, Zst } = out.properties;
  assert.ok(Math.abs(out.results.r0 - out.inputs.mdot / (4 * Math.PI * rhoD * Zst)) < 1e-15);
});

test('iso-surface radius satisfies its defining equation', () => {
  for (const c of [1, 50, 500, 5000]) {
    const rq = 0.005, r = F.isoRadius(rq, c);
    assert.ok(r > 0 && r <= rq);
    assert.ok(Math.abs(Math.log(rq / r) - c * r) < 1e-9);
  }
});

test('buoyancy grows monotonically with gravity, follows sqrt(g), and narrows the flame', () => {
  const rs = [G.micro, G.moon, G.mars, G.earth].map((g) => run({ gravity: g }));
  for (let i = 1; i < rs.length; i++) {
    assert.ok(rs[i].buoyantVelocity > rs[i - 1].buoyantVelocity);
    assert.ok(rs[i].peclet > rs[i - 1].peclet);
    assert.ok(rs[i].width < rs[i - 1].width);
  }
  assert.ok(Math.abs(rs[3].buoyantVelocity / rs[1].buoyantVelocity - Math.sqrt(G.earth / G.moon)) < 1e-9);
  assert.deepEqual(rs[3].direction, [0, 1]); // no forced flow: plume points straight up
});

test('gravity is continuous: tiny changes give tiny responses', () => {
  const a = run({ gravity: 3.7 }), b = run({ gravity: 3.7001 });
  assert.ok(Math.abs(a.width - b.width) / a.width < 1e-4);
});

test('the same forced flow tilts a microgravity flame further than an Earth flame', () => {
  const tilt = (g) => { const d = run({ gravity: g, flow: 0.1 }).direction; return Math.atan2(d[0], d[1]); };
  assert.ok(Math.abs(tilt(0) - Math.PI / 2) < 1e-12);
  assert.ok(tilt(0) > tilt(G.moon) && tilt(G.moon) > tilt(G.mars) && tilt(G.mars) > tilt(G.earth));
});

test('lower pressure raises diffusivity, so the flame is less convection-dominated', () => {
  assert.ok(run({ pressure: 56.5 }).peclet < run({ pressure: 101.325 }).peclet);
});

test('flame temperature is the Burke-Schumann adiabatic value', () => {
  const out = F.solve({ o2: 21 });
  const { Zst, dHc, cp } = out.properties;
  assert.ok(Math.abs(out.results.flameTemp - (out.inputs.tAmb + (Zst * dHc) / cp)) < 1e-9);
  assert.ok(run({ o2: 30 }).flameTemp > run({ o2: 21 }).flameTemp);
});

test('bad input is clamped or defaulted with a warning, never NaN', () => {
  const out = F.solve({ gravity: 'abc', o2: 300, pressure: -5, fuel: 'nope' });
  assert.equal(out.warnings.length, 4);
  for (const v of Object.values(out.results)) {
    if (typeof v === 'number') assert.ok(Number.isFinite(v));
  }
});
