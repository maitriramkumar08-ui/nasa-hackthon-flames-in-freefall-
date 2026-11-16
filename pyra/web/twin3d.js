/**
 * twin3d.js: a 3D view of the SIMULATED Ops run.
 *
 * A procedural station (no asset files) with one pressurised module per compartment.
 * Every frame is driven by the same /api/ops snapshot the Crew and Controller views use:
 *
 *   flow_cm_s      -> cabin fan speed and the speed of the cyan airflow streaks
 *   smoke_level    -> density of the grey haze inside the module
 *   temperature_c  -> warmth of the module's interior light
 *   banner.status  -> nominal / watch / alert colour of the module's status lights
 *   tiles[].status -> the per-channel chips in the side panel and the pins
 *
 * Statuses always come from the backend (pyra/ops.py). The VISUAL_SCALE numbers below
 * only decide how strong an effect looks; they are not limits and judge nothing.
 * The layout is our own illustration, not a real vehicle. Nothing here predicts a fire:
 * the haze shows the SIMULATED smoke index, and in microgravity it drifts with the
 * airflow instead of rising.
 *
 * app.js (a classic script) calls window.pyraTwin.update(view) on every Ops tick.
 * Coordinates: station axis = X, up = Y.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

const $ = (sel) => document.querySelector(sel);

// The page only needs an empty <div id="sub-twin" class="sub" hidden>; the view builds itself
// (markup and scoped styles) so it does not depend on the rest of the layout.
const TWIN_HTML = `
<div class="twin">
  <div id="twin-stage" class="twin-stage">
    <div id="twin-pins" class="twin-pins"></div>
    <div id="twin-hud" class="twin-hud">Waiting for readings…</div>
    <div class="twin-tools">
      <div id="twin-views" class="twin-row"></div>
      <div class="twin-row">
        <button type="button" id="twin-roof">Cutaway</button>
        <button type="button" id="twin-air">Airflow</button>
        <button type="button" id="twin-labels">Labels</button>
        <button type="button" id="twin-spin">Orbit</button>
      </div>
    </div>
    <div class="twin-legend">
      <span><i class="tdot nominal"></i>nominal</span><span><i class="tdot watch"></i>watch</span><span><i class="tdot alert"></i>alert</span>
      <span><i class="tdot air"></i>airflow speed</span><span><i class="tdot smoke"></i>smoke index</span>
      
    </div>
    <div id="twin-loading" class="twin-loading">Loading the 3D view. It loads three.js from cdn.jsdelivr.net, so it needs an internet connection.</div>
  </div>
  <aside id="twin-detail" class="twin-detail" aria-live="polite"></aside>
</div>
<p class="twin-note">Drag to look around, scroll to zoom, click a module to open it up. The readings are a demo run and the station layout is a sketch, not a real vehicle.</p>`;

const TWIN_CSS = `
.twin{display:grid;grid-template-columns:minmax(0,1fr) 330px;gap:12px;margin-top:12px}
.twin-stage{position:relative;height:min(68vh,640px);min-height:380px;border:1px solid var(--line);border-radius:var(--r);overflow:hidden;background:var(--bg)}
.twin-stage canvas{display:block;width:100%;height:100%;touch-action:none}
.twin-pins{position:absolute;inset:0;pointer-events:none}
.twin-pin{position:absolute;left:0;top:0;pointer-events:auto;display:flex;flex-direction:column;align-items:flex-start;gap:3px;
  padding:7px 10px;border-radius:var(--r-sm);border:1px solid var(--line-2);background:color-mix(in srgb,var(--surface) 86%,transparent);
  color:var(--text);font:600 12px var(--sans);white-space:nowrap;cursor:pointer;text-transform:capitalize}
.twin-pin-head{display:flex;align-items:center;gap:8px}
.twin-pin small{font:400 11px var(--mono);color:var(--muted);text-transform:none}
.twin-pin:hover{border-color:var(--text-2)}
.twin-pin.on{outline:1px solid var(--ember);outline-offset:2px}
.twin-pin.watch{border-color:var(--warn)}.twin-pin.alert{border-color:var(--alert);}
.twin .tchip{display:inline-flex;align-items:center;gap:5px;text-transform:none;font-style:normal;white-space:nowrap;font:500 11px var(--sans)}
.twin .tchip::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.twin .tchip.nominal{color:var(--ok)}.twin .tchip.watch{color:var(--warn)}.twin .tchip.alert{color:var(--alert)}
.twin-hud{position:absolute;left:12px;top:12px;padding:5px 9px;border-radius:var(--r-sm);border:1px solid var(--line);
  background:color-mix(in srgb,var(--surface) 86%,transparent);color:var(--text-2);font:11px var(--mono)}
.twin-tools{position:absolute;right:12px;top:12px;display:flex;flex-direction:column;align-items:flex-end;gap:6px}
.twin-row{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:4px}
.twin-row button{font:500 12px var(--sans);color:var(--text-2);background:color-mix(in srgb,var(--surface-2) 90%,transparent);
  border:1px solid var(--line-2);border-radius:var(--r-sm);padding:5px 10px;cursor:pointer;text-transform:capitalize;}
.twin-row button:hover{border-color:var(--text-2);color:var(--text)}
.twin-row button[aria-pressed=true]{background:var(--text);color:var(--bg);border-color:var(--text)}
.twin-legend{position:absolute;left:12px;bottom:12px;right:12px;display:flex;flex-wrap:wrap;gap:4px 14px;font:11px var(--sans);color:var(--muted);pointer-events:none}
.tdot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:middle}
.tdot.nominal{background:var(--ok)}.tdot.watch{background:var(--warn)}.tdot.alert{background:var(--alert)}.tdot.air{background:var(--ice)}.tdot.smoke{background:#9a9ea6}
.twin-loading{position:absolute;inset:0;display:grid;place-items:center;padding:24px;text-align:center;color:var(--muted);background:var(--bg);font:13px var(--sans)}
.twin-loading[hidden]{display:none}
.twin-detail{border:1px solid var(--line);border-radius:var(--r);padding:14px;background:var(--surface);max-height:min(68vh,640px);overflow:auto}
.twin-detail h3{margin:0 0 10px;font:600 18px var(--sans);text-transform:capitalize;color:var(--text)}
.twin-detail h3 small{text-transform:none;margin-left:8px;font:400 12px var(--sans);color:var(--muted)}
.twin-banner{padding:10px 12px;border-radius:var(--r-sm);border:1px solid var(--line-2);background:var(--surface-2);margin-bottom:12px;font-size:13px;color:var(--text-2)}
.twin-banner.watch{border-color:var(--warn);color:var(--warn)}.twin-banner.alert{border-color:var(--alert);color:var(--alert)}
.twin-tile{border:1px solid var(--line);border-radius:var(--r-sm);padding:8px 10px;margin-bottom:6px;background:var(--surface-2)}
.twin .twin-tile-row{display:flex;align-items:center;gap:10px;cursor:pointer;list-style:none;color:var(--text-2);font-size:13px}
.twin .twin-tile-row::-webkit-details-marker{display:none}
.twin .twin-tile-name{flex:1;font-style:normal;text-align:left}
.twin .twin-tile-row b{font:600 15px var(--mono);color:var(--text);white-space:nowrap}
.twin .twin-tile-row b small{font:11px var(--mono);color:var(--muted)}
.twin-tile.watch{border-color:color-mix(in srgb,var(--warn) 55%,transparent)}.twin-tile.alert{border-color:var(--alert)}
.twin-tile ul{margin:8px 0 2px 16px;padding:0;font-size:12px;color:var(--muted)}
.twin-note{color:var(--muted);font-size:12px}
@media (max-width:900px){.twin{grid-template-columns:1fr}.twin-stage{height:58vh}.twin-detail{max-height:none}}`;

const slot = $('#sub-twin');
if (slot && !$('#twin-stage')) {
  slot.insertAdjacentHTML('beforeend', TWIN_HTML);
  document.head.appendChild(Object.assign(document.createElement('style'), { textContent: TWIN_CSS }));
}
const host = $('#twin-stage');
const pinsLayer = $('#twin-pins');
const detail = $('#twin-detail');
const loading = $('#twin-loading');
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

// Visual scaling only (see header). [value that looks "none", value that looks "full"].
const VISUAL_SCALE = {
  flow_cm_s: [0, 15],
  smoke_level: [0, 0.3],
  temperature_c: [20, 32],
};
const STATUS_COLOR = { nominal: 0x5ed69c, watch: 0xffc84a, alert: 0xff4f4f }; // --ok / --warn / --alert
const ROOF_Y = 0.45; // the cutaway removes everything above this height
const R = 2.1; // module radius

const norm = (ch, v) => {
  const [lo, hi] = VISUAL_SCALE[ch];
  return v == null || Number.isNaN(v) ? 0 : Math.min(1, Math.max(0, (v - lo) / (hi - lo)));
};
const fmt = (v) => (v == null ? '-' : Math.abs(v) >= 100 ? v.toFixed(0) : Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(2));
function h(tag, attrs = {}, text) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  // app.js (a classic script) defines human(), which turns the server's provenance labels into plain words.
  if (text != null) node.textContent = typeof window.human === 'function' ? window.human(String(text)) : text;
  return node;
}

// ---------------------------------------------------------------- renderer
let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
} catch (err) {
  loading.textContent = 'This browser could not start WebGL, so the 3D view is unavailable. Crew and Controller still work.';
  throw err;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.85;
renderer.localClippingEnabled = true;
host.prepend(renderer.domElement);
renderer.domElement.addEventListener('webglcontextlost', (e) => {
  e.preventDefault();
  loading.hidden = false;
  loading.textContent = 'The graphics context was lost. Reload the page to bring the 3D view back.';
});

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0b0c0e); // --bg
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
scene.environmentIntensity = 0.55;

const camera = new THREE.PerspectiveCamera(42, 1, 0.1, 3000);
camera.position.set(4, 19, 21);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 5;
controls.maxDistance = 80;
controls.maxPolarAngle = Math.PI * 0.62;
controls.autoRotateSpeed = 0.4;

const composer = new EffectComposer(renderer);
composer.addPass(new RenderPass(scene, camera));
const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), 0.4, 0.35, 0.95);
composer.addPass(bloom);
composer.addPass(new OutputPass());

// ---------------------------------------------------------------- lights and sky
const sun = new THREE.DirectionalLight(0xfff4e6, 1.6);
sun.position.set(30, 40, 20);
scene.add(sun, new THREE.HemisphereLight(0x9cc8ff, 0x0a0c14, 0.35));

function starfield() {
  const n = 2600, pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    const v = new THREE.Vector3().randomDirection().multiplyScalar(900 + Math.random() * 300);
    pos.set([v.x, v.y, v.z], i * 3);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  return new THREE.Points(g, new THREE.PointsMaterial({ color: 0xcfe0ff, size: 1.6, sizeAttenuation: false }));
}
scene.add(starfield());

// Backdrop body follows the gravity picked for the evidence check. Decorative only.
const BACKDROPS = {
  '': { color: 0x173a6e, rim: 0x5c9be0, label: 'Earth orbit (backdrop)' },
  '0': { color: 0x173a6e, rim: 0x5c9be0, label: 'Earth orbit (backdrop)' },
  '0.16': { color: 0x4a4a4f, rim: 0xb9bcc6, label: 'Moon (backdrop)' },
  '0.38': { color: 0x6b2e18, rim: 0xff9a6b, label: 'Mars (backdrop)' },
  '1': null,
};
const planetMat = new THREE.MeshStandardMaterial({ color: 0x173a6e, roughness: 1, metalness: 0, envMapIntensity: 0.15 });
const planet = new THREE.Mesh(new THREE.SphereGeometry(900, 128, 96), planetMat);
const rimMat = new THREE.MeshBasicMaterial({ color: 0x6fb6ff, transparent: true, opacity: 0.18, side: THREE.BackSide,
  blending: THREE.AdditiveBlending, depthWrite: false });
planet.add(new THREE.Mesh(new THREE.SphereGeometry(930, 96, 64), rimMat));
planet.position.set(0, -1250, -900);
scene.add(planet);
function applyBackdrop() {
  const pick = BACKDROPS[$('#ops-gravity')?.value ?? ''];
  planet.visible = !!pick;
  if (pick) { planetMat.color.setHex(pick.color); rimMat.color.setHex(pick.rim); }
}
$('#ops-gravity')?.addEventListener('change', applyBackdrop);
applyBackdrop();

// ---------------------------------------------------------------- shared materials and textures
const roofPlane = new THREE.Plane(new THREE.Vector3(0, -1, 0), ROOF_Y);
const hull = new THREE.MeshPhysicalMaterial({ color: 0xb9bec7, metalness: 0.25, roughness: 0.6, clearcoat: 0.15,
  side: THREE.DoubleSide, clippingPlanes: [roofPlane], clipShadows: true });
const hullInner = new THREE.MeshStandardMaterial({ color: 0xb8c2d0, metalness: 0.1, roughness: 0.8,
  side: THREE.BackSide, clippingPlanes: [roofPlane] });
const ribMat = new THREE.MeshStandardMaterial({ color: 0x9aa6b8, metalness: 0.7, roughness: 0.35, clippingPlanes: [roofPlane] });
const floorMat = new THREE.MeshStandardMaterial({ color: 0x3a4456, metalness: 0.5, roughness: 0.6 });
const rackMat = new THREE.MeshStandardMaterial({ color: 0xd9dee6, metalness: 0.2, roughness: 0.5 });
const darkMat = new THREE.MeshStandardMaterial({ color: 0x1c2230, metalness: 0.6, roughness: 0.4 });
const fanMat = new THREE.MeshStandardMaterial({ color: 0x8994a6, metalness: 0.8, roughness: 0.25 });

function canvasTexture(w, hgt, draw) {
  const c = document.createElement('canvas');
  c.width = w; c.height = hgt;
  draw(c.getContext('2d'), w, hgt);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
const puff = canvasTexture(64, 64, (g, w) => {
  const grad = g.createRadialGradient(w / 2, w / 2, 0, w / 2, w / 2, w / 2);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.4, 'rgba(255,255,255,.45)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad; g.fillRect(0, 0, w, w);
});
const solarTex = canvasTexture(256, 512, (g, w, hgt) => {
  g.fillStyle = '#0b1f4a'; g.fillRect(0, 0, w, hgt);
  for (let y = 0; y < hgt; y += 32) for (let x = 0; x < w; x += 32) {
    g.fillStyle = `hsl(222, 70%, ${18 + Math.random() * 8}%)`; g.fillRect(x + 1, y + 1, 30, 30);
  }
  g.strokeStyle = '#c9a54a'; g.lineWidth = 3; g.strokeRect(1, 1, w - 2, hgt - 2);
});

// ---------------------------------------------------------------- one module per compartment
function cylinderX(r, len, mat, open = true, seg = 64) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(r, r, len, seg, 1, open), mat);
  m.rotation.z = Math.PI / 2;
  return m;
}

function buildModule(name, x, len, isNode) {
  const g = new THREE.Group();
  g.position.x = x;
  const pick = [];
  const tag = (m) => { m.userData.compartment = name; pick.push(m); return m; };

  // hull, ribs and end bulkheads (all cut by the roof plane)
  g.add(tag(cylinderX(R, len, hull)));
  g.add(cylinderX(R - 0.06, len, hullInner));
  const ribs = Math.max(2, Math.round(len / 1.5));
  for (let i = 0; i <= ribs; i++) {
    const rib = new THREE.Mesh(new THREE.TorusGeometry(R + 0.02, 0.07, 10, 72), ribMat);
    rib.rotation.y = Math.PI / 2;
    rib.position.x = -len / 2 + (i * len) / ribs;
    g.add(rib);
  }
  [-1, 1].forEach((side) => {
    const cap = new THREE.Mesh(new THREE.CircleGeometry(R, 64), hull);
    cap.rotation.y = side * Math.PI / 2;
    cap.position.x = side * len / 2;
    g.add(tag(cap));
    const hatch = new THREE.Mesh(new THREE.TorusGeometry(0.85, 0.09, 12, 48), darkMat);
    hatch.rotation.y = Math.PI / 2;
    hatch.position.x = side * (len / 2 - 0.02);
    g.add(hatch);
  });

  // floor, status strips and racks
  const floor = new THREE.Mesh(new THREE.BoxGeometry(len - 0.2, 0.08, 2.7), floorMat);
  floor.position.y = -1.25;
  g.add(tag(floor));
  const statusMat = new THREE.MeshStandardMaterial({ color: 0x111111, emissive: STATUS_COLOR.nominal, emissiveIntensity: 1.6 });
  [-1, 1].forEach((side) => {
    const strip = new THREE.Mesh(new THREE.BoxGeometry(len - 0.4, 0.05, 0.06), statusMat);
    strip.position.set(0, -1.18, side * 1.3);
    g.add(strip);
  });
  const screenMat = new THREE.MeshStandardMaterial({ color: 0x050a12, emissive: STATUS_COLOR.nominal, emissiveIntensity: 0.9 });
  if (!isNode) {
    const racks = Math.floor((len - 1.6) / 1.1);
    for (let i = 0; i < racks; i++) {
      const rx = -len / 2 + 1.1 + i * 1.1 + 0.5;
      [-1, 1].forEach((side) => {
        const rack = new THREE.Mesh(new THREE.BoxGeometry(1.0, 1.55, 0.55), rackMat);
        rack.position.set(rx, -0.43, side * 1.45);
        g.add(tag(rack));
        if ((i + (side > 0 ? 1 : 0)) % 2 === 0) {
          const screen = new THREE.Mesh(new THREE.PlaneGeometry(0.6, 0.38), screenMat);
          screen.position.set(rx, -0.15, side * 1.165);
          screen.rotation.y = side > 0 ? Math.PI : 0;
          g.add(screen);
        }
      });
    }
  } else {
    // a node: side ports and a central table
    [-1, 1].forEach((side) => {
      const port = new THREE.Mesh(new THREE.CylinderGeometry(1.0, 1.0, 0.9, 48, 1, true), hull);
      port.rotation.x = Math.PI / 2;
      port.position.z = side * (R + 0.2);
      g.add(tag(port));
      const ring = new THREE.Mesh(new THREE.TorusGeometry(1.0, 0.1, 12, 48), darkMat);
      ring.position.z = side * (R + 0.65);
      g.add(ring);
    });
    const table = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 0.06, 40), rackMat);
    table.position.y = -0.4;
    g.add(table);
    const screen = new THREE.Mesh(new THREE.CircleGeometry(0.45, 40), screenMat);
    screen.rotation.x = -Math.PI / 2;
    screen.position.y = -0.36;
    g.add(screen);
  }

  // cabin fan at the upstream end; its speed follows airflow
  const fan = new THREE.Group();
  fan.position.set(-len / 2 + 0.35, 0.15, 0);
  const duct = new THREE.Mesh(new THREE.TorusGeometry(0.62, 0.07, 12, 48), darkMat);
  duct.rotation.y = Math.PI / 2;
  fan.add(duct);
  const rotor = new THREE.Group();
  for (let i = 0; i < 6; i++) {
    const blade = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.52, 0.16), fanMat);
    blade.position.y = 0.28;
    const arm = new THREE.Group();
    arm.rotation.x = (i / 6) * Math.PI * 2;
    blade.rotation.y = 0.5;
    arm.add(blade);
    rotor.add(arm);
  }
  rotor.add(new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 12), darkMat));
  fan.add(rotor);
  g.add(fan);

  // interior light: warmth follows temperature
  const lamp = new THREE.PointLight(0xdfeaff, 6, len * 1.4, 1.6);
  lamp.position.set(0, 0.9, 0);
  g.add(lamp);

  // airflow streaks (additive points moving along +X)
  const nAir = Math.round(len * 34);
  const air = particles(nAir, len, 1.45);
  const airMat = new THREE.PointsMaterial({ color: 0x8fd0ff, size: 0.07, transparent: true, opacity: 0.8,
    blending: THREE.AdditiveBlending, depthWrite: false, clippingPlanes: [roofPlane] });
  const airPts = new THREE.Points(air.geo, airMat);
  g.add(airPts);

  // smoke haze (soft sprites), opacity and visible count follow the smoke index
  const nSmoke = Math.round(len * 22);
  const smoke = particles(nSmoke, len, 1.6);
  const smokeMat = new THREE.PointsMaterial({ color: 0x9a9ea6, map: puff, size: 1.25, transparent: true, opacity: 0, clippingPlanes: [roofPlane],
    depthWrite: false });
  const smokePts = new THREE.Points(smoke.geo, smokeMat);
  g.add(smokePts);

  // exterior status ring
  const ringMat = new THREE.MeshStandardMaterial({ color: 0x111111, emissive: STATUS_COLOR.nominal, emissiveIntensity: 2,
    clippingPlanes: [roofPlane] });
  const ring = new THREE.Mesh(new THREE.TorusGeometry(R + 0.12, 0.05, 8, 96), ringMat);
  ring.rotation.y = Math.PI / 2;
  g.add(ring);

  scene.add(g);
  return {
    name, group: g, len, x, isNode, pick, rotor, lamp, airPts, airMat, air, nAir, smoke, smokePts, smokeMat, nSmoke,
    statusMats: [statusMat, screenMat, ringMat], status: 'nominal', phase: Math.random() * 6,
    cur: { flow_cm_s: 10, smoke_level: 0, temperature_c: 22 }, tgt: { flow_cm_s: 10, smoke_level: 0, temperature_c: 22 },
  };
}

function particles(n, len, radius) {
  const pos = new Float32Array(n * 3), seed = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2, r = Math.sqrt(Math.random()) * radius;
    pos.set([(Math.random() - 0.5) * len, Math.max(-1.1, Math.sin(a) * r), Math.cos(a) * r * 0.82], i * 3);
    seed[i] = Math.random();
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  return { geo, pos, seed };
}

// ---------------------------------------------------------------- station layout
let modules = [];
const byName = {};
function layout(names) {
  // A "node" compartment goes in the middle as the connector; the rest line up either side.
  const nodeName = names.find((n) => /node/i.test(n));
  const rest = names.filter((n) => n !== nodeName);
  const order = nodeName ? [...rest.slice(0, Math.ceil(rest.length / 2)), nodeName, ...rest.slice(Math.ceil(rest.length / 2))] : rest;
  const lens = order.map((n) => (n === nodeName ? 4.6 : 9));
  const gap = 1.6;
  const total = lens.reduce((a, b) => a + b, 0) + gap * (order.length - 1);
  let cursor = -total / 2;
  modules = order.map((n, i) => {
    const m = buildModule(n, cursor + lens[i] / 2, lens[i], n === nodeName);
    if (i > 0) { // pressurised tunnel to the previous module
      const t = cylinderX(0.95, gap + 0.2, hull, true, 40);
      t.position.x = cursor - gap / 2;
      scene.add(t);
    }
    cursor += lens[i] + gap;
    byName[n] = m;
    return m;
  });
  buildTruss(total);
  buildPins();
  buildViewButtons();
}

function buildTruss(total) {
  const span = total + 10;
  const truss = new THREE.Group();
  truss.position.y = R + 1.3;
  [[-0.3, -0.3], [-0.3, 0.3], [0.3, -0.3], [0.3, 0.3]].forEach(([y, z]) => {
    const beam = new THREE.Mesh(new THREE.BoxGeometry(span, 0.08, 0.08), ribMat);
    beam.position.set(0, y, z);
    truss.add(beam);
  });
  for (let x = -span / 2; x <= span / 2; x += 1.2) {
    const brace = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.7, 0.7), new THREE.MeshStandardMaterial({ color: 0x9aa6b8, metalness: 0.7, roughness: 0.4, wireframe: true }));
    brace.position.x = x;
    truss.add(brace);
  }
  const panelMat = new THREE.MeshStandardMaterial({ map: solarTex, metalness: 0.55, roughness: 0.35, side: THREE.DoubleSide });
  [-1, 1].forEach((side) => {
    for (const z of [-1, 1]) {
      const wing = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 11), panelMat);
      wing.rotation.x = -Math.PI / 2;
      wing.position.set(side * (span / 2 + 0.6), 0, z * 6.2);
      truss.add(wing);
    }
    const mast = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.12, 24), ribMat);
    mast.position.x = side * (span / 2 + 0.6);
    truss.add(mast);
  });
  const rad = new THREE.Mesh(new THREE.PlaneGeometry(2.4, 7), new THREE.MeshStandardMaterial({ color: 0xf2f4f7, roughness: 0.7, side: THREE.DoubleSide }));
  rad.rotation.x = -Math.PI / 2;
  rad.position.set(0, 0.6, 0);
  rad.rotation.z = 0.0;
  truss.add(rad);
  scene.add(truss);
}

// ---------------------------------------------------------------- pins, view buttons and side panel
let selected = null;
let view = null;
let showLabels = true;

function buildPins() {
  pinsLayer.replaceChildren();
  modules.forEach((m) => {
    const pin = h('button', { type: 'button', class: 'twin-pin nominal', 'aria-label': `Select ${m.name}` });
    const head = h('div', { class: 'twin-pin-head' });
    head.append(h('b', {}, m.name), h('i', { class: 'tchip nominal' }, 'nominal'));
    pin.append(head, h('small', {}, ''));
    pin.addEventListener('click', () => select(m.name, true));
    pinsLayer.appendChild(pin);
    m.pin = pin;
  });
}

function buildViewButtons() {
  const box = $('#twin-views');
  box.replaceChildren();
  const add = (label, fn) => { const b = h('button', { type: 'button' }, label); b.addEventListener('click', fn); box.appendChild(b); };
  add('Overview', () => { select(null); flyTo(new THREE.Vector3(4, 19, 21), new THREE.Vector3(0, 0, 0)); });
  modules.forEach((m) => add(m.name, () => select(m.name, true)));
}

function select(name, fly = false) {
  selected = name;
  modules.forEach((m) => m.pin && m.pin.classList.toggle('on', m.name === name));
  const m = byName[name];
  if (m && fly) flyTo(new THREE.Vector3(m.x + 2.5, 6.5, 9.5), new THREE.Vector3(m.x, -0.3, 0));
  drawDetail();
}

function drawDetail() {
  detail.replaceChildren();
  if (!view) { detail.appendChild(h('p', { class: 'twin-note' },'Waiting for the first reading.')); return; }
  const name = selected || pickMostUrgent();
  const room = view.compartments[name];
  if (!room) return;
  const title = h('h3', {}, name);
  if (!selected) title.appendChild(h('small', {}, '(most urgent)'));
  detail.appendChild(title);
  detail.appendChild(h('div', { class: `twin-banner ${room.banner.status}` }, room.banner.text));
  const list = h('div', { class: 'twin-tiles' });
  room.tiles.forEach((t) => {
    const d = h('details', { class: `twin-tile ${t.status}` });
    const s = h('summary', { class: 'twin-tile-row' });
    const val = h('b', {}, fmt(t.value));
    val.appendChild(h('small', {}, ` ${t.unit}`));
    s.append(h('em', { class: 'twin-tile-name' }, t.title), val, h('i', { class: `tchip ${t.status}` }, t.status));
    d.appendChild(s);
    const ul = h('ul');
    (t.reasons.length ? t.reasons : ['No alert, trend, grouped concern or evidence note for this channel.'])
      .forEach((r) => ul.appendChild(h('li', {}, r)));
    d.appendChild(ul);
    list.appendChild(d);
  });
  detail.appendChild(list);
  detail.appendChild(h('p', { class: 'twin-note' }, `Temperature ${fmt(room.sample.temperature_c)} °C. Material class: ${room.material_class || 'not set'}.`));
}

const RANK = { alert: 2, watch: 1, nominal: 0 };
function pickMostUrgent() {
  const names = Object.keys(view.compartments);
  return names.reduce((best, n) => (RANK[view.compartments[n].banner.status] > RANK[view.compartments[best].banner.status] ? n : best), names[0]);
}

// ---------------------------------------------------------------- data in
function update(next) {
  if (!next || !next.compartments) return;
  view = next;
  if (!modules.length) layout(Object.keys(next.compartments));
  Object.entries(next.compartments).forEach(([name, room]) => {
    const m = byName[name];
    if (!m) return;
    ['flow_cm_s', 'smoke_level', 'temperature_c'].forEach((ch) => { if (room.sample[ch] != null) m.tgt[ch] = room.sample[ch]; });
    m.status = room.banner.status in STATUS_COLOR ? room.banner.status : 'nominal';
    const c = new THREE.Color(STATUS_COLOR[m.status]);
    m.statusMats.forEach((mat) => mat.emissive.copy(c));
    if (m.pin) {
      m.pin.className = `twin-pin ${m.status}${m.name === selected ? ' on' : ''}`;
      const chip = m.pin.querySelector('.tchip');
      chip.className = `tchip ${m.status}`;
      chip.textContent = m.status;
      m.pin.title = room.banner.text;
      const s = room.sample;
      m.pin.querySelector('small').textContent = `O2 ${fmt(s.o2_percent)}% · smoke ${fmt(s.smoke_level)} · flow ${fmt(s.flow_cm_s)}`;
    }
  });
  $('#twin-hud').textContent = `t = ${next.t} s of ${next.steps} · ${next.scenario}`;
  drawDetail();
}

// ---------------------------------------------------------------- toolbar
function toggle(id, initial, fn) {
  const b = $(id);
  let on = initial;
  b.setAttribute('aria-pressed', String(on));
  b.addEventListener('click', () => { on = !on; b.setAttribute('aria-pressed', String(on)); fn(on); });
  fn(on);
}
let airOn = true;
toggle('#twin-roof', true, (on) => { roofPlane.constant = on ? ROOF_Y : 100; });
toggle('#twin-air', true, (on) => { airOn = on; });
toggle('#twin-labels', true, (on) => { showLabels = on; pinsLayer.hidden = !on; });
toggle('#twin-spin', false, (on) => { controls.autoRotate = on && !REDUCED; });

// ---------------------------------------------------------------- picking
const ray = new THREE.Raycaster();
const ndc = new THREE.Vector2();
let downAt = null;
renderer.domElement.addEventListener('pointerdown', (e) => { downAt = [e.clientX, e.clientY]; });
renderer.domElement.addEventListener('pointerup', (e) => {
  if (!downAt || Math.hypot(e.clientX - downAt[0], e.clientY - downAt[1]) > 5) return;
  const r = renderer.domElement.getBoundingClientRect();
  ndc.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ndc, camera);
  const hit = ray.intersectObjects(modules.flatMap((m) => m.pick), false)
    .find((i) => i.point.y <= roofPlane.constant); // ignore the cut-away roof
  if (hit) select(hit.object.userData.compartment, true);
});

// ---------------------------------------------------------------- camera flights
let fly = null;
function flyTo(pos, target) {
  if (REDUCED) { camera.position.copy(pos); controls.target.copy(target); return; }
  fly = { p0: camera.position.clone(), t0: controls.target.clone(), p1: pos, t1: target, t: 0 };
}

// ---------------------------------------------------------------- frame loop
const tmp = new THREE.Vector3();
const warm = new THREE.Color(0xffb27a), cool = new THREE.Color(0xdfeaff);
const clock = new THREE.Clock();
let shownW = 0, shownH = 0;

function resize() {
  const w = host.clientWidth, hgt = host.clientHeight;
  if (!w || !hgt || (w === shownW && hgt === shownH)) return;
  shownW = w; shownH = hgt;
  renderer.setSize(w, hgt, false);
  composer.setSize(w, hgt);
  bloom.setSize(w, hgt);
  camera.aspect = w / hgt;
  camera.updateProjectionMatrix();
}

function stepModule(m, dt, time) {
  const k = 1 - Math.exp(-dt * 2.5);
  Object.keys(m.cur).forEach((ch) => { m.cur[ch] += (m.tgt[ch] - m.cur[ch]) * k; });
  const flow = norm('flow_cm_s', m.cur.flow_cm_s);
  const smoke = norm('smoke_level', m.cur.smoke_level);
  const heat = norm('temperature_c', m.cur.temperature_c);
  const motion = REDUCED ? 0.15 : 1;

  m.rotor.rotation.x += dt * (1 + flow * 22) * motion;
  m.lamp.color.copy(cool).lerp(warm, heat);
  m.lamp.intensity = 5 + heat * 3;

  const pulse = m.status === 'alert' ? 1.4 + Math.sin(time * 6 + m.phase) * 1.1 : m.status === 'watch' ? 1.6 + Math.sin(time * 2.5) * 0.4 : 1.4;
  m.statusMats.forEach((mat, i) => { mat.emissiveIntensity = i === 1 ? pulse * 0.6 : pulse; });

  // airflow streaks: carried along +X at a rate set by flow_cm_s, wrapping at the far end
  const half = m.len / 2 - 0.3;
  m.airPts.visible = airOn;
  if (airOn) {
    const a = m.air.pos, v = (0.4 + flow * 4.5) * dt * motion;
    for (let i = 0; i < m.nAir; i++) {
      const j = i * 3;
      a[j] += v * (0.7 + m.air.seed[i] * 0.6);
      if (a[j] > half) a[j] = -half;
    }
    m.air.geo.attributes.position.needsUpdate = true;
    m.airMat.opacity = 0.25 + flow * 0.65;
  }

  // smoke haze: drifts with the air plus a slow random walk; no buoyant rise in microgravity
  const s = m.smoke.pos, sv = (0.15 + flow * 1.6) * dt * motion;
  for (let i = 0; i < m.nSmoke; i++) {
    const j = i * 3, sd = m.smoke.seed[i];
    s[j] += sv * (0.5 + sd);
    s[j + 1] += Math.sin(time * 0.7 + sd * 40) * 0.12 * dt;
    s[j + 2] += Math.cos(time * 0.6 + sd * 30) * 0.12 * dt;
    if (s[j] > half) s[j] = -half;
  }
  m.smoke.geo.attributes.position.needsUpdate = true;
  m.smoke.geo.setDrawRange(0, Math.round(m.nSmoke * Math.min(1, smoke * 1.5)));
  m.smokeMat.opacity = smoke * 0.55;
  m.smokeMat.size = 0.9 + smoke * 1.1;
}

function placePins() {
  if (!showLabels) return;
  const w = host.clientWidth, hgt = host.clientHeight;
  modules.forEach((m) => {
    tmp.set(m.x, R + 0.5 + (m.isNode ? 3.6 : 0), 0).project(camera);
    const visible = tmp.z < 1 && Math.abs(tmp.x) < 1.1 && Math.abs(tmp.y) < 1.1;
    m.pin.style.display = visible ? '' : 'none';
    if (visible) m.pin.style.transform = `translate(${((tmp.x + 1) / 2) * w}px, ${((1 - tmp.y) / 2) * hgt}px) translate(-50%, -100%)`;
  });
}

function frame() {
  requestAnimationFrame(frame);
  const dt = Math.min(clock.getDelta(), 0.1);
  if (!host.clientWidth) return; // tab hidden: skip the work
  resize();
  const time = clock.elapsedTime;
  if (fly) {
    fly.t = Math.min(1, fly.t + dt / 1.6);
    const e = fly.t < 0.5 ? 4 * fly.t ** 3 : 1 - (-2 * fly.t + 2) ** 3 / 2;
    camera.position.lerpVectors(fly.p0, fly.p1, e);
    controls.target.lerpVectors(fly.t0, fly.t1, e);
    if (fly.t >= 1) fly = null;
  }
  modules.forEach((m) => stepModule(m, dt, time));
  planet.rotation.y += dt * 0.004;
  controls.update();
  composer.render();
  placePins();
}

window.pyraTwin = { update };
loading.hidden = true;
if (window.pyraOps) update(window.pyraOps);
else drawDetail();
frame();
