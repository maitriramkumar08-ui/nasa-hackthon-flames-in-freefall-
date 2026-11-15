// PYRA front end. Plain JavaScript, no libraries: every chart is hand-drawn SVG.
// All numbers come from the API; this file only lays them out.
"use strict";

const QUANTITIES = {
  o2_percent: "O2 (%)", pressure: "pressure (kPa)", flow_speed: "flow (cm/s)",
  gravity: "gravity (g)", temperature: "temperature (K)",
};
// Okabe-Ito, readable with the common forms of colour blindness.
const PALETTE = ["#E69F00", "#56B4E9", "#009E73", "#F0E442", "#4C9BE8", "#D55E00", "#CC79A7", "#BBBBBB"];
const SHAPES = { bench: "circle", "spacecraft-scale": "square", unknown: "triangle" };
const SVG = "http://www.w3.org/2000/svg";

const state = { investigations: [], runs: [], coverage: null, telemetry: [], step: 0, timer: null,
  selected: new Set(), history: {} };
const MAX_COMPARE = 3;
const $ = (sel) => document.querySelector(sel);

async function api(path, body) {
  const options = body === undefined ? {} :
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || `${path} answered ${response.status}`);
  return payload;
}

function showError(err) {
  const box = $("#error");
  box.textContent = err ? err.message : "";
  box.hidden = !err;
}

// The server marks provenance with upper-case labels (SIMULATED, DERIVED, ...) and gap
// classes with codes (NO_INDEXED_DATA). On screen we drop bracketed tags and read the rest
// as ordinary words, so the interface speaks plainly.
const TAG = "(?:MEASURED|DERIVED|HYPOTHETICAL|INTERPRETATION|SIMULATED|PLACEHOLDER|ILLUSTRATIVE|PROPOSAL)";
const TAG_IN_BRACKETS = new RegExp(String.raw`\s*\[[^\]]*\b${TAG}\b[^\]]*\]`, "g");
const TAG_IN_PARENS = new RegExp(String.raw`\s*\(${TAG}\)`, "g");
const TAG_PREFIX = new RegExp(String.raw`^${TAG}:\s*`);
const TAG_WORD = new RegExp(String.raw`\b${TAG}\b`, "g");
const CODES = /\b(DIRECTLY[_ ]TESTED|BOUNDED|ONE[_ ]SIDED|INSUFFICIENT|NOT[_ ]COMPARABLE|NO[_ ]INDEXED[_ ]DATA|NOT[_ ]EVALUATED|NOT SET|THRESHOLD|TREND)\b/g;
function human(text) {
  if (typeof text !== "string") return text;
  return text
    .replace(TAG_IN_BRACKETS, "")
    .replace(TAG_IN_PARENS, "")
    .replace(TAG_PREFIX, "")
    .replace(CODES, (w) => w.replace(/_/g, " ").toLowerCase())
    .replace(TAG_WORD, (w) => w.toLowerCase());
}

function el(tag, attrs = {}, text) {
  const node = document.createElement(tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  if (text !== undefined) node.textContent = human(text);
  return node;
}

// Same clean-up for HTML the server renders (the scenario report).
function humanizeTree(root) {
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) n.nodeValue = human(n.nodeValue);
}

function svgEl(tag, attrs = {}) {
  const node = document.createElementNS(SVG, tag);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, v));
  return node;
}

function show(value) {
  if (value === null || value === undefined) return "not provided";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toPrecision(4);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

// A table for any list of flat-ish objects, so the view keeps up with the engines.
function table(rows) {
  if (!rows || !rows.length) return el("p", { class: "note" }, "No data found.");
  const keys = Object.keys(rows[0]);
  const wrap = el("div", { class: "table-wrap" });
  const tbl = el("table");
  const head = el("tr");
  keys.forEach((k) => head.appendChild(el("th", { scope: "col" }, k)));
  tbl.appendChild(head);
  rows.forEach((row) => {
    const tr = el("tr");
    keys.forEach((k) => tr.appendChild(el("td", {}, show(row[k]))));
    tbl.appendChild(tr);
  });
  wrap.appendChild(tbl);
  return wrap;
}

/* ---------- views ---------- */

// Routes are "#/<tab>/<sub>". Tabs: explore, ops, builder, agents, assistant, demo.
const TABS = { explore: ["coverage", "research", "report"], ops: ["crew", "controller", "twin"], builder: [], agents: [], assistant: [], demo: [] };
// Old one-word views (from the six-tab layout) redirect to where they live now.
const LEGACY = {
  explorer: "explore", researchers: "explore/research", compare: "explore", report: "explore/report", agent: "assistant",
  astronaut: "ops/crew", mission: "ops/controller", builders: "builder",
};

function parseRoute(hash) {
  let path = (hash || "").replace(/^#\/?/, "");
  if (LEGACY[path]) path = LEGACY[path];
  let [tab, sub] = path.split("/");
  if (!TABS[tab]) tab = "explore";
  if (!TABS[tab].includes(sub)) sub = TABS[tab][0];
  return { tab, sub, canonical: sub ? `#/${tab}/${sub}` : `#/${tab}` };
}

function route() {
  const { tab, sub, canonical } = parseRoute(location.hash);
  const wanted = location.hash.replace(/^#\/?/, "");
  if (LEGACY[wanted]) history.replaceState(null, "", canonical);
  document.querySelectorAll(".view").forEach((v) => { v.hidden = v.id !== `view-${tab}`; });
  document.querySelectorAll(".tab").forEach((a) => a.setAttribute("aria-current", a.dataset.tab === tab ? "page" : "false"));
  const view = $(`#view-${tab}`);
  view.querySelectorAll(".sub").forEach((s) => { s.hidden = s.id !== `sub-${sub}`; });
  view.querySelectorAll(".subtab").forEach((a) => a.setAttribute("aria-current", a.dataset.sub === sub ? "page" : "false"));
  if (tab === "ops") startTelemetry(); else stopTelemetry();
  if (tab === "explore" && sub === "coverage") drawMap();
  if (tab === "explore" && sub === "research") loadWeakness();
  if (tab === "builder") builderBoundary(loadBuilder)();
  if (tab === "agents" && window.pyraAgents) window.pyraAgents.show();
  // The 3D scene is heavy, so it only loads the first time the tab is opened.
  if (tab === "demo" && !$("#demo-frame").src) $("#demo-frame").src = $("#demo-frame").dataset.src;
}

function toggleDrawer(id, open) {
  const drawer = document.getElementById(id);
  drawer.hidden = open === undefined ? !drawer.hidden : !open;
  $("#scrim").hidden = !document.querySelector(".drawer:not([hidden])");
  const toggle = document.querySelector(`[aria-controls=${id}]`);
  if (toggle) toggle.setAttribute("aria-expanded", String(!drawer.hidden));
  if (!drawer.hidden) { const first = drawer.querySelector("input, button:not(.drawer-close)"); if (first) first.focus(); }
}

/* ---------- Explorer ---------- */

function colorOf(acronym) {
  const index = state.investigations.findIndex((inv) => inv.acronym === acronym);
  return PALETTE[(index < 0 ? PALETTE.length - 1 : index) % PALETTE.length];
}

function marker(shape, x, y, r, fill) {
  if (shape === "square") return svgEl("rect", { x: x - r, y: y - r, width: 2 * r, height: 2 * r, fill });
  if (shape === "triangle") return svgEl("polygon", { points: `${x},${y - r - 1} ${x + r + 1},${y + r} ${x - r - 1},${y + r}`, fill });
  return svgEl("circle", { cx: x, cy: y, r, fill });
}

function extent(values) {
  const nums = values.filter((v) => typeof v === "number");
  if (!nums.length) return [0, 1];
  let lo = Math.min(...nums), hi = Math.max(...nums);
  if (lo === hi) { lo -= 1; hi += 1; }
  const pad = (hi - lo) * 0.08;
  return [lo - pad, hi + pad];
}

function ticks([lo, hi], count = 5) {
  return Array.from({ length: count + 1 }, (_, i) => lo + ((hi - lo) * i) / count);
}

function scenarioValues() {
  return state.coverage ? state.coverage.scenario : null;
}

function drawMap() {
  const svg = $("#map");
  const width = svg.clientWidth || 700, height = svg.clientHeight || 440;
  const m = { left: 62, right: 22, top: 20, bottom: 46 };
  const xKey = $("#x-axis").value, yKey = $("#y-axis").value;
  const runs = state.coverage ? state.coverage.runs : state.runs;
  const scen = scenarioValues();
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.replaceChildren();
  svg.appendChild(svgEl("rect", { class: "plot-bg", x: m.left, y: m.top, width: Math.max(0, width - m.left - m.right),
    height: Math.max(0, height - m.top - m.bottom), rx: 6 }));

  const xs = runs.map((r) => r.values[xKey]).concat(scen ? [scen[xKey]] : []);
  const ys = runs.map((r) => r.values[yKey]).concat(scen ? [scen[yKey]] : []);
  const xDom = extent(xs), yDom = extent(ys);
  const sx = (v) => m.left + ((v - xDom[0]) / (xDom[1] - xDom[0])) * (width - m.left - m.right);
  const sy = (v) => height - m.bottom - ((v - yDom[0]) / (yDom[1] - yDom[0])) * (height - m.top - m.bottom);

  ticks(xDom).forEach((v) => {
    svg.appendChild(svgEl("line", { class: "grid", x1: sx(v), x2: sx(v), y1: m.top, y2: height - m.bottom }));
    const label = svgEl("text", { x: sx(v), y: height - m.bottom + 18, "text-anchor": "middle" });
    label.textContent = show(v);
    svg.appendChild(label);
  });
  ticks(yDom).forEach((v) => {
    svg.appendChild(svgEl("line", { class: "grid", x1: m.left, x2: width - m.right, y1: sy(v), y2: sy(v) }));
    const label = svgEl("text", { x: m.left - 10, y: sy(v) + 4, "text-anchor": "end" });
    label.textContent = show(v);
    svg.appendChild(label);
  });
  const xTitle = svgEl("text", { class: "axis-title", x: m.left + (width - m.left - m.right) / 2, y: height - 8, "text-anchor": "middle" });
  xTitle.textContent = QUANTITIES[xKey];
  const yMid = m.top + (height - m.top - m.bottom) / 2;
  const yTitle = svgEl("text", { class: "axis-title", x: 14, y: yMid, transform: `rotate(-90 14 ${yMid})`, "text-anchor": "middle" });
  yTitle.textContent = QUANTITIES[yKey];
  svg.append(xTitle, yTitle);

  const placed = runs.filter((r) => typeof r.values[xKey] === "number" && typeof r.values[yKey] === "number");
  const hasScenario = scen && typeof scen[xKey] === "number" && typeof scen[yKey] === "number";
  if (hasScenario && state.coverage.gaps) {
    (state.coverage.gaps.nearest_runs || []).forEach((near) => {
      const run = placed.find((r) => r.run_id === near.run_id && r.acronym === near.acronym);
      if (run) svg.appendChild(svgEl("line", { class: "near", x1: sx(scen[xKey]), y1: sy(scen[yKey]), x2: sx(run.values[xKey]), y2: sy(run.values[yKey]) }));
    });
  }

  placed.forEach((run) => {
    const dot = marker(SHAPES[run.scale] || "triangle", sx(run.values[xKey]), sy(run.values[yKey]), 6, colorOf(run.acronym));
    dot.setAttribute("class", "run");
    dot.setAttribute("tabindex", "0");
    dot.setAttribute("aria-label", `${run.acronym} run ${run.run_id}`);
    const open = () => hoverCard(run, dot);
    dot.addEventListener("mouseenter", open);
    dot.addEventListener("focus", open);
    dot.addEventListener("mouseleave", () => { $("#hover").hidden = true; });
    dot.addEventListener("blur", () => { $("#hover").hidden = true; });
    svg.appendChild(dot);
  });

  if (hasScenario) {
    const x = sx(scen[xKey]), y = sy(scen[yKey]);
    svg.appendChild(svgEl("circle", { class: "scenario", cx: x, cy: y, r: 7 }));
    const right = x < width - 160;
    const tag = svgEl("text", { class: "scenario-tag", x: right ? x + 12 : x - 12, y: y - 10, "text-anchor": right ? "start" : "end" });
    tag.textContent = "your scenario";
    svg.appendChild(tag);
  }

  const hidden = runs.length - placed.length;
  const note = svgEl("text", { class: "map-note", x: width - m.right - 10, y: m.top + 18, "text-anchor": "end" });
  note.textContent = hidden ? `${hidden} run(s) not shown: missing ${QUANTITIES[xKey]} or ${QUANTITIES[yKey]}` : "";
  svg.appendChild(note);
  drawLegend();
}

function hoverCard(run, dot) {
  const card = $("#hover");
  const missing = Object.keys(QUANTITIES).filter((q) => run.values[q] === null || run.values[q] === undefined);
  const lines = Object.keys(QUANTITIES).filter((q) => run.original[q]).map((q) => {
    const o = run.original[q];
    const kind = run.from_words.includes(q) ? "· read from the text" : "";
    return `${QUANTITIES[q]}: ${show(run.values[q])} (reported ${show(o.value)} ${o.unit || ""}, ${o.page || "page not provided"}) ${kind}`;
  });
  card.replaceChildren(
    el("strong", {}, `${run.acronym} / ${run.run_id}`),
    el("div", { class: "note" }, `${run.hardware || "hardware not provided"}, ${run.scale}`),
    el("div", {}, `Source: ${run.source.title || "not provided"}${run.page_or_table ? ", " + run.page_or_table : ""}`),
    ...lines.map((line) => el("div", { class: "mono" }, line)),
    el("div", { class: "note" }, missing.length ? `Missing (not zero): ${missing.join(", ")}` : "No missing quantities."),
  );
  const box = dot.getBoundingClientRect(), frame = $("#map").getBoundingClientRect();
  card.style.left = `${Math.min(box.left - frame.left + 12, frame.width - 290)}px`;
  card.style.top = `${box.top - frame.top + 12}px`;
  card.hidden = false;
}

function drawLegend() {
  const legend = $("#legend");
  legend.replaceChildren();
  const swatch = (shape, color, label) => {
    const item = el("span");
    const icon = svgEl("svg", { width: 14, height: 14, "aria-hidden": "true" });
    icon.appendChild(marker(shape, 7, 7, 5, color));
    item.append(icon, ` ${label}`);
    legend.appendChild(item);
  };
  state.investigations.forEach((inv) => swatch("circle", colorOf(inv.acronym), inv.acronym));
  Object.entries(SHAPES).forEach(([scale, shape]) => swatch(shape, "#8d8f96", `scale: ${scale}`));
  legend.appendChild(el("span", {}, "Points are reported values. Where a paper only says \"microgravity\", we place gravity from that word."));
}

function scenarioBody() {
  const form = new FormData($("#scenario"));
  const body = Object.fromEntries([...form.entries()].filter(([, v]) => v !== ""));
  // Gravity is a slider, so it always has a value; "set" decides whether it is sent.
  if (!body.gravity_set) delete body.gravity_g;
  delete body.gravity_set;
  return body;
}

async function runCoverage() {
  try {
    state.coverage = await api("/api/coverage", scenarioBody());
    showError(null);
  } catch (err) {
    state.coverage = null;
    showError(err);
  }
  drawMap();
  drawGaps();
  drawRanked();
}

// Which scenario input sets each gap axis, so an unset axis line can open it.
const AXIS_INPUT = {
  o2_percent: "o2_percent", pressure: "pressure", flow_speed: "flow_speed",
  gravity: "gravity_g", material_class: "material", pillar: "pillar",
};
const AXIS_LABEL = {
  o2_percent: "O2", pressure: "Pressure", flow_speed: "Flow", gravity: "Gravity",
  material_class: "Material", pillar: "Pillar",
};

function openAxisInput(axis) {
  if (axis === "gravity") $("#scenario [name=gravity_set]").checked = true;
  const input = $(`#scenario [name=${AXIS_INPUT[axis]}]`);
  if (!input) return;
  input.disabled = false;
  input.focus();
  if (input.select && input.type !== "range") input.select();
}

// Gap classes from best evidence to none (pyra/gaps.py); the ladder fills one segment per rung of strength.
const LADDER = ["DIRECTLY_TESTED", "BOUNDED", "ONE_SIDED", "INSUFFICIENT", "NOT_COMPARABLE", "NO_INDEXED_DATA"];

function ladder(cls) {
  const rung = LADDER.indexOf(cls);
  const strength = rung < 0 ? 0 : LADDER.length - rung;
  const box = el("span", { class: "ladder", title: human(String(cls)), "aria-hidden": "true" });
  LADDER.forEach((_, i) => box.appendChild(el("i", { class: i < strength ? "on" : "" })));
  return box;
}

// The gap panel only lays out the lines the engine wrote (gaps.panel_line); it never
// shows a raw null, so the words "not provided" cannot appear here.
function drawGaps() {
  const box = $("#gaps");
  box.replaceChildren();
  const gaps = state.coverage && state.coverage.gaps;
  if (!gaps) return box.appendChild(el("p", { class: "note" }, "Run a scenario to see coverage per axis."));
  Object.entries(gaps.axes || {}).forEach(([axis, g]) => {
    if (g.state === "NOT_EVALUATED") {
      const line = el("button", { type: "button", class: "gap-unset", "data-axis": axis });
      line.append(el("b", {}, `+ ${AXIS_LABEL[axis] || axis}`), g.summary);
      line.addEventListener("click", () => openAxisInput(axis));
      box.appendChild(line);
      return;
    }
    const rung = LADDER.indexOf(g.class);
    const card = el("div", { class: `gap-card ${g.class}${rung >= 2 ? " weak" : ""}` });
    const top = el("div", { class: "gap-top" });
    top.append(el("span", { class: "gap-axis-name" }, AXIS_LABEL[axis] || axis), ladder(g.class));
    card.append(top, el("span", { class: `gap-class ${g.class}` }, String(g.class)),
      el("span", { class: "gap-line" }, g.summary));
    box.appendChild(card);
  });
  if (gaps.combination) box.appendChild(el("p", { class: "gap-combo" }, gaps.combination.summary));
}

function pickBox(acronym) {
  const box = el("input", { type: "checkbox", value: acronym, class: "pick", "aria-label": `Select ${acronym} to compare` });
  box.checked = state.selected.has(acronym);
  box.addEventListener("change", () => {
    if (box.checked) state.selected.add(acronym); else state.selected.delete(acronym);
    syncPicks();
  });
  return box;
}

// Keep every checkbox for the same investigation in step, and cap the selection at MAX_COMPARE.
function syncPicks() {
  const full = state.selected.size >= MAX_COMPARE;
  document.querySelectorAll("input.pick").forEach((box) => {
    box.checked = state.selected.has(box.value);
    box.disabled = full && !box.checked;
  });
  const n = state.selected.size;
  const button = $("#compare-btn");
  button.textContent = `Compare (${n})`;
  button.disabled = n < 2 || n > MAX_COMPARE;
  $("#compare-hint").textContent = n < 2 ? "Tick 2 or 3 investigations to compare."
    : `${[...state.selected].join(", ")}`;
}

function drawRanked() {
  const list = $("#ranked");
  list.replaceChildren();
  const ranked = (state.coverage && state.coverage.ranked) || [];
  ranked.forEach((inv) => {
    const li = el("li");
    const head = el("label", { class: "ranked-head" });
    head.append(pickBox(inv.acronym), el("strong", {}, inv.acronym));
    if (inv.evidence_class) head.appendChild(el("span", { class: "ev" }, inv.evidence_class));
    head.appendChild(el("span", { class: "total", title: "How close this investigation is to your scenario" }, show(inv.total)));
    li.appendChild(head);
    const bars = el("div", { class: "bars" });
    Object.entries(inv.scores || {}).forEach(([name, score]) => {
      const bar = el("div", { class: "bar" });
      bar.style.width = `${Math.max(0, Math.min(1, score || 0)) * 100}%`;
      const track = el("div");
      track.appendChild(bar);
      bars.append(el("span", {}, name), track, el("span", { class: "mono" }, show(score)));
    });
    li.append(bars, el("div", { class: "note" }, inv.explanation || ""));
    if (inv.unmatched && inv.unmatched.length) li.appendChild(el("div", { class: "note" }, `Not matched: ${inv.unmatched.join(", ")}`));
    list.appendChild(li);
  });
  if (!ranked.length) list.appendChild(el("li", { class: "note ranked-empty" }, "Run a scenario to rank the indexed investigations."));
  drawPicks(new Set(ranked.map((inv) => inv.acronym)));
}

async function openReport() {
  try {
    const built = await api("/api/report", { scenario: scenarioBody() });
    $("#report-out").innerHTML = built.html;
    humanizeTree($("#report-out"));
    location.hash = "#/explore/report";
    showError(null);
  } catch (err) { showError(err); }
}

/* ---------- Compare (side panel) ---------- */

// Investigations that are not in the ranked list can still be picked from "Other investigations".
function drawPicks(shown = new Set()) {
  const box = $("#compare-picks");
  box.replaceChildren();
  state.investigations.filter((inv) => !shown.has(inv.acronym)).forEach((inv) => {
    const label = el("label");
    label.append(pickBox(inv.acronym), ` ${inv.acronym}`);
    box.appendChild(label);
  });
  if (!box.children.length) box.appendChild(el("p", { class: "note" }, "All investigations are in the ranked list."));
  syncPicks();
}

// What each verdict reason is about. The wording comes from pyra/compare.py; we only label it.
const REASON_TOPICS = [
  [/hardware/i, "Hardware"], [/scale/i, "Scale"], [/fuel|phase/i, "Fuel phase"],
  [/sensor|measure/i, "Measurement definition"],
];

function reasonItem(reason) {
  const text = reason.replace(/^NOT DIRECTLY COMPARABLE:\s*/, "");
  const topic = (REASON_TOPICS.find(([pattern]) => pattern.test(text)) || [null, "Other"])[1];
  const li = el("li");
  li.append(el("strong", {}, `${topic}: `), text);
  return li;
}

function verdictBlock(verdict) {
  const block = el("div", { class: verdict.comparable ? "verdict ok" : "verdict no" });
  if (verdict.comparable) {
    block.appendChild(el("p", { class: "verdict-title" }, "Comparable with care"));
    block.appendChild(el("p", { class: "note" }, "Hardware, scale, fuel phase and sensors all line up."));
    return block;
  }
  block.appendChild(el("p", { class: "verdict-title" }, "Not directly comparable"));
  const reasons = el("ul");
  (verdict.reasons || []).forEach((r) => reasons.appendChild(reasonItem(r)));
  block.appendChild(reasons);
  return block;
}

async function runCompare() {
  const acronyms = [...state.selected];
  const out = $("#compare-out");
  out.replaceChildren(el("p", { class: "note" }, `Comparing ${acronyms.join(", ")}...`));
  toggleDrawer("compare-panel", true);
  try {
    const found = await api("/api/compare", { acronyms });
    showError(null);
    out.replaceChildren(verdictBlock(found.verdict || {}));
    const names = found.investigations || acronyms;
    const tbl = el("table");
    const head = el("tr");
    head.appendChild(el("th", {}, "field"));
    names.forEach((a) => head.appendChild(el("th", {}, a)));
    tbl.appendChild(head);
    (found.rows || []).forEach((row) => {
      const tr = el("tr", { class: row.same ? "" : "differs" });
      tr.appendChild(el("td", {}, row.field));
      const values = Array.isArray(row.values) ? row.values : names.map((a) => row.values[a]);
      values.forEach((v) => tr.appendChild(el("td", {}, show(v))));
      tbl.appendChild(tr);
    });
    const wrap = el("div", { class: "table-wrap" });
    wrap.appendChild(tbl);
    out.appendChild(wrap);
    [["Can conclude", found.can_conclude], ["Cannot conclude", found.cannot_conclude]].forEach(([title, items]) => {
      out.appendChild(el("h3", {}, title));
      const ul = el("ul");
      [].concat(items || []).forEach((t) => ul.appendChild(el("li", {}, show(t))));
      out.appendChild(ul);
    });
  } catch (err) {
    out.replaceChildren(el("p", { class: "error" }, err.message));
  }
}

/* ---------- Ops: Crew and Controller over one SIMULATED stream ---------- */

const OPS = { steps: 180, seed: 1, compartments: ["habitat", "lab", "node"], speed: 1 };

function stopTelemetry() {
  clearInterval(state.timer);
  state.timer = null;
}

function startTelemetry(restart = false) {
  if (state.timer && !restart) return;
  stopTelemetry();
  if (restart) { state.step = 0; state.history = {}; state.lastT = null; }
  syncPlayback();
  if (state.paused) { tick(false); return; }
  tick();
  state.timer = setInterval(tick, 1000 / OPS.speed);
}

function syncPlayback() {
  const play = $("#ops-play");
  play.textContent = state.paused ? "Play" : "Pause";
  play.setAttribute("aria-label", state.paused ? "Play" : "Pause");
  play.setAttribute("aria-pressed", String(!!state.paused));
  $("#ops-scrub").max = OPS.steps - 1;
  $("#ops-scrub").value = Math.min(state.step, OPS.steps - 1);
}

function togglePlay() {
  if (state.paused && state.step >= OPS.steps) { state.paused = false; return startTelemetry(true); }
  state.paused = !state.paused;
  if (state.paused) { stopTelemetry(); syncPlayback(); } else startTelemetry(); // resumes at the current step
}

function opsBody() {
  const gravity = $("#ops-gravity").value;
  return {
    scenario: $("#tele-scenario").value || "nominal", seed: OPS.seed, steps: OPS.steps, step: state.step,
    compartments: OPS.compartments, material_class: $("#material-class").value.trim() || null,
    material_classes: state.materialClasses || {}, gravity_g: gravity === "" ? null : gravity,
  };
}

async function tick(advance = true) {
  // A redraw asked for mid-request (scrub, material or gravity change) runs once the request ends,
  // so it is never lost. Timer ticks are simply skipped; the next interval brings another.
  if (state.opsBusy) { if (!advance) state.pendingTick = true; return; }
  state.opsBusy = true;
  try {
    const view = await api("/api/ops", opsBody());
    const picker = $("#tele-scenario");
    if (!picker.options.length) {
      view.scenarios.forEach((name) => picker.appendChild(el("option", {}, name)));
      picker.value = view.scenario;
    }
    state.ops = view;
    recordHistory();
    showError(null);
    drawCrew();
    drawController();
    window.pyraOps = view;
    if (window.pyraTwin) window.pyraTwin.update(view);
    $("#ops-scrub").value = Math.min(state.step, OPS.steps - 1);
    if (advance) state.step += 1;
    if (state.step >= OPS.steps) { stopTelemetry(); state.paused = true; syncPlayback(); }
  } catch (err) {
    showError(err);
    stopTelemetry();
  } finally {
    state.opsBusy = false;
    if (state.pendingTick) { state.pendingTick = false; tick(false); }
  }
}

function crewCompartment() {
  const picker = $("#crew-compartment");
  const names = Object.keys(state.ops.compartments);
  if (picker.options.length !== names.length) {
    const keep = picker.value;
    picker.replaceChildren(...names.map((n) => el("option", {}, n)));
    picker.value = names.includes(keep) ? keep : names[0];
  }
  return state.ops.compartments[picker.value];
}

function crewName() { return $("#crew-compartment").value; }

// Remember the recent SIMULATED values per channel so a tile can show its trend.
function recordHistory() {
  if (state.ops.t === state.lastT) return;
  state.lastT = state.ops.t;
  Object.entries(state.ops.compartments).forEach(([name, room]) => room.tiles.forEach((tile) => {
    const key = `${name}:${tile.channel}`;
    const series = state.history[key] || (state.history[key] = []);
    if (typeof tile.value === "number") series.push(tile.value);
    if (series.length > 60) series.shift();
  }));
}

function sparkline(series) {
  const svg = svgEl("svg", { class: "spark", viewBox: "0 0 100 40", preserveAspectRatio: "none", "aria-hidden": "true" });
  if (series.length < 2) return svg;
  let lo = Math.min(...series), hi = Math.max(...series);
  if (hi - lo < 1e-9) { lo -= 1; hi += 1; }
  const pts = series.map((v, i) => [(i / (series.length - 1)) * 100, 36 - ((v - lo) / (hi - lo)) * 30]);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)} ${y.toFixed(2)}`).join("");
  svg.append(svgEl("path", { class: "area", d: `${line}L100 40L0 40Z` }), svgEl("path", { class: "line", d: line }));
  return svg;
}

function drawCrew() {
  if (!state.ops) return;
  $("#ops-clock").textContent = `t = ${state.ops.t} s of ${OPS.steps}`;
  const room = crewCompartment();
  if (!room) return;
  const banner = $("#banner");
  banner.className = `banner ${room.banner.status}`;
  banner.textContent = human(room.banner.text);
  const tiles = $("#tiles");
  tiles.replaceChildren();
  room.tiles.forEach((tile) => {
    const open = state.openTile === tile.channel;
    const button = el("button", { type: "button", class: `tile ${tile.status}`, "aria-expanded": String(open),
      "aria-controls": "tile-detail" });
    const value = el("span", { class: "value" });
    value.append(el("b", {}, show(tile.value)), el("span", { class: "unit" }, tile.unit));
    button.append(el("span", {}, tile.title), value, el("span", { class: `chip ${tile.status}` }, tile.status),
      sparkline(state.history[`${crewName()}:${tile.channel}`] || []));
    button.addEventListener("click", () => {
      state.openTile = open ? null : tile.channel;
      drawCrew();
    });
    tiles.appendChild(button);
  });
  const detail = $("#tile-detail");
  const chosen = room.tiles.find((t) => t.channel === state.openTile);
  detail.hidden = !chosen;
  if (chosen) {
    const list = el("ul");
    (chosen.reasons.length ? chosen.reasons : ["No alert, trend, grouped concern or evidence note for this channel."])
      .forEach((r) => list.appendChild(el("li", {}, r)));
    detail.replaceChildren(el("h3", {}, `${chosen.title}: ${chosen.status}`), list);
  }
}

function reasoningChain(reasoning) {
  const box = el("div", { class: "chain" });
  const observed = Object.entries(reasoning.observed || {})
    .filter(([k, v]) => typeof v === "number" && k !== "t").map(([k, v]) => `${k} ${show(v)}`).join(", ");
  box.appendChild(el("p", {}, `1. What the sensors show: ${observed}`));
  const matched = (reasoning.matched_experiments || []).map((m) => m.why);
  box.appendChild(el("p", {}, `2. Closest experiments we have: ${matched.join(" ") || "none"}`));
  const findings = (reasoning.measured_findings || []).map((f) => `${f.text} (source ${f.source}, ${f.page || "page unknown"})`);
  box.appendChild(el("p", {}, `3. What those experiments measured: ${findings.join("; ") || "none indexed"}`));
  box.appendChild(el("p", {}, `4. What they don't cover: ${(reasoning.not_covered || []).join("; ")}`));
  box.appendChild(el("p", {}, `5. How well the evidence fits: ${reasoning.confidence}`));
  return box;
}

function drawController() {
  if (!state.ops) return;
  const rooms = state.ops.compartments;
  // Compartment table, with a material class per compartment for the evidence check.
  const tbl = el("table");
  const head = el("tr");
  ["compartment", "material class", "O2 %", "pressure kPa", "CO ppm", "CO2 ppm", "smoke", "airflow cm/s", "temp C", "alerts"]
    .forEach((h) => head.appendChild(el("th", {}, h)));
  tbl.appendChild(head);
  Object.entries(rooms).forEach(([name, room]) => {
    const tr = el("tr");
    tr.appendChild(el("td", {}, name));
    const cell = el("td");
    const input = el("input", { size: 8, "aria-label": `Material class for ${name}` });
    input.value = (state.materialClasses || {})[name] || room.material_class || "";
    input.addEventListener("change", () => { state.materialClasses = { ...(state.materialClasses || {}), [name]: input.value.trim() }; });
    cell.appendChild(input);
    tr.appendChild(cell);
    const s = room.sample;
    [s.o2_percent, s.total_pressure_kpa, s.co_ppm, s.co2_ppm, s.smoke_level, s.flow_cm_s, s.temperature_c, room.alerts.length]
      .forEach((v) => tr.appendChild(el("td", {}, show(v))));
    tbl.appendChild(tr);
  });
  const wrap = el("div", { class: "table-wrap" });
  wrap.appendChild(tbl);
  if (!$("#compartments").contains(document.activeElement)) $("#compartments").replaceChildren(wrap);

  // Alerts, each with its reasoning chain.
  const list = $("#alerts");
  const openKeys = new Set([...list.querySelectorAll("details[open]")].map((d) => d.dataset.key));
  list.replaceChildren();
  Object.entries(rooms).forEach(([name, room]) => {
    room.alerts.forEach((alert) => {
      const key = `${name}:${alert.type}:${alert.channel}`;
      const details = el("details", { "data-key": key });
      if (openKeys.has(key)) details.open = true;
      details.appendChild(el("summary", {}, `${name}: ${alert.type} on ${alert.channel}. ${alert.message}`));
      details.appendChild(reasoningChain(room.reasoning));
      list.appendChild(details);
    });
  });
  if (!list.children.length) list.appendChild(el("p", { class: "note" }, "No alerts at this step."));

  // Combined view (a): evidence envelope per compartment.
  const envelope = $("#envelope");
  envelope.replaceChildren();
  state.ops.combined.envelope.forEach((check) => {
    const block = el("div", { class: check.outside && check.outside.length ? "envelope outside" : "envelope" });
    block.appendChild(el("p", {}, check.summary));
    const ul = el("ul");
    Object.entries(check.axes || {}).forEach(([axis, a]) => {
      const li = el("li");
      li.append(el("span", { class: `gap-class ${a.class || ""}` }, a.class || "not set"), ` ${human(a.summary)}`);
      ul.appendChild(li);
    });
    block.appendChild(ul);
    envelope.appendChild(block);
  });

  // Combined view (b): co-occurring concerns, each with the alerts it groups.
  const groups = $("#co-occurring");
  groups.replaceChildren();
  state.ops.combined.co_occurring.forEach((g) => {
    const details = el("details", { open: "" });
    const changes = Object.entries(g.changes).map(([ch, d]) => `${ch} ${d > 0 ? "+" : ""}${show(d)}`).join(", ");
    details.appendChild(el("summary", {}, `${g.compartment}: ${g.message} Changes over ${g.window_s} s: ${changes}. [${g.label}]`));
    const ul = el("ul");
    g.members.forEach((m) => ul.appendChild(el("li", {}, `${m.type} on ${m.channel}: ${m.message}`)));
    if (!g.members.length) ul.appendChild(el("li", {}, "No single-channel alert yet; the channels moved together."));
    details.appendChild(ul);
    groups.appendChild(details);
  });
  if (!groups.children.length) groups.appendChild(el("p", { class: "note" }, "No rule matched at this step."));
}

/* ---------- Builder: early-design evidence check ---------- */

const PSI_IN_KPA = 6.894757293168; // same constant as pyra/units.py

// Same rules as builder.validate on the server; the server checks again, so this is only for instant messages.
function validateBuilder(body) {
  const errors = {};
  const num = (key, label) => {
    const raw = body[key];
    if (raw === undefined || raw === null || String(raw).trim() === "") return null;
    const n = Number(raw);
    if (!Number.isFinite(n)) { errors[key] = `${label} must be a number.`; return null; }
    return n;
  };
  const o2 = num("o2_percent", "O2");
  if (o2 !== null && (o2 < 0 || o2 > 100)) errors.o2_percent = "O2 must be between 0 and 100 %.";
  const p = num("pressure", "Pressure");
  if (p !== null && p <= 0) errors.pressure = "Pressure must be greater than 0.";
  const lo = num("flow_min", "Flow min"), hi = num("flow_max", "Flow max");
  if (lo !== null && lo < 0) errors.flow_min = "Flow cannot be negative.";
  if (hi !== null && hi < 0) errors.flow_max = "Flow cannot be negative.";
  if (lo !== null && hi !== null && !errors.flow_min && !errors.flow_max && lo > hi) errors.flow_max = "Flow max must be at least flow min.";
  const g = body.preset === "custom" ? num("gravity_g", "Gravity") : null;
  if (g !== null && g < 0) errors.gravity_g = "Gravity cannot be negative.";
  return errors;
}

function builderBody() {
  const form = new FormData($("#builder"));
  const body = {};
  ["preset", "o2_percent", "pressure", "pressure_unit", "flow_min", "flow_max", "flow_unit", "gravity_g", "pillar", "mission_duration"]
    .forEach((k) => { const v = form.get(k); if (v !== null && String(v).trim() !== "") body[k] = String(v).trim(); });
  const picked = form.getAll("material");
  const other = (form.get("other_materials") || "").split(",").map((m) => m.trim()).filter(Boolean);
  body.materials = [...picked, ...other];
  if (body.preset !== "custom") delete body.gravity_g;
  return body;
}

function showFieldErrors(errors) {
  document.querySelectorAll("#builder .field-error").forEach((span) => { span.textContent = ""; });
  document.querySelectorAll("#builder input").forEach((input) => input.removeAttribute("aria-invalid"));
  Object.entries(errors).forEach(([key, message]) => {
    const span = document.querySelector(`#builder [data-error=${key}]`)
      || document.querySelector(`#builder [data-field=${key}] .field-error`)
      || document.querySelector("#builder [data-field=materials] .field-error");
    if (span) span.textContent = message;
    const input = document.querySelector(`#builder [name=${key}]`);
    if (input) input.setAttribute("aria-invalid", "true");
  });
}

function drawPpo2() {
  const form = new FormData($("#builder"));
  const o2 = Number(form.get("o2_percent")), p = Number(form.get("pressure"));
  const filled = String(form.get("o2_percent") || "").trim() !== "" && String(form.get("pressure") || "").trim() !== "";
  const kpa = form.get("pressure_unit") === "psi" ? p * PSI_IN_KPA : p;
  const ok = filled && Number.isFinite(o2 * kpa) && o2 >= 0 && o2 <= 100 && p > 0;
  $("#b-ppo2").value = ok ? (o2 / 100 * kpa).toFixed(2) : "set a valid O2 and pressure";
  $("#b-ppo2").classList.toggle("empty", !ok);
}

function applyPreset() {
  const preset = (state.builderOptions.presets || []).find((p) => p.id === $("#b-preset").value);
  if (!preset) return;
  const form = $("#builder");
  const gravity = form.elements.gravity_g;
  gravity.readOnly = preset.id !== "custom";
  if (preset.id !== "custom") gravity.value = preset.gravity_g ?? "";
  if (preset.o2_percent !== null && preset.o2_percent !== undefined) form.elements.o2_percent.value = preset.o2_percent;
  if (preset.pressure !== null && preset.pressure !== undefined) {
    form.elements.pressure.value = preset.pressure;
    form.querySelectorAll("[name=pressure_unit]").forEach((r) => { r.checked = r.value === preset.pressure_unit; });
  }
  const verified = preset.verified_by ? `verified by ${preset.verified_by}` : "not yet verified by the team";
  const atmosphere = preset.o2_percent === null ? "No cited atmosphere for this preset; type your own." : `Atmosphere: ${preset.atmosphere_source.replace(/\.$/, "")}.`;
  $("#b-preset-note").textContent = `Gravity: ${preset.gravity_source.replace(/\.$/, "")}. ${atmosphere} (${verified})`;
  drawPpo2();
}

function chip(cell) {
  if (!cell || cell.state === "NOT_EVALUATED") return el("span", { class: "gap-class unset" }, "not set");
  return el("span", { class: `gap-class ${cell.class}`, title: cell.summary }, cell.class);
}

function drawHints(hints) {
  document.querySelectorAll("#builder .hint").forEach((h) => h.replaceChildren());
  Object.entries(hints || {}).forEach(([field, cell]) => {
    const span = document.querySelector(`#builder [data-hint=${field}]`) || document.querySelector(`#builder [data-field=${field}] .hint`);
    if (!span || cell.state === "NOT_EVALUATED") return;
    span.append(chip(cell), " ", human(cell.summary));
  });
}

function drawBuilderResult(found) {
  const out = $("#builder-out");
  drawHints(found.hints);
  const parts = [];
  const head = el("p", { class: "note" });
  head.append(`Based on the values you entered. O2 partial pressure: ${found.derived.o2_partial_kpa === null ? "not computed (O2 or pressure not set)" : found.derived.o2_partial_kpa + " kPa"}.`
    + (found.mission_duration ? ` Mission duration: ${found.mission_duration} (label only).` : ""));
  parts.push(el("h3", {}, "Materials × axis coverage"), head);

  const tbl = el("table", { class: "coverage-table" });
  const hr = el("tr");
  ["Material", "O2", "Pressure", "Flow (min / max)", "Gravity", "Material class", "Pillar", "All together", "Nearest evidence"]
    .forEach((h) => hr.appendChild(el("th", { scope: "col" }, h)));
  tbl.appendChild(hr);
  found.table.forEach((row) => {
    const tr = el("tr");
    const name = el("td");
    name.append(el("strong", {}, row.material), row.in_index ? "" : el("div", { class: "note" }, "not in index"));
    tr.appendChild(name);
    ["o2_percent", "pressure"].forEach((k) => { const td = el("td"); td.appendChild(chip(row[k])); tr.appendChild(td); });
    const flow = el("td");
    row.flow.forEach((f, i) => { if (i) flow.append(" / "); flow.appendChild(chip(f)); });
    tr.appendChild(flow);
    ["gravity", "material_class", "pillar"].forEach((k) => { const td = el("td"); td.appendChild(chip(row[k])); tr.appendChild(td); });
    const combo = el("td");
    row.combination.forEach((c, i) => { if (i) combo.append(" / "); combo.appendChild(chip({ class: c.class, state: c.class ? "EVALUATED" : "NOT_EVALUATED", summary: c.summary })); });
    tr.appendChild(combo);
    const near = el("td");
    if (row.nearest) {
      const label = `${row.nearest.acronym}${row.nearest.run_id ? " / " + row.nearest.run_id : ""}`;
      near.append(`${label}: `);
      if (row.nearest.url) near.appendChild(el("a", { href: row.nearest.url, target: "_blank", rel: "noopener" }, row.nearest.source || "source"));
      else near.append(row.nearest.source || "source title not indexed");
    } else near.append("no indexed evidence");
    tr.appendChild(near);
    tbl.appendChild(tr);
  });
  const wrap = el("div", { class: "table-wrap" });
  wrap.appendChild(tbl);
  parts.push(wrap, el("p", { class: "note" }, "Hover a class to read the full line. Flow is checked at both ends of the range."));

  parts.push(el("h3", {}, "Suggested experiments"));
  const proposals = el("ul");
  found.proposals.forEach((p) => {
    const li = el("li");
    const text = human(p.text);
    li.append(text.charAt(0).toUpperCase() + text.slice(1));
    proposals.appendChild(li);
  });
  if (!found.proposals.length) proposals.appendChild(el("li", { class: "note" }, "No gap to propose an experiment for."));
  parts.push(proposals);

  parts.push(el("h3", {}, "Design notes"));
  const notes = el("ul");
  found.design_notes.forEach((n) => {
    const li = el("li");
    if (Array.isArray(n.guidance)) {
      li.append(el("strong", {}, `${n.subject}: `), n.guidance.map((g) => `${g.text} [${g.source}, ${g.page}]`).join(" | "));
    } else {
      li.append(el("strong", {}, `${n.subject}: `), n.guidance);
    }
    notes.appendChild(li);
  });
  parts.push(notes);
  out.replaceChildren(...parts);
}

// Error boundary: nothing thrown while checking or drawing reaches the page as a crash.
function builderBoundary(fn) {
  return async (...args) => {
    const box = $("#builder-boundary");
    try {
      box.hidden = true;
      await fn(...args);
    } catch (err) {
      console.error("[PYRA builder]", err);
      box.textContent = `The Builder hit a problem and stopped this check: ${err.message}. Your inputs are kept; change a field and try again.`;
      box.hidden = false;
    }
  };
}

async function runBuilder(event) {
  if (event) event.preventDefault();
  const body = builderBody();
  const errors = validateBuilder(body);
  showFieldErrors(errors);
  if (Object.keys(errors).length) {
    drawHints({});
    $("#builder-out").replaceChildren(el("p", { class: "note" }, "Fix the highlighted fields to see coverage."));
    return;
  }
  const found = await api("/api/builder/check", body);
  if (!found.valid) {
    showFieldErrors(found.errors);
    drawHints({});
    $("#builder-out").replaceChildren(el("p", { class: "note" }, "Fix the highlighted fields to see coverage."));
    return;
  }
  drawBuilderResult(found);
}

async function loadBuilder() {
  if (state.builderOptions) return;
  state.builderOptions = await api("/api/builder/options");
  const presetPicker = $("#b-preset");
  presetPicker.replaceChildren(...state.builderOptions.presets.map((p) => el("option", { value: p.id }, p.name)));
  const box = $("#b-materials");
  box.replaceChildren(...state.builderOptions.materials.map((m) => {
    const label = el("label");
    label.append(el("input", { type: "checkbox", name: "material", value: m.category }),
      ` ${m.category} `, el("span", { class: "note" }, `(${m.investigations} inv, ${m.runs} runs)`));
    return label;
  }));
  if (!state.builderOptions.materials.length) box.appendChild(el("p", { class: "note" }, "No material classes indexed yet."));
  presetPicker.value = "custom";
  applyPreset();
}

async function loadWeakness() {
  try {
    const found = await api("/api/research/weakness");
    $("#weakness").replaceChildren(table(Array.isArray(found) ? found : found.rows || [found]));
    showError(null);
  } catch (err) { showError(err); }
}

async function runOpportunities() {
  try {
    const found = await api("/api/research/opportunities", { scenario: scenarioBody() });
    $("#opportunities").replaceChildren(found.length ? table(found)
      : el("p", { class: "note" }, "Every set axis is DIRECTLY_TESTED, or no axis is set, so there is nothing to rank."));
    showError(null);
  } catch (err) { showError(err); }
}

// "ACRONYM=2012" lines -> {ACRONYM: "2012"}
function yearsOf(text) {
  const years = {};
  (text || "").split(/\n|,/).map((s) => s.trim()).filter(Boolean).forEach((line) => {
    const [key, year] = line.split("=").map((s) => s.trim());
    if (key && year) years[key] = year;
  });
  return years;
}

async function runBacktest(event) {
  event.preventDefault();
  const form = new FormData($("#backtest"));
  const body = {
    cutoff_year: form.get("cutoff_year"), years: yearsOf(form.get("years")),
    checks: [{ name: "current scenario", scenario: scenarioBody(), should_flag: form.get("should_flag") === "on" }],
  };
  try {
    const found = await api("/api/research/backtest", body);
    $("#backtest-out").replaceChildren(
      el("p", {}, `Kept before ${found.cutoff_year}: ${found.investigations_kept.join(", ") || "none"}. `
        + `Dropped for having no year: ${found.undated_dropped.join(", ") || "none"}. Hits ${found.hits}, misses ${found.misses}.`),
      table(found.checks));
    showError(null);
  } catch (err) { showError(err); }
}

/* ---------- AI assistant (Groq through /api/ask) ---------- */

function mk(tag, cls, ...kids) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  kids.flat().forEach((k) => { if (k !== null && k !== undefined && k !== false) node.append(k instanceof Node ? k : String(k)); });
  return node;
}

async function loadAskModel() {
  const chip = $("#ask-model");
  if (chip.dataset.done) return;
  try {
    const info = await api("/api/agents");
    chip.textContent = info.live ? String(info.llm).replace(/ \(checked.*$/, "") : "offline: passages only";
    chip.dataset.state = info.live ? "live" : "off";
    chip.title = info.live ? "Answers come from this model and are checked against PYRA's rules." : "Set GROQ_API_KEY in .env to turn on the model.";
    chip.dataset.done = "1";
  } catch { chip.textContent = "unknown"; }
}

// Answer text with [S1, S2] turned into chips that jump to the source row.
function citedText(text, msgId) {
  const frag = document.createDocumentFragment();
  String(text).split("\n").forEach((line) => {
    if (!line.trim()) return;
    const p = mk("p", /^\s*(\(?[abc]\)|#+\s|What the sources|What this means|Limits|Confidence:)/i.test(line) ? "ai-sec" : "");
    const clean = line.replace(/^#+\s*/, "");
    let last = 0;
    clean.replace(/\[(S\d+(?:\s*,\s*S\d+)*)\]/g, (m, ids, at) => {
      p.append(clean.slice(last, at));
      ids.split(/\s*,\s*/).forEach((id) => {
        const a = mk("a", "ai-cite", id);
        a.href = `#${msgId}-${id}`;
        a.addEventListener("click", (e) => {
          e.preventDefault();
          const row = document.getElementById(`${msgId}-${id}`);
          if (!row) return;
          row.closest("details").open = true;
          row.scrollIntoView({ block: "nearest", behavior: "smooth" });
          row.classList.add("flash");
          setTimeout(() => row.classList.remove("flash"), 1200);
        });
        p.append(a);
      });
      last = at + m.length;
      return m;
    });
    p.append(clean.slice(last));
    frag.append(p);
  });
  return frag;
}

/* ---------- Research assistant ---------- */

const EXAMPLES = [
  "How does flow speed change flame spread?",
  "Is my scenario covered by the tests?",
  "Which investigations are closest to my scenario?",
];
const HEADINGS = /^\s*(?:\(?[abc]\)\s*)?(?:what the sources report\s*)?\(?(MEASURED|INTERPRETATION|Limits(?: and gaps)?)\)?:?\s*$/i;

// One line of answer text, with every [S1, S2] turned into buttons that light up the passage.
function withCitations(line) {
  const p = el("p");
  line.split(/(\[S\d+(?:\s*,\s*S\d+)*\])/).forEach((part) => {
    const ids = part.match(/^\[(S\d+(?:\s*,\s*S\d+)*)\]$/);
    if (!ids) return p.append(part);
    ids[1].split(",").map((id) => id.trim()).forEach((id) => {
      const cite = el("button", { type: "button", class: "cite", "data-source": id }, `[${id}]`);
      cite.addEventListener("click", () => lightSource(id));
      p.append(cite);
    });
  });
  return p;
}

function lightSource(id) {
  document.querySelectorAll("#agent-sources li").forEach((li) => li.classList.toggle("lit", li.dataset.source === id));
  const target = document.querySelector(`#agent-sources li[data-source="${id}"]`);
  if (target) target.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function drawAnswer(text) {
  const box = $("#agent-answer");
  box.replaceChildren();
  text.split("\n").filter((line) => line.trim()).forEach((line) => {
    const heading = line.match(HEADINGS);
    if (heading) return box.appendChild(el("h4", {}, heading[1].toUpperCase()));
    const node = withCitations(line);
    if (/^\s*Confidence:/i.test(line)) node.className = "confidence";
    box.appendChild(node);
  });
}

function drawCheck(found) {
  const box = $("#agent-check");
  box.hidden = false;
  box.className = found.passed ? "agent-check" : "agent-check failed";
  box.replaceChildren();
  if (found.passed) {
    box.textContent = `Passed the answer checks${found.revised ? " after one rewrite" : ""}. Planner: ${found.planner}.`;
    return;
  }
  box.append(`Answer withheld: it broke ${found.problems.length} rule(s) even after a rewrite.`);
  const list = el("ul");
  found.problems.forEach((problem) => list.appendChild(el("li", {}, problem)));
  const draft = el("details");
  draft.append(el("summary", {}, "Show the rejected draft"), el("pre", {}, found.draft || ""));
  box.append(list, draft);
}

function stepSummary(step) {
  const out = step.output || {};
  if (step.error) return out.error;
  if (out.passages) return out.passages.length ? `${out.passages.length} passage(s): ${out.passages.map((p) => p.id).join(", ")}` : out.note;
  if (out.investigations) return `${out.investigations.length} investigation(s)`;
  if (out.ranked) return out.ranked.map((r) => `${r.acronym} ${show(r.total)}`).join(", ");
  if (out.axes) return Object.entries(out.axes).filter(([, a]) => a.class).map(([axis, a]) => `${axis} ${a.class}`).join(", ");
  if ("comparable" in out) return out.comparable ? "comparable" : "not directly comparable";
  return "";
}

function drawSteps(found) {
  const list = $("#agent-steps");
  list.replaceChildren();
  found.steps.forEach((step) => {
    const li = el("li", { class: step.error ? "error" : "" });
    const args = Object.keys(step.input || {}).length ? JSON.stringify(step.input) : "";
    li.append(el("code", {}, `${step.tool}(${args})`), el("div", { class: "note" }, stepSummary(step)));
    const raw = el("details");
    raw.append(el("summary", {}, "result"), el("pre", {}, JSON.stringify(step.output, null, 2)));
    li.appendChild(raw);
    list.appendChild(li);
  });
  if (found.stopped) list.appendChild(el("li", { class: "error" }, found.stopped));
  if (!found.steps.length) list.appendChild(el("li", { class: "note" }, "No tools were called."));
}

function drawSources(found) {
  const list = $("#agent-sources");
  list.replaceChildren();
  (found.context || []).forEach((p) => {
    const li = el("li", { "data-source": p.id });
    li.append(el("strong", {}, `[${p.id}] ${p.investigation || "source"}`),
      el("span", { class: "note" }, ` ${p.page || "page not given"}, ${p.section || ""}`),
      el("div", {}, p.text));
    list.appendChild(li);
  });
  if (!list.children.length) list.appendChild(el("li", { class: "note" }, "No passage was retrieved."));
}

async function runAgent(event) {
  event.preventDefault();
  const form = new FormData($("#agent-form"));
  const body = { question: form.get("question"), audience: form.get("audience") };
  if (form.get("use_scenario")) body.scenario = scenarioBody();
  if (form.get("planner")) body.planner = form.get("planner");
  const button = $("#agent-form button[type=submit]");
  button.disabled = true;
  $("#agent-check").hidden = true;
  $("#agent-answer").replaceChildren(el("p", { class: "busy" }, "Planning and running tools..."));
  try {
    const found = await api("/api/agent", body);
    showError(null);
    drawCheck(found);
    if (found.answer) drawAnswer(found.answer);
    else $("#agent-answer").replaceChildren(el("p", { class: "note" }, "Nothing is shown because the answer failed its checks. The steps and passages are still listed."));
    drawSteps(found);
    drawSources(found);
  } catch (err) {
    $("#agent-answer").replaceChildren(el("p", { class: "note" }, "No answer."));
    showError(err);
  } finally {
    button.disabled = false;
  }
}

async function loadAgentStatus() {
  const info = $("#planner-info");
  try {
    const status = await api("/api/agent/status");
    const ready = [];
    if (status.claude_ready) ready.push(`Claude ready (${status.model})`);
    if (status.groq_ready) ready.push(`Groq ready (${status.groq_model})`);
    const models = ready.length ? ready.join(", ") : "No model configured, so answers come from the offline templates";
    info.textContent = `Default planner: ${status.default}. ${models}.`;
  } catch (err) {
    info.textContent = `Assistant unavailable: ${err.message}`;
  }
  const examples = $("#agent-examples");
  EXAMPLES.forEach((text) => {
    const chip = el("button", { type: "button" }, text);
    chip.addEventListener("click", () => { $("#agent-form [name=question]").value = text; });
    examples.appendChild(chip);
  });
}

let askCount = 0;
async function runAsk(event) {
  event.preventDefault();
  const form = $("#ask");
  const data = new FormData(form);
  const question = String(data.get("question") || "").trim();
  if (!question) return;
  const log = $("#ask-log");
  const hints = log.querySelector(".ai-hints");
  if (hints) hints.remove();
  form.elements.question.value = "";
  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  log.append(mk("div", "ai-q", question));
  const bubble = mk("div", "ai-a pending", mk("span", "ai-typing", mk("i"), mk("i"), mk("i")));
  log.append(bubble);
  log.scrollTop = log.scrollHeight;
  const msgId = `ai${++askCount}`;
  try {
    const found = await api("/api/ask", { question, audience: data.get("audience") });
    bubble.classList.remove("pending");
    bubble.replaceChildren(mk("div", "ai-head", mk("span", "ai-label", found.label || "INTERPRETATION"),
      mk("span", "ai-meta", found.live && found.text ? (found.model || "model") : "retrieval only"),
      found.retried ? mk("span", "ai-meta", "rewritten once to pass the rules") : null));
    if (found.text) bubble.append(citedText(found.text, msgId));
    else bubble.append(mk("p", "", (found.context || []).length
      ? "No language model is connected, so here are the passages that match your question."
      : "No data found in the indexed sources."));
    if (found.model_error) bubble.append(mk("p", "ai-warn", `The model could not be reached (${found.model_error}). Showing the passages instead.`));
    if ((found.problems || []).length) {
      bubble.append(mk("details", "ai-checks", mk("summary", "", `${found.problems.length} rule check(s) still flagged: read with care`),
        mk("ul", "", found.problems.map((p) => mk("li", "", p)))));
    } else if (found.text && found.live) bubble.append(mk("div", "ai-ok", "Passed PYRA's rule checks: citations, numbers, wording."));
    const ctx = found.context || [];
    if (ctx.length) {
      const rows = ctx.map((c) => {
        const where = [c.investigation, c.source_id, c.page ? `p. ${c.page}` : null, c.section].filter(Boolean).join(" · ");
        const row = mk("div", "ai-src", mk("b", "", c.id), mk("span", "ai-where", where), mk("div", "ai-snip", String(c.text || "").slice(0, 420)));
        row.id = `${msgId}-${c.id}`;
        return row;
      });
      const src = mk("details", "ai-sources", mk("summary", "", `Sources (${ctx.length})`), rows);
      if (!found.text) src.open = true;
      bubble.append(src);
    }
    showError(null);
  } catch (err) {
    bubble.classList.remove("pending");
    bubble.replaceChildren(mk("p", "ai-warn", err.message || String(err)));
  }
  btn.disabled = false;
  form.elements.question.focus();
  log.scrollTop = log.scrollHeight;
}

/* ---------- start ---------- */

async function start() {
  ["#x-axis", "#y-axis"].forEach((sel, i) => {
    Object.entries(QUANTITIES).forEach(([key, label]) => $(sel).appendChild(el("option", { value: key }, label)));
    $(sel).value = i === 0 ? "o2_percent" : "flow_speed";
    $(sel).addEventListener("change", drawMap);
  });
  $("#scenario").addEventListener("submit", (e) => { e.preventDefault(); runCoverage(); });
  const fill = (r) => r.style.setProperty("--p", `${((r.value - r.min) / (r.max - r.min)) * 100}%`);
  fill($("#scenario [name=gravity_g]"));
  $("#scenario [name=gravity_g]").addEventListener("input", (e) => {
    fill(e.target);
    $("#g-out").value = Number(e.target.value).toFixed(2);
    $("#scenario [name=gravity_set]").checked = true;
  });
  $("#report-btn").addEventListener("click", openReport);
  $("#report-menu").addEventListener("click", (e) => { e.target.closest("details").open = false; openReport(); });
  $("#compare-btn").addEventListener("click", runCompare);
  const checkBuilder = builderBoundary(runBuilder);
  $("#builder").addEventListener("submit", checkBuilder);
  $("#builder").addEventListener("input", builderBoundary(async () => { drawPpo2(); showFieldErrors(validateBuilder(builderBody())); }));
  $("#b-preset").addEventListener("change", builderBoundary(async () => { applyPreset(); await runBuilder(); }));
  $("#ask").addEventListener("submit", runAsk);
  $("#agent-form").addEventListener("submit", runAgent);
  $("#ask-toggle").addEventListener("click", () => { toggleDrawer("ask-panel"); loadAskModel(); if (!$("#ask-panel").hidden) $("#ask [name=question]").focus(); });
  document.querySelectorAll(".ai-hint").forEach((b) => b.addEventListener("click", () => {
    $("#ask [name=question]").value = b.textContent;
    $("#ask").requestSubmit();
  }));
  $("#demo-run").addEventListener("click", () => {
    if (!location.hash.startsWith("#/agents")) location.hash = "#/agents";
    setTimeout(() => window.pyraAgents && window.pyraAgents.demo(), 0);
  });
  $("#scrim").addEventListener("click", () => document.querySelectorAll(".drawer:not([hidden])").forEach((d) => toggleDrawer(d.id, false)));
  document.querySelectorAll(".drawer-close").forEach((b) => b.addEventListener("click", () => toggleDrawer(b.dataset.close, false)));
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") document.querySelectorAll(".drawer:not([hidden])").forEach((d) => toggleDrawer(d.id, false));
  });
  $("#opportunities-btn").addEventListener("click", runOpportunities);
  $("#backtest").addEventListener("submit", runBacktest);
  $("#tele-scenario").addEventListener("change", () => startTelemetry(true));
  $("#crew-compartment").addEventListener("change", drawCrew);
  ["#material-class", "#ops-gravity"].forEach((sel) => $(sel).addEventListener("change", () => {
    tick(false);
  }));
  $("#ops-play").addEventListener("click", togglePlay);
  $("#ops-restart").addEventListener("click", () => startTelemetry(true));
  $("#ops-speed").addEventListener("change", (e) => {
    OPS.speed = Number(e.target.value) || 1;
    if (state.timer) { stopTelemetry(); state.timer = setInterval(tick, 1000 / OPS.speed); }
  });
  $("#ops-scrub").addEventListener("input", (e) => {
    state.step = Number(e.target.value);
    state.history = {}; state.lastT = null;
    tick(false);
  });
  $("#large-text").addEventListener("click", (e) => {
    const on = document.body.classList.toggle("large");
    e.target.setAttribute("aria-pressed", on);
  });
  window.addEventListener("resize", drawMap);
  window.addEventListener("hashchange", route);

  try {
    [state.investigations, state.runs] = await Promise.all([api("/api/investigations"), api("/api/runs")]);
  } catch (err) { return showError(err); }
  drawPicks();
  route();
  runCoverage();
  loadAgentStatus();
}

start();
