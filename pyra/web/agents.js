// PYRA Agents tab: an agent control room in the style of the HUKUM prototype.
// Left: the mission form and the route. Centre: a stats strip, the live agent graph
// (supervisor hub, agents on an orbit, packets along the active edge, a speech bubble)
// and result tabs. Right: the approval card and a chat-style activity feed.
// Plain JavaScript, no libraries. Every number comes from the API; this file lays it out.
// Talks to: GET /api/agents, GET /api/builder/options, POST /api/agents/run,
// GET /api/agents/stream/<id> (SSE), POST /api/agents/resume/<id>, POST /api/agents/stop/<id>, POST /api/agents/ask.
(function () {
  "use strict";

  /* ------------------------------------------------------------------ agents */
  const AGENTS = [
    { id: "librarian", label: "Librarian", short: "Librarian", key: "corpus", tab: "Librarian",
      role: "Reads the PYRA evidence database and says what it covers and whether any sheet is marked NOT REAL DATA." },
    { id: "mission_profiler", label: "Mission Profiler", short: "Mission", key: "mission", tab: "Mission",
      role: "Turns a preset and your typed values into one HYPOTHETICAL scenario, with the source of every value." },
    { id: "physicist", label: "Physicist", short: "Physicist", key: "physics", tab: "Physicist",
      role: "Compares buoyant flow with ventilation flow (ILLUSTRATIVE scaling) to say how close a normal-gravity test is." },
    { id: "evidence_ranker", label: "Evidence Ranker", short: "Evidence Ranker", key: "ranking", tab: "Claims",
      role: "Ranks investigations and drafts one labelled, cited claim per material." },
    { id: "skeptic", label: "Skeptic", short: "Skeptic", key: "review", tab: "Skeptic",
      role: "Checks every claim against PYRA's rules and sends the draft back until it is honest." },
    { id: "incident_analyst", label: "Incident Analyst", short: "Incidents", key: "incidents", tab: "Past fires",
      role: "Breaks Apollo 1, Apollo 13 and Mir into a fire chain and finds the same links in the scenario." },
    { id: "gap_hunter", label: "Gap Hunter", short: "Gap Hunter", key: "gaps", tab: "Gaps",
      role: "Classifies every axis, scores data opportunities and proposes the experiment that closes the biggest gap." },
    { id: "safety_officer", label: "Safety Officer", short: "Safety Officer", key: "actions", tab: "Actions",
      role: "Turns the findings into evidence actions and waits for a person to approve them." },
  ];
  const AGENT_IDS = AGENTS.map((a) => a.id);
  const EXTRA = {
    supervisor: { id: "supervisor", label: "Supervisor", short: "Supervisor", role: "Plans the route from the goal and mode, then hands over to one agent at a time." },
    reporter: { id: "reporter", label: "Reporter", short: "Reporter", key: "report", role: "Writes the briefing with KPIs, labels and a markdown copy." },
  };
  const COLORS = {
    supervisor: "#ff8f4d", reporter: "#c3c5c9",
    librarian: "#6fb4ff", mission_profiler: "#36cfc9", physicist: "#85a5ff", evidence_ranker: "#ffc53d",
    skeptic: "#b39cff", incident_analyst: "#ff7a45", gap_hunter: "#5ed69c", safety_officer: "#ff85c0",
  };
  const ICONS = {
    supervisor: "M9 3h6v5H9zM12 8v4M5 16v-4h14v4M3 16h4v5H3zM10 16h4v5h-4zM17 16h4v5h-4z",
    reporter: "M6 3h9l3 3v15H6zM9 9h6M9 13h6M9 17h4",
    librarian: "M4 4h4v16H4zM10 4h4v16h-4zM15.5 5.2l3.8-1 3.4 14.6-3.8 1z",
    mission_profiler: "M12 2c3 2.2 5 6 5 10l-2 4H9l-2-4c0-4 2-7.8 5-10zM12 8.5a1.6 1.6 0 100 3.2 1.6 1.6 0 000-3.2zM9 16l-2.5 4M15 16l2.5 4",
    physicist: "M12 3c1 4 5 5 5 10a5 5 0 01-10 0c0-3 2-4 2-6 1 1 2 2 2 3 0-3 0-5 1-7z",
    evidence_ranker: "M4 20V11M10 20V5M16 20v-6M2 20h20",
    skeptic: "M10 4a6 6 0 100 12 6 6 0 000-12zM14.5 14.5L20 20M8 10h4",
    incident_analyst: "M3.5 12a8.5 8.5 0 102.5-6L3.5 8.5M3.5 3.5v5h5M12 7.5V12l3 3",
    gap_hunter: "M12 3a9 9 0 100 18 9 9 0 000-18zM12 7.5a4.5 4.5 0 100 9 4.5 4.5 0 000-9zM12 11.2v1.6",
    safety_officer: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6zM9 12l2 2 4-4",
  };
  const meta = (id) => AGENTS.find((a) => a.id === id) || EXTRA[id] || { id, label: String(id || "system"), short: String(id || "system"), role: "" };
  const colorOf = (id) => COLORS[id] || "#8f949c";

  const MODES = [["full", "Full evidence check"], ["evidence", "Evidence claims only"], ["gaps", "Gaps and next experiment"],
    ["lessons", "Lessons from past fires"], ["custom", "Custom: pick agents"]];
  const SUB = { idle: "waiting", active: "working", done: "done", interrupt: "needs approval", error: "error", skipped: "not in route" };

  // One-click demo of the whole workflow: a fixed sample scenario, every agent, shadow mode (no approval pause).
  // The header's Demo run: a fuller story than the test run. Mars transit, every agent,
  // a pause before each agent so the graph can be followed, and the human approval step.
  const DEMO_RUN = { preset: "mars_transit", o2_percent: "", pressure: "", gravity_g: "", flow_speed: "5",
    materials: "PMMA, cotton", pillar: "", mode: "full", pilot_mode: "approve",
    goal: "Demo: what is really known about a cabin fire on a Mars transit crew module, and what should be tested next?" };
  const DEMO_PACE_S = 0.9;
  const TEST_RUN = { preset: "lunar_surface", o2_percent: "", pressure: "", gravity_g: "", flow_speed: "10",
    materials: "PMMA, cotton", pillar: "", mode: "full", pilot_mode: "shadow",
    goal: "Test run: sample lunar habitat evidence check" };

  /* ------------------------------------------------------------------ helpers */
  const SVGNS = "http://www.w3.org/2000/svg";
  function setAttrs(n, attrs) {
    Object.entries(attrs || {}).forEach(([k, v]) => {
      if (v === false || v === null || v === undefined) return;
      if (k === "style" && typeof v === "object") Object.entries(v).forEach(([sk, sv]) => n.style.setProperty(sk.replace(/[A-Z]/g, (c) => "-" + c.toLowerCase()), sv));
      else if (k.startsWith("on") && typeof v === "function") n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    });
  }
  function append(n, kids) { kids.flat(Infinity).forEach((kid) => { if (kid !== null && kid !== undefined && kid !== false) n.append(kid instanceof Node ? kid : String(kid)); }); }
  function h(tag, attrs, ...kids) { const n = document.createElement(tag); setAttrs(n, attrs); append(n, kids); return n; }
  function s(tag, attrs, ...kids) { const n = document.createElementNS(SVGNS, tag); setAttrs(n, attrs); append(n, kids); return n; }
  const q = (sel, root) => (root || document).querySelector(sel);
  const isObj = (v) => v && typeof v === "object" && !Array.isArray(v);
  const fmt = (v) => (v === null || v === undefined ? "not set" : typeof v === "number" ? String(+v.toPrecision(4)) : typeof v === "boolean" ? (v ? "yes" : "no") : String(v));
  const human = (k) => String(k || "").replace(/_/g, " ").replace(/\bo2\b/gi, "O2").replace(/^./, (c) => c.toUpperCase());
  const clock = (t) => (t ? new Date(t > 1e12 ? t : t * 1000).toTimeString().slice(0, 8) : "");
  const LABEL_TONE = { MEASURED: "ok", DERIVED: "info", HYPOTHETICAL: "warn", INTERPRETATION: "violet", PROPOSAL: "accent", ILLUSTRATIVE: "muted", MIXED: "muted" };
  const label = (text) => h("span", { class: `ag-chip ${LABEL_TONE[String(text || "").toUpperCase()] || "muted"}` }, text || "");
  const chip = (text, tone) => h("span", { class: `ag-chip ${tone || "muted"}` }, text);

  function icon(id, size) {
    return s("svg", { viewBox: "0 0 24 24", width: size || 16, height: size || 16, fill: "none", stroke: "currentColor", "stroke-width": "1.9",
      "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true", class: "ag-ico" }, s("path", { d: ICONS[id] || "M12 4a8 8 0 100 16 8 8 0 000-16z" }));
  }
  function avatar(id, size) {
    const c = colorOf(id), px = size || 26;
    return h("span", { class: "ag-av", style: { width: `${px}px`, height: `${px}px`, color: c, background: `${c}1f`, borderColor: `${c}66` } }, icon(id, Math.round(px * 0.58)));
  }

  async function call(path, body) {
    const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
    const res = await fetch(path, opts);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `${path} answered ${res.status}`);
    return data;
  }

  /* ------------------------------------------------------------------ run state */
  const S = { built: false, tab: "overview", runId: null, source: null, info: null, presets: {}, waiting: null, decided: null };
  let R = freshRun();
  function freshRun() {
    return { state: {}, messages: [], statuses: {}, plan: null, pass: 0, started: false, finished: false, t0: null, active: null, mode: "full", ver: 0 };
  }
  const ui = {};

  /* ================================================================== graph */
  const W = 920, H = 400, CX = 460, CY = 200, RX = 290, RY = 148, NW = 150, NH = 44;

  function wrapText(text, max, lines) {
    const words = String(text || "").replace(/\s+/g, " ").trim().split(" ");
    const out = []; let cur = "";
    for (const w of words) {
      if ((cur + " " + w).trim().length > max) { if (cur) out.push(cur); cur = w; if (out.length === lines) break; }
      else cur = (cur + " " + w).trim();
    }
    if (out.length < lines && cur) out.push(cur);
    if (out.length === lines && words.join(" ").length > out.join(" ").length) out[lines - 1] = out[lines - 1].replace(/.{0,3}$/, "...");
    return out.slice(0, lines);
  }

  function createGraph(root, onSelect) {
    const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, class: "ag-graph", role: "img", "aria-label": "Agent graph" });
    const defs = s("defs", {},
      s("radialGradient", { id: "ag-glow", cx: "50%", cy: "50%", r: "50%" },
        s("stop", { offset: "0%", "stop-color": "#ff8f4d", "stop-opacity": ".10" }),
        s("stop", { offset: "100%", "stop-color": "#ff8f4d", "stop-opacity": "0" })),
      s("pattern", { id: "ag-dots", width: "22", height: "22", patternUnits: "userSpaceOnUse" }, s("circle", { cx: "1", cy: "1", r: "1", fill: "#1d232c" })));
    const gBack = s("g", {},
      s("rect", { x: 0, y: 0, width: W, height: H, fill: "url(#ag-dots)" }),
      s("ellipse", { cx: CX, cy: CY, rx: RX + 40, ry: RY + 34, fill: "url(#ag-glow)" }),
      s("ellipse", { class: "orbit", cx: CX, cy: CY, rx: RX, ry: RY }));
    const gEdges = s("g", {}), gFlow = s("g", { class: "flows" }), gNodes = s("g", {}), gBubble = s("g", { class: "bubble", opacity: "0" });
    const loopLabel = s("text", { class: "loop-label", "text-anchor": "middle" }, "");
    svg.append(defs, gBack, gEdges, gFlow, gNodes, loopLabel, gBubble);
    root.replaceChildren(svg);

    const pos = {}, nodeEls = {}, edgeEls = [];
    let loopEl = null, flowKey = "";
    const speech = {};

    pos.supervisor = { x: CX, y: CY, w: 168, h: 52, type: "hub" };
    AGENT_IDS.forEach((id, i) => {
      const a = (-90 + (360 / AGENT_IDS.length) * i) * Math.PI / 180;
      pos[id] = { x: CX + RX * Math.cos(a), y: CY + RY * Math.sin(a), w: NW, h: NH, type: "agent", angle: a };
    });
    pos.reporter = { x: 846, y: 118, w: 128, h: NH, type: "agent" };
    pos.__start__ = { x: 44, y: CY, w: 66, h: 26, type: "terminal" };
    pos.__end__ = { x: 860, y: 300, w: 66, h: 26, type: "terminal" };

    const edges = [["__start__", "supervisor", "normal"]];
    AGENT_IDS.forEach((id) => { if (id !== "skeptic") edges.push(["supervisor", id, "conditional"]); });
    edges.push(["evidence_ranker", "skeptic", "loop"], ["skeptic", "supervisor", "conditional"],
      ["supervisor", "reporter", "conditional"], ["reporter", "__end__", "normal"]);

    for (const [a, b, kind] of edges) {
      const A = pos[a], B = pos[b];
      let d;
      if (kind === "loop") {
        const mx = (A.x + B.x) / 2, my = (A.y + B.y) / 2;
        const dx = mx - CX, dy = my - CY, dd = Math.hypot(dx, dy) || 1;
        d = `M${A.x},${A.y} Q${mx + (dx / dd) * 80},${my + (dy / dd) * 80} ${B.x},${B.y}`;
        loopLabel.setAttribute("x", String(Math.min(W - 90, mx + (dx / dd) * 120)));
        loopLabel.setAttribute("y", String(Math.min(H - 8, my + (dy / dd) * 92)));
      } else d = `M${A.x},${A.y} L${B.x},${B.y}`;
      const el = s("path", { d, class: `edge ${kind}` });
      if (kind === "loop") loopEl = el;
      gEdges.append(el);
      edgeEls.push({ a, b, el, kind, d });
    }

    for (const [id, P] of Object.entries(pos)) {
      const term = P.type === "terminal";
      const m = meta(id), col = colorOf(id);
      const ir = P.type === "hub" ? 15 : 13, icx = ir + 9, icy = P.h / 2;
      const kids = [s("title", {}, term ? "" : `${m.label}: ${m.role}`),
        s("rect", { class: "halo", x: -5, y: -5, width: P.w + 10, height: P.h + 10, rx: 14 }),
        s("rect", { class: "box", width: P.w, height: P.h, rx: term ? P.h / 2 : 10 })];
      if (term) kids.push(s("text", { class: "lbl", x: P.w / 2, y: P.h / 2 + 4, "text-anchor": "middle" }, id === "__start__" ? "Start" : "End"));
      else kids.push(
        s("circle", { cx: icx, cy: icy, r: ir, fill: col, "fill-opacity": ".14", stroke: col, "stroke-opacity": ".45" }),
        s("circle", { class: "ring", cx: icx, cy: icy, r: ir + 3.5, stroke: col }),
        s("g", { transform: `translate(${icx - ir * 0.62},${icy - ir * 0.62}) scale(${(ir * 1.24) / 24})`, fill: "none", stroke: col,
          "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round" }, s("path", { d: ICONS[id] })),
        s("text", { class: "lbl", x: icx + ir + 9, y: P.h / 2 - 2 }, m.short),
        s("text", { class: "sub", x: icx + ir + 9, y: P.h / 2 + 12 }, P.type === "hub" ? "routing" : "waiting"),
        s("g", { class: "tick", transform: `translate(${P.w - 15},${P.h / 2})` }, s("circle", { r: 7 }), s("path", { d: "M-3,0 L-1,2.5 L3.2,-2.4" })));
      const g = s("g", { class: `node ${P.type}`, "data-status": "idle", transform: `translate(${P.x - P.w / 2},${P.y - P.h / 2})`,
        tabindex: term ? null : "0", role: term ? null : "button", "aria-label": term ? null : m.label }, ...kids);
      if (!term) {
        g.addEventListener("click", () => onSelect(id));
        g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(id); } });
      }
      gNodes.append(g);
      nodeEls[id] = g;
    }

    function setFlows(active) {
      const key = `${active || ""}|${R.pass}`;
      if (key === flowKey) return;
      flowKey = key;
      gFlow.replaceChildren();
      if (!active) return;
      const col = colorOf(active);
      for (const e of edgeEls) {
        if (!(e.a === active || e.b === active)) continue;
        if (!(e.a === "supervisor" || e.b === "supervisor" || e.kind === "loop")) continue;
        if (e.kind === "loop" && active !== "skeptic" && R.pass < 2) continue;
        const toward = e.b === active;
        for (let i = 0; i < 3; i++) {
          const c = s("circle", { r: 3.2, class: "packet", fill: col });
          c.append(s("animateMotion", { dur: "1.4s", repeatCount: "indefinite", begin: `${(i * 1.4) / 3}s`, path: e.d,
            keyPoints: toward ? "0;1" : "1;0", keyTimes: "0;1", calcMode: "linear" }));
          gFlow.append(c);
        }
      }
    }

    function renderBubble(active) {
      const text = active && speech[active], P = active && pos[active];
      if (!text || !P) { gBubble.setAttribute("opacity", "0"); return; }
      const lines = wrapText(text, 42, 2);
      const bw = 262, bh = 16 + lines.length * 14;
      const below = P.y <= CY;
      const x = Math.max(8, Math.min(W - bw - 8, P.x - bw / 2));
      const y = below ? P.y + P.h / 2 + 12 : P.y - P.h / 2 - 12 - bh;
      const tx = Math.max(x + 14, Math.min(x + bw - 14, P.x));
      const tip = below ? `M${tx - 7},${y} L${tx},${y - 7} L${tx + 7},${y} Z` : `M${tx - 7},${y + bh} L${tx},${y + bh + 7} L${tx + 7},${y + bh} Z`;
      const col = colorOf(active);
      gBubble.replaceChildren(
        s("rect", { x, y, width: bw, height: bh, rx: 9, class: "bub", stroke: col }),
        s("path", { d: tip, class: "bub-tip", stroke: col }),
        ...lines.map((l, i) => s("text", { x: x + 11, y: y + 18 + i * 14, class: "bub-t" }, l)));
      gBubble.setAttribute("opacity", "1");
    }

    function render() {
      let active = null;
      for (const [id, g] of Object.entries(nodeEls)) {
        if (pos[id].type === "terminal") {
          const st = id === "__start__" ? (R.started ? "done" : "idle") : (R.finished ? "done" : "idle");
          g.setAttribute("data-status", st);
          continue;
        }
        const st = R.statuses[id] || "idle";
        g.setAttribute("data-status", st);
        const sub = q("text.sub", g);
        if (sub) sub.textContent = id === "supervisor" && st === "idle" ? "routing"
          : (id === "evidence_ranker" || id === "skeptic") && R.pass > 1 && st !== "idle" ? `${SUB[st]}, pass ${R.pass}` : SUB[st] || st;
        if (st === "active" || st === "interrupt") active = active && active !== "supervisor" ? active : id;
      }
      for (const e of edgeEls) {
        const on = active && (e.a === active || e.b === active) && (e.a === "supervisor" || e.b === "supervisor" || e.kind === "loop");
        e.el.classList.toggle("flow", !!on);
        if (on) e.el.style.setProperty("--flow", colorOf(active)); else e.el.style.removeProperty("--flow");
        const ok = (id) => R.statuses[id] === "done" || id === "supervisor" && R.started || id === "__start__" && R.started || id === "__end__" && R.finished;
        e.el.classList.toggle("done", !on && ok(e.a) && ok(e.b));
      }
      if (loopEl) loopEl.classList.toggle("hot", R.pass > 1);
      loopLabel.textContent = R.pass > 0 ? `Skeptic review: pass ${R.pass}` : "Skeptic review loop";
      loopLabel.classList.toggle("hot", R.pass > 1);
      setFlows(active);
      renderBubble(active);
    }
    render();
    return {
      render,
      say(id, text) { if (!id || !text) return; speech[id] = text; if (R.statuses[id] === "active" || R.statuses[id] === "interrupt") render(); },
      reset() { Object.keys(speech).forEach((k) => delete speech[k]); flowKey = ""; render(); },
    };
  }

  /* ================================================================== layout */
  function field(text, input, cls) { return h("label", { class: `ag-field${cls ? " " + cls : ""}` }, h("span", {}, text), input); }

  function buildMission() {
    ui.form = h("form", { id: "ag-form", "aria-label": "Agent run", onsubmit: (e) => { e.preventDefault(); run(false); } });
    ui.preset = h("select", { name: "preset", onchange: presetNote });
    ui.presetNote = h("p", { class: "ag-note" });
    ui.mode = h("select", { name: "mode", onchange: () => { ui.custom.hidden = ui.mode.value !== "custom"; } },
      MODES.map(([v, t]) => h("option", { value: v }, t)));
    ui.custom = h("fieldset", { class: "ag-custom", hidden: true }, h("legend", {}, "Agents to run"),
      AGENTS.map((a) => h("label", { class: "ag-check" }, h("input", { type: "checkbox", value: a.id, checked: true }),
        h("i", { style: { background: colorOf(a.id) } }), a.label)));
    ui.run = h("button", { type: "submit", class: "ag-btn primary" }, "Run agents");
    ui.stop = h("button", { type: "button", class: "ag-btn danger", disabled: true, onclick: stop }, "Stop");
    ui.test = h("button", { type: "button", class: "ag-btn", onclick: testRun,
      title: "Fill the form with a sample lunar scenario (PMMA, cotton, 10 cm/s) and run every agent in shadow mode" }, "Test run (sample scenario)");
    ui.llm = h("span", { class: "ag-llm", title: "Language model used by the agents" }, "checking");
    ui.progress = h("div", { class: "ag-progress" }, h("i"));
    ui.runStatus = h("div", { class: "ag-runstatus", role: "status" }, "Idle. Pick a preset and press Run agents.");
    ui.route = h("ol", { class: "ag-route" });

    ui.form.append(
      h("h2", { class: "ag-h" }, "Mission ", label("HYPOTHETICAL")),
      field("Environment preset", ui.preset), ui.presetNote,
      h("div", { class: "ag-row2" },
        field("O2 %", h("input", { name: "o2_percent", type: "number", step: "0.1", min: "0", max: "100", placeholder: "preset" })),
        field("Gravity g", h("input", { name: "gravity_g", type: "number", step: "0.001", min: "0", placeholder: "preset" }))),
      h("div", { class: "ag-row2 ag-row-p" },
        field("Pressure", h("span", { class: "ag-joined" },
          h("input", { name: "pressure", type: "number", step: "0.1", min: "0", placeholder: "preset" }),
          h("select", { name: "pressure_unit", "aria-label": "Pressure unit" }, h("option", {}, "psi"), h("option", {}, "kPa")))),
        field("Flow cm/s", h("input", { name: "flow_speed", type: "number", step: "0.1", min: "0", placeholder: "not set" }))),
      field("Materials (comma separated)", h("input", { name: "materials", type: "text", value: "PMMA, cotton" })),
      h("div", { class: "ag-row2" },
        field("Pillar", h("select", { name: "pillar" }, h("option", { value: "" }, "any"), ["prevention", "detection", "suppression"].map((p) => h("option", {}, p)))),
        field("Recommendations", h("select", { name: "pilot_mode" }, h("option", { value: "approve" }, "Ask me first"), h("option", { value: "shadow" }, "Shadow: list only")))),
      field("What to run", ui.mode), ui.custom,
      field("Goal (optional)", h("textarea", { name: "goal", rows: 3, placeholder: "e.g. what is tested for a lunar habitat?" })),
      h("div", { class: "ag-btnrow" }, ui.run, ui.stop), ui.test,
      h("div", { class: "ag-llmrow" }, h("span", { class: "muted" }, "LLM"), ui.llm),
      ui.progress, ui.runStatus);
    return h("aside", { id: "ag-mission", "aria-label": "Mission" }, ui.form, h("h2", { class: "ag-h" }, "Route"), ui.route);
  }

  function buildCenter() {
    ui.stats = h("div", { class: "ag-stats", role: "status", "aria-live": "off" });
    ui.graphWrap = h("div", { id: "ag-graph-wrap" });
    ui.banner = h("div", { class: "ag-banner", hidden: true });
    ui.tabs = h("div", { id: "ag-tabs", role: "tablist", "aria-label": "Results" });
    ui.panel = h("div", { id: "ag-panel", role: "tabpanel", tabindex: "0" });
    ui.tabBtns = {};
    const tabs = [["overview", "Briefing"], ...AGENTS.map((a) => [a.id, a.tab]), ["trace", "Trace"]];
    for (const [id, text] of tabs) {
      const b = h("button", { type: "button", role: "tab", "data-id": id, "aria-selected": String(id === S.tab), tabindex: id === S.tab ? "0" : "-1", onclick: () => selectTab(id) },
        AGENT_IDS.includes(id) ? h("span", { class: "ag-tabico", style: { color: colorOf(id) } }, icon(id, 13)) : null, text);
      ui.tabBtns[id] = b;
      ui.tabs.append(b);
    }
    ui.tabs.addEventListener("keydown", (e) => {
      const ids = Object.keys(ui.tabBtns), i = ids.indexOf(S.tab);
      const j = e.key === "ArrowRight" ? (i + 1) % ids.length : e.key === "ArrowLeft" ? (i - 1 + ids.length) % ids.length : -1;
      if (j < 0) return;
      e.preventDefault(); selectTab(ids[j]); ui.tabBtns[ids[j]].focus();
    });
    ui.maxBtn = h("button", { type: "button", class: "ag-maxbtn", title: "Maximise (F)", "aria-label": "Maximise (F)", onclick: () => setMax(!isMax()) });
    ui.maxBtn.innerHTML = maxIcon(false);
    return h("section", { id: "ag-center" }, ui.stats, ui.graphWrap, ui.banner, ui.tabs, ui.panel, ui.maxBtn);
  }

  function buildRight() {
    ui.approval = h("div", { id: "ag-approval" });
    ui.feedCount = h("span", { class: "muted" }, "");
    ui.feed = h("div", { id: "ag-feed", "aria-live": "off" });
    return h("aside", { id: "ag-right", "aria-label": "Activity" }, ui.approval, h("h2", { class: "ag-h" }, "Live activity ", ui.feedCount), ui.feed);
  }

  const maxIcon = (out) => `<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="${out ? "M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" : "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"}" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
  const isMax = () => ui.layout.classList.contains("ag-max");
  function setMax(on) {
    ui.layout.classList.toggle("ag-max", on);
    ui.maxBtn.innerHTML = maxIcon(on);
    ui.maxBtn.title = on ? "Exit full screen (F)" : "Maximise (F)";
    if (on && !document.fullscreenElement && ui.layout.requestFullscreen) ui.layout.requestFullscreen().catch(() => {});
    if (!on && document.fullscreenElement) document.exitFullscreen();
  }

  function build(view) {
    ui.layout = h("div", { id: "ag-layout" }, buildMission(), buildCenter(), buildRight());
    view.replaceChildren(ui.layout);
    ui.graph = createGraph(ui.graphWrap, (id) => selectTab(id === "supervisor" ? "trace" : id === "reporter" ? "overview" : id));
    document.addEventListener("fullscreenchange", () => { if (!document.fullscreenElement && isMax()) setMax(false); });
    addEventListener("keydown", (e) => {
      if (view.hidden) return;
      if (e.key === "Escape" && isMax()) setMax(false);
      else if ((e.key === "f" || e.key === "F") && !e.ctrlKey && !e.metaKey && !e.altKey
        && !/^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName) && !e.target.isContentEditable) setMax(!isMax());
    });
    S.built = true;
    sysLine("Eight agents over the same evidence engines as the rest of PYRA. The Skeptic sends every draft back until its labels are honest, "
      + "and a person approves the recommendations. Agents never call a material safe or unsafe and do not predict fires.");
    loadInfo();
    renderAll();
  }

  async function loadInfo() {
    try {
      const [info, opts] = await Promise.all([call("/api/agents"), call("/api/builder/options")]);
      S.info = info;
      ui.llm.textContent = info.live ? info.llm : "scripted (no model)";
      ui.llm.dataset.state = info.live ? "live" : "off";
      ui.llm.title = info.live ? "Every sentence the model writes is checked against PYRA's rules; numbers come from code."
        : "No model connected: agents use scripted wording. Numbers always come from code.";
      ui.preset.replaceChildren(...opts.presets.map((p) => h("option", { value: p.id }, p.name)));
      ui.preset.value = opts.presets.some((p) => p.id === "lunar_surface") ? "lunar_surface" : opts.presets[0].id;
      S.presets = Object.fromEntries(opts.presets.map((p) => [p.id, p]));
      presetNote();
    } catch (err) {
      ui.llm.textContent = "unavailable";
      sysLine(`Agents not available: ${err.message}`, "bad");
    }
  }

  function presetNote() {
    const p = S.presets[ui.preset.value];
    if (!p) return;
    const parts = [p.gravity_g !== null ? `${p.gravity_g} g` : null, p.o2_percent !== null ? `${p.o2_percent} % O2` : null,
      p.pressure !== null ? `${p.pressure} ${p.pressure_unit}` : null].filter(Boolean);
    ui.presetNote.textContent = (parts.length ? parts.join(", ") + ". " : "No preset values. ")
      + (p.verified_by ? `Verified by ${p.verified_by}.` : "Preset source not yet verified.") + " Typed values win.";
  }

  /* ================================================================== run control */
  function body() {
    const f = ui.form.elements;
    const v = (n) => String(f[n].value || "").trim();
    const num = (n) => (v(n) === "" ? null : Number(v(n)));
    const scenario = { preset: v("preset"), o2_percent: num("o2_percent"), pressure: num("pressure"),
      pressure_unit: v("pressure_unit"), gravity_g: num("gravity_g"), flow_speed: num("flow_speed"), flow_unit: "cm/s",
      materials: v("materials").split(",").map((m) => m.trim()).filter(Boolean), pillar: v("pillar") || null,
      pilot_mode: v("pilot_mode") };
    const out = { goal: v("goal"), mode: v("mode"), scenario };
    if (out.mode === "custom") out.agents = [...ui.custom.querySelectorAll("input:checked")].map((i) => i.value);
    return out;
  }

  async function run(isTest) {
    if (S.source) S.source.close();
    R = freshRun();
    S.waiting = null; S.decided = null; S.runId = null;
    ui.approval.replaceChildren();
    ui.feed.replaceChildren();
    ui.graph.reset();
    const req = body();
    R.mode = req.mode;
    if (isTest === "demo") req.pace = DEMO_PACE_S;
    busy(true, isTest === "demo" ? "Starting the demo run..." : isTest ? "Starting the test run..." : "Starting...");
    sysLine(isTest === "demo" ? "Demo run: Mars transit scenario, every agent, slowed down so you can follow the graph. The Safety Officer will ask you to approve."
      : isTest ? "Test run: sample lunar scenario, every agent, shadow mode (no approval pause)." : "Run requested.");
    renderAll();
    try {
      const { run_id } = await call("/api/agents/run", req);
      S.runId = run_id;
      const es = new EventSource(`/api/agents/stream/${run_id}`);
      S.source = es;
      es.onmessage = (e) => { const ev = JSON.parse(e.data); onEvent(ev); if (ev.type === "done" || ev.type === "error") es.close(); };
      es.onerror = () => { if (es.readyState === EventSource.CLOSED && !R.finished) busy(false, "Disconnected from the run."); };
    } catch (err) {
      busy(false, "Could not start.");
      sysLine(err.message, "bad");
    }
  }

  function fill(values) {
    const f = ui.form.elements;
    Object.entries(values).forEach(([name, value]) => {
      const el = f[name];
      if (!el) return;
      if (name === "preset" && !Array.from(el.options).some((o) => o.value === value)) return;
      el.value = value;
    });
    ui.custom.hidden = true;
    presetNote();
  }

  async function demoRun() {
    for (let i = 0; i < 50 && !ui.preset.options.length; i++) await new Promise((r) => setTimeout(r, 100));  // presets loading
    if (!ui.preset.options.length) { sysLine("The demo could not start: presets did not load.", "bad"); return; }
    if (S.source && !R.finished && R.started) await stop();
    fill(DEMO_RUN);
    selectTab("overview");
    run("demo");
  }

  function testRun() {
    const f = ui.form.elements;
    if (!ui.preset.options.length) return;          // presets not loaded yet
    Object.entries(TEST_RUN).forEach(([name, value]) => {
      const el = f[name];
      if (!el) return;
      if (name === "preset" && !Array.from(el.options).some((o) => o.value === value)) return;
      el.value = value;
    });
    ui.custom.hidden = true;
    presetNote();
    run(true);
  }

  async function stop() {
    if (!S.runId) return;
    try { await call(`/api/agents/stop/${S.runId}`, {}); } catch (err) { sysLine(err.message, "bad"); }
  }

  function busy(on, status) {
    ui.run.disabled = on; ui.test.disabled = on; ui.stop.disabled = !on;
    if (status) ui.runStatus.textContent = status;
  }

  function onEvent(ev) {
    const a = ev.agent;
    if (ev.type === "run_start") {
      R.started = true; R.t0 = Date.now();
      busy(true, `Running (${ev.mode}).`);
      sysLine(`Run ${ev.run_id} started with ${ev.llm || "scripted wording"}.`, "ok");
    } else if (ev.type === "node_start") {
      for (const [id, st] of Object.entries(R.statuses)) if (st === "active") R.statuses[id] = "done";
      R.statuses[a] = "active"; R.active = a;
      if (a === "evidence_ranker") R.pass += 1;
      if (AGENT_IDS.includes(a) && S.tab !== a && S.tab !== "trace" && !askFocused()) selectTab(a, true);
    } else if (ev.type === "message") {
      const m = ev.data || {};
      R.messages.push(m);
      feedMsg(m);
      if (["thought", "llm", "result", "warning", "handoff"].includes(m.kind)) ui.graph.say(m.agent, m.text);
    } else if (ev.type === "node_end") {
      Object.assign(R.state, ev.update || {});
      R.statuses[a] = "done";
      if (a === "supervisor" && !R.plan && ev.update) {
        R.plan = [ev.update.next, ...(ev.update.route || [])].filter((x) => x && x !== "reporter");
        if (R.plan.includes("evidence_ranker") && !R.plan.includes("skeptic")) R.plan.splice(R.plan.indexOf("evidence_ranker") + 1, 0, "skeptic");
        AGENT_IDS.forEach((id) => { if (!R.plan.includes(id)) R.statuses[id] = "skipped"; });
      }
      R.ver++;
    } else if (ev.type === "interrupt") {
      S.waiting = ev.data; S.decided = null;
      R.statuses[a] = "interrupt";
      busy(true, "Waiting for your approval.");
      showApproval();
      if (!askFocused()) selectTab("safety_officer", true);
    } else if (ev.type === "resumed") {
      S.decided = ev.data; S.waiting = null;
      R.statuses[a] = "active";
      busy(true, "Running.");
      showApproval();
    } else if (ev.type === "done") {
      Object.assign(R.state, ev.state || {});
      for (const [id, st] of Object.entries(R.statuses)) if (st === "active") R.statuses[id] = "done";
      R.finished = true; R.active = null; R.ver++;
      busy(false, "Done. The briefing is ready.");
      sysLine("Run finished. Briefing written.", "ok");
      if (Array.isArray(ev.llm_rejected) && ev.llm_rejected.length)
        sysLine(`${ev.llm_rejected.length} model sentence(s) broke PYRA's rules and were replaced with scripted wording.`, "warn");
      selectTab("overview", true);
    } else if (ev.type === "error") {
      for (const [id, st] of Object.entries(R.statuses)) if (st === "active" || st === "interrupt") R.statuses[id] = "error";
      R.active = null; S.waiting = null;
      ui.approval.replaceChildren();
      busy(false, "Stopped.");
      sysLine(ev.text || "The run stopped.", "bad");
    }
    renderAll();
  }
  const askFocused = () => document.activeElement && document.activeElement.closest && document.activeElement.closest(".ag-ask");

  /* ================================================================== approval */
  function showApproval() {
    const box = ui.approval;
    if (S.decided) {
      const d = S.decided;
      box.replaceChildren(h("div", { class: "ag-appr done" },
        h("div", { class: "ag-appr-head" }, avatar("safety_officer", 24), h("b", {}, "Decision sent"), chip(d.decision === "approve" ? "approved" : "rejected", d.decision === "approve" ? "ok" : "bad")),
        h("div", { class: "ag-appr-note" }, d.decision === "approve" ? `${(d.ids || []).length || "All"} recommendation(s) approved.` : (d.reason ? `Rejected: ${d.reason}.` : "All recommendations rejected."))));
      return;
    }
    if (!S.waiting) { box.replaceChildren(); return; }
    const recs = S.waiting.actions || [];
    const send = async (decision) => {
      const ids = decision === "approve" ? [...box.querySelectorAll("input:checked")].map((i) => i.value) : [];
      if (decision === "approve" && !ids.length) decision = "reject";
      box.querySelectorAll("button").forEach((b) => { b.disabled = true; });
      try { await call(`/api/agents/resume/${S.runId}`, { decision, ids }); } catch (err) { sysLine(err.message, "bad"); }
    };
    box.replaceChildren(h("div", { class: "ag-appr", role: "group", "aria-label": "Approve recommendations" },
      h("div", { class: "ag-appr-head" }, avatar("safety_officer", 24), h("b", {}, "Safety Officer needs your approval")),
      h("div", { class: "ag-appr-note" }, S.waiting.question || "Approve these recommendations for the briefing?"),
      h("div", { class: "ag-appr-list" }, recs.map((r) => h("label", { class: "ag-appr-item" },
        h("input", { type: "checkbox", value: r.id, checked: true }),
        h("span", {}, h("span", { class: "ag-appr-title" }, chip(r.priority, r.priority === "P1" ? "bad" : r.priority === "P2" ? "warn" : "info"), " ", h("b", {}, r.title), " ", label(r.label)),
          h("span", { class: "ag-appr-text" }, r.text))))),
      h("div", { class: "ag-btnrow" },
        h("button", { type: "button", class: "ag-btn primary", onclick: () => send("approve") }, "Approve selected"),
        h("button", { type: "button", class: "ag-btn", onclick: () => send("reject") }, "Reject all"))));
  }

  /* ================================================================== feed */
  let feedStick = true;
  function feedAdd(node) {
    if (!ui.feed.dataset.wired) { ui.feed.dataset.wired = "1"; ui.feed.addEventListener("scroll", () => { feedStick = ui.feed.scrollHeight - ui.feed.scrollTop - ui.feed.clientHeight < 80; }); }
    ui.feed.append(node);
    while (ui.feed.childElementCount > 500) ui.feed.firstElementChild.remove();
    ui.feedCount.textContent = R.messages.length ? `(${R.messages.length})` : "";
    if (feedStick) ui.feed.scrollTop = ui.feed.scrollHeight;
  }
  function feedMsg(m) {
    const kind = String(m.kind || "note");
    const prev = ui.feed.lastElementChild;
    const cont = prev && prev.dataset.agent === String(m.agent) && !prev.classList.contains("sys");
    feedAdd(h("div", { class: `ag-fl k-${kind}${cont ? " cont" : ""}`, "data-agent": String(m.agent), style: { "--c": colorOf(m.agent) } },
      cont ? h("span", { class: "ag-av-gap" }) : avatar(m.agent, 26),
      h("div", { class: "ag-fl-body" },
        cont ? null : h("div", { class: "ag-fl-head" }, h("b", { style: { color: colorOf(m.agent) } }, meta(m.agent).label), h("span", { class: "ag-time" }, clock(m.t))),
        h("div", { class: "ag-fl-text" }, kind !== "thought" && kind !== "llm" ? h("span", { class: `ag-kind k-${kind}` }, kind) : null, m.text))));
  }
  function sysLine(text, tone) { feedAdd(h("div", { class: `ag-fl sys${tone ? " " + tone : ""}` }, text)); }

  /* ================================================================== stats + route */
  function counts() {
    const plan = R.plan || [];
    const done = plan.filter((id) => R.statuses[id] === "done").length + (R.statuses.reporter === "done" ? 1 : 0);
    const total = plan.length ? plan.length + 1 : 0;
    return { done, total };
  }

  function renderStats() {
    const { done, total } = counts();
    const act = R.active && R.active !== "supervisor" ? R.active : R.active;
    const m = act ? meta(act) : null;
    const claims = (R.state.ranking && R.state.ranking.claims) || [];
    const measured = claims.filter((c) => c.label === "MEASURED").length;
    const axes = (R.state.gaps && R.state.gaps.axes) || [];
    const open = axes.filter((x) => x.class && x.class !== "DIRECTLY_TESTED").length;
    const recs = (R.state.actions && R.state.actions.recommendations) || [];
    const approved = recs.filter((r) => r.status === "approved").length;
    const secs = R.t0 ? Math.round((Date.now() - R.t0) / 1000) : null;
    const stat = (v, l, tone) => h("div", { class: `ag-stat${tone ? " " + tone : ""}` }, h("b", {}, v), h("span", {}, l));
    const now = h("div", { class: "ag-stat-now" },
      m ? avatar(act, 30) : h("span", { class: "ag-av idle" }),
      h("div", {}, h("b", {}, m ? m.label : R.finished ? "Run complete" : R.started ? "Starting" : "Team idle"),
        h("div", { class: "muted" }, m ? (R.statuses[act] === "interrupt" ? "waiting for your approval" : "working") : R.finished ? "briefing ready" : "press Run agents")));
    ui.stats.replaceChildren(now,
      h("div", { class: "ag-stat-bar" }, h("i", { style: { width: `${total ? (100 * done) / total : 0}%` } })),
      stat(total ? `${done}/${total}` : "-", "agents done", R.finished ? "ok" : ""),
      stat(R.pass ? String(R.pass) : "-", "review pass", R.pass > 1 ? "warn" : ""),
      stat(claims.length ? `${measured}/${claims.length}` : "-", "claims MEASURED"),
      stat(axes.length ? String(open) : "-", "open gaps", open ? "warn" : ""),
      stat(recs.length ? `${approved}/${recs.length}` : "-", "actions approved"),
      stat(secs !== null && !R.finished ? `${secs}s` : secs !== null ? "done" : "-", "elapsed"));
    q("i", ui.progress).style.width = `${total ? (100 * done) / total : 0}%`;
  }

  function renderRoute() {
    const plan = R.plan || (R.started ? [] : (S.info && S.info.modes && S.info.modes[R.mode]) || []);
    const ids = R.plan ? [...plan, "reporter"] : plan.length ? [...plan, "reporter"] : [...AGENT_IDS, "reporter"];
    ui.route.replaceChildren(...ids.map((id, i) => {
      const st = R.statuses[id] || (R.plan ? "idle" : "idle");
      const m = meta(id);
      const tone = { active: "accent", done: "ok", interrupt: "warn", error: "bad", skipped: "muted" }[st] || "muted";
      return h("li", { "data-status": st, style: { "--c": colorOf(id) } },
        h("span", { class: "ag-step" }, st === "done" ? "✓" : String(i + 1)),
        h("button", { type: "button", class: "ag-link ag-roster", onclick: () => selectTab(id === "reporter" ? "overview" : id) },
          avatar(id, 24), h("span", { class: "ag-roster-t" }, h("b", {}, m.label), h("span", { class: "muted" }, id === "skeptic" && R.pass ? `review pass ${R.pass}` : SUB[st] || st))),
        st !== "idle" ? chip(SUB[st] || st, tone) : null);
    }));
    if (!R.started) ui.route.prepend(h("li", { class: "ag-route-note" }, h("span", { class: "muted" }, "The supervisor plans the route when the run starts.")));
  }

  function renderBanner() {
    if (S.waiting) { ui.banner.className = "ag-banner warn"; ui.banner.textContent = "The Safety Officer is waiting for you: approve or reject the recommendations on the right."; ui.banner.hidden = false; }
    else if (R.finished && R.state.corpus && R.state.corpus.not_real) { ui.banner.className = "ag-banner info"; ui.banner.textContent = "This corpus holds sheets marked NOT REAL DATA: their numbers are not NASA results."; ui.banner.hidden = false; }
    else ui.banner.hidden = true;
  }

  function renderTabs() {
    for (const [id, b] of Object.entries(ui.tabBtns)) {
      b.setAttribute("aria-selected", String(id === S.tab));
      b.tabIndex = id === S.tab ? 0 : -1;
      const st = id === "overview" ? (R.statuses.reporter || "idle") : R.statuses[id];
      if (st) b.dataset.status = st; else delete b.dataset.status;
    }
  }

  function renderAll() {
    if (!S.built) return;
    ui.graph.render();
    renderStats();
    renderRoute();
    renderBanner();
    renderTabs();
    renderPanel();
  }
  setInterval(() => { if (S.built && R.started && !R.finished) renderStats(); }, 1000);

  /* ================================================================== panel */
  const askBoxes = {};
  const traceUi = { agent: "", kind: "", q: "" };
  let panelCache = { tab: null, ver: -1, slot: null };

  function selectTab(id, auto) {
    if (!ui.tabBtns[id]) id = "overview";
    if (auto && id === S.tab) return;
    S.tab = id;
    panelCache = { tab: null, ver: -1, slot: null };
    renderTabs();
    renderPanel();
    ui.panel.scrollTop = 0;
  }

  function renderPanel() {
    const ver = S.tab === "trace" ? R.messages.length : `${R.ver}|${R.statuses[S.tab] || ""}|${R.pass}`;
    if (panelCache.tab === S.tab && panelCache.ver === ver) return;
    let content;
    try {
      content = S.tab === "overview" ? viewOverview() : S.tab === "trace" ? viewTrace() : viewAgent(S.tab);
    } catch (err) {
      console.error("agents: panel render failed", err);
      content = h("div", { class: "ag-empty" }, "This view could not be drawn from the data received so far.");
    }
    if (panelCache.tab !== S.tab) {
      ui.panel.replaceChildren();
      if (S.tab === "trace") ui.panel.append(traceFilters());
      panelCache.slot = h("div", { class: "ag-slot" });
      ui.panel.append(panelCache.slot);
      if (AGENT_IDS.includes(S.tab)) ui.panel.append(askBox(S.tab));
    }
    panelCache.slot.replaceChildren(...[content].flat(3).filter(Boolean));
    panelCache.tab = S.tab; panelCache.ver = ver;
  }

  const card = (title, ...kids) => h("section", { class: "ag-card" }, title ? h("h3", {}, title) : null, ...kids);
  const tile = (v, l, tone) => h("div", { class: `ag-tile${tone ? " " + tone : ""}` }, h("b", {}, fmt(v)), h("span", {}, l));
  function table(head, rows, numCols) {
    return h("div", { class: "ag-table-wrap" }, h("table", { class: "ag-table" },
      h("thead", {}, h("tr", {}, head.map((t, i) => h("th", { class: (numCols || []).includes(i) ? "num" : null }, t)))),
      h("tbody", {}, rows.map((r) => h("tr", {}, r.map((c, i) => h("td", { class: (numCols || []).includes(i) ? "num mono" : null }, c)))))));
  }
  function cite(c) {
    const text = [c.acronym, c.run_id].filter(Boolean).join(" ") || c.title || "source";
    return c.url ? h("a", { href: c.url, target: "_blank", rel: "noopener" }, text) : h("span", {}, text);
  }

  function agentHead(id) {
    const m = meta(id), st = R.statuses[id];
    const tone = { active: "accent", done: "ok", interrupt: "warn", error: "bad" }[st] || "muted";
    return h("div", { class: "ag-agent-head", style: { borderLeftColor: colorOf(id) } },
      h("div", { class: "ag-agent-id" }, avatar(id, 36), h("div", {}, h("h2", {}, m.label), h("div", { class: "muted" }, m.role))),
      chip(st ? SUB[st] || st : R.started ? "waiting" : "not run", tone));
  }

  function lastThought(id) {
    const m = R.messages.filter((x) => x.agent === id && (x.kind === "llm" || x.kind === "thought")).pop();
    return m ? m.text : "";
  }

  // Scalars as a key/value list, arrays of objects as small tables.
  function autoView(slice, skip) {
    const out = [];
    const scal = Object.entries(slice).filter(([k, v]) => !(skip || []).includes(k) && (v === null || typeof v !== "object"));
    if (scal.length) out.push(card("Values", h("dl", { class: "ag-kv" }, scal.map(([k, v]) => [h("dt", {}, human(k)), h("dd", {}, fmt(v))]))));
    for (const [k, v] of Object.entries(slice)) {
      if ((skip || []).includes(k)) continue;
      if (Array.isArray(v) && v.length && isObj(v[0])) {
        const cols = Object.keys(v[0]).filter((c) => v.some((r) => r[c] === null || typeof r[c] !== "object")).slice(0, 6);
        out.push(card(human(k), table(cols.map(human), v.slice(0, 30).map((r) => cols.map((c) => fmt(r[c]))))));
      } else if (isObj(v)) {
        const sc = Object.entries(v).filter(([, x]) => x === null || typeof x !== "object");
        if (sc.length) out.push(card(human(k), h("dl", { class: "ag-kv" }, sc.map(([a, b]) => [h("dt", {}, human(a)), h("dd", {}, fmt(b))]))));
      } else if (Array.isArray(v) && v.length) {
        out.push(card(human(k), h("div", { class: "ag-chips" }, v.slice(0, 40).map((x) => chip(fmt(x))))));
      }
    }
    return out;
  }

  function viewAgent(id) {
    const m = meta(id), slice = R.state[m.key];
    const out = [agentHead(id)];
    const said = lastThought(id);
    if (said) out.push(h("p", { class: "ag-summary" }, said));
    if (slice === undefined) {
      out.push(h("div", { class: "ag-empty" }, R.statuses[id] === "skipped" ? "Not in this run's route." : R.started ? "This agent has not reported yet." : "Run the team to see this agent's work."));
      return out;
    }
    const V = VIEWS[id];
    out.push(...[V ? V(slice) : autoView(slice)].flat(3));
    return out;
  }

  const VIEWS = {
    librarian(c) {
      const g = c.runs_by_gravity || {};
      return [h("div", { class: "ag-tiles" }, tile(c.investigations, "investigations"), tile(c.runs, "test runs"),
        tile(c.measured_findings, "MEASURED findings", "good"), tile(g.microgravity, "microgravity runs"), tile(g["normal gravity"], "normal-gravity runs"),
        tile(g.partial, "partial-gravity runs"), tile(c.not_real ? "not real" : "verified", "corpus", c.not_real ? "warn" : "good")),
      autoView(c, ["investigations", "runs", "measured_findings", "not_real", "runs_by_gravity"])];
    },
    mission(p) { return VIEWS.mission_profiler(p); },
    mission_profiler(p) {
      const vals = p.values || [];
      return [h("div", { class: "ag-verdict" }, h("b", {}, p.name || "Scenario"), label("HYPOTHETICAL"), p.gravity_regime ? chip(p.gravity_regime, "info") : null,
        p.o2_partial_kpa !== null && p.o2_partial_kpa !== undefined ? chip(`O2 partial ${p.o2_partial_kpa} kPa (DERIVED)`, "info") : null),
      vals.length ? card("Scenario values", table(Object.keys(vals[0]).slice(0, 5).map(human), vals.map((v) => Object.keys(vals[0]).slice(0, 5).map((k) => fmt(v[k]))))) : null,
      (p.materials || []).length ? card("Materials", h("div", { class: "ag-chips" }, p.materials.map((x) => chip(isObj(x) ? (x.name || x.id || JSON.stringify(x)) : x, "accent")))) : null,
      (p.unverified_sources || []).length ? h("div", { class: "ag-banner warn" }, "Preset source not yet verified by the team.") : null];
    },
    physicist(f) {
      if (f.state !== "EVALUATED") return [h("div", { class: "ag-empty" }, `Not evaluated: ${f.reason || "missing inputs"}.`)];
      return [h("div", { class: "ag-tiles" }, tile(f.buoyant_velocity_m_s, "buoyant flow m/s"), tile(f.earth_buoyant_velocity_m_s, "1 g buoyant flow m/s"),
        tile(f.normal_gravity_test_similarity || "not evaluated", "similarity to a 1 g test")),
      f.regime_text ? card("Flow regime ", h("p", { class: "ag-p" }, f.regime_text, " ", label("ILLUSTRATIVE"))) : null,
      autoView(f, ["state", "summary", "regime_text", "buoyant_velocity_m_s", "earth_buoyant_velocity_m_s", "normal_gravity_test_similarity"])];
    },
    evidence_ranker(r) {
      const claims = r.claims || [];
      const out = [h("div", { class: "ag-tiles" }, tile(r.pass, "draft pass"), tile(claims.length, "claims"),
        tile(claims.filter((c) => c.label === "MEASURED").length, "MEASURED", "good"), tile((r.ranked || []).length, "investigations ranked"))];
      if ((r.history || []).length) out.push(h("p", { class: "ag-more" }, r.history.map((x) => `pass ${x.pass}: ${x.measured} of ${x.claims} MEASURED`).join("  →  ")));
      out.push(card(`Claims ${r.strict ? "(after the Skeptic's review)" : "(first draft)"}`,
        table(["Claim", "Label", "Statement", "Cites"], claims.map((c) => [h("span", { class: "mono" }, c.id), label(c.label), c.text,
          (c.citations || []).length ? c.citations.map((x, i) => [i ? ", " : "", cite(x)]) : h("span", { class: "muted" }, "none")]))));
      if ((r.ranked || []).length) out.push(card("Closest investigations", table(["Investigation", "Score", "Class", "Unmatched"],
        r.ranked.map((e) => [e.acronym, h("span", {}, h("span", { class: "ag-meter" }, h("i", { style: { width: `${Math.max(0, Math.min(100, 100 * (+e.total || 0)))}%` } })), fmt(e.total)),
          e.evidence_class, (e.unmatched || []).join(", ") || "none"]))));
      return out;
    },
    skeptic(rev) {
      const issues = rev.issues || [];
      return [h("div", { class: "ag-verdict" }, chip(rev.approved ? "approved" : "sent back", rev.approved ? "ok" : "bad"), h("span", {}, `Pass ${rev.pass}`),
        h("span", { class: "muted" }, `${issues.length} issue(s)`)),
      issues.length ? card("Issues", h("ul", { class: "ag-issues" }, issues.map((i) => h("li", { class: i.severity === "block" ? "bad" : "warn" },
        h("span", { class: "mono" }, i.code), " ", i.text, h("div", { class: "muted" }, `Fix: ${i.fix}`))))) : h("div", { class: "ag-empty sm" }, "No issues. Every label is honest.")];
    },
    incident_analyst(c) {
      const L = ["oxidizer", "fuel", "ignition", "detection", "suppression", "escape"];
      return [h("p", { class: "ag-more" }, "Pattern match against past fires (INTERPRETATION), never a prediction. Summaries are not yet verified unless marked."),
        h("div", { class: "ag-sections" }, (c.cases || []).map((x) => h("section", { class: `ag-card ag-sec${x.id === c.closest ? " closest" : ""}` },
          h("h3", {}, `${x.name} (${x.year}) `, chip(`${x.shared_links} shared link(s)`, x.shared_links ? "warn" : "muted")),
          h("div", { class: "ag-chain" }, L.map((k) => h("div", { class: x.links && x.links.some((l) => String(l).toLowerCase().includes(k)) ? "hit" : null }, h("b", {}, k), x.chain ? x.chain[k] : ""))),
          h("p", { class: "ag-p" }, (x.links || []).length ? "In this scenario: " + x.links.join("; ") + "." : "No shared links."),
          h("p", { class: "ag-more" }, "Not evaluated: " + (x.not_evaluated || []).join("; ") + ". ",
            h("a", { href: x.source, target: "_blank", rel: "noopener" }, x.verified ? "source (verified)" : "source (not yet verified)")))))];
    },
    gap_hunter(g) {
      const n = g.next_experiment;
      return [g.combination && g.combination.summary ? h("p", { class: "ag-summary" }, g.combination.summary) : null,
        card("Axes", table(["Axis", "Class", "What PYRA found"], (g.axes || []).map((a) => [human(a.axis),
          a.class ? h("span", { class: `ag-gap gap-${a.class}` }, a.class.replace(/_/g, " ")) : h("span", { class: "muted" }, "not set"), a.summary || ""]))),
        n ? h("section", { class: "ag-card ag-proposal" }, h("h3", {}, "Proposed next experiment ", label("PROPOSAL")), h("p", { class: "ag-p" }, n.text)) : null,
        (g.opportunities || []).length ? card("Data opportunities", table(["Axis", "Gap class", "Score"], g.opportunities.map((o) => [human(o.axis), o.gap_class, fmt(o.score)]), [2])) : null];
    },
    safety_officer(a) {
      const recs = a.recommendations || [];
      return [h("div", { class: "ag-verdict" }, chip(a.pilot_mode === "approve" ? "a person reviewed these" : "shadow mode: not reviewed", a.pilot_mode === "approve" ? "ok" : "warn"),
        h("span", { class: "muted" }, `${(a.approved_ids || []).length} approved, ${(a.rejected_ids || []).length} rejected`)),
      h("div", { class: "ag-wos" }, recs.map((r) => h("div", { class: `ag-wo ${r.status === "approved" ? "ok" : r.status === "rejected" ? "bad" : "warn"}` },
        h("div", { class: "ag-wo-head" }, chip(r.priority, r.priority === "P1" ? "bad" : r.priority === "P2" ? "warn" : "info"), h("b", {}, r.title), label(r.label),
          h("span", { class: "ag-wo-due" }, chip(r.status, r.status === "approved" ? "ok" : r.status === "rejected" ? "bad" : "muted"))),
        h("div", {}, r.text),
        h("div", { class: "muted sm" }, "Evidence: " + ((r.evidence || []).join(", ") || "none")))))];
    },
  };

  function viewOverview() {
    const r = R.state.report;
    if (r) {
      const md = new Blob([r.markdown || ""], { type: "text/markdown" });
      return [h("p", { class: "ag-headline" }, r.headline),
        h("div", { class: "ag-tiles" }, Object.entries(r.kpis || {}).map(([k, v]) => tile(v, human(k)))),
        h("div", { class: "ag-sections" }, (r.sections || []).map((sec) => h("section", { class: "ag-card ag-sec", style: { borderLeftColor: colorOf(sec.agent) } },
          h("h3", {}, sec.agent ? avatar(sec.agent, 20) : null, sec.title, " ", label(sec.label)),
          h("ul", { class: "ag-bullets" }, (sec.bullets || []).filter(Boolean).map((b) => h("li", {}, b)))))),
        h("div", { class: "ag-btnrow" }, h("a", { class: "ag-btn", href: URL.createObjectURL(md), download: "pyra_agents_briefing.md" }, "Download briefing (markdown)"))];
    }
    const out = [h("p", { class: `ag-headline${R.started ? "" : " muted"}` }, R.started
      ? (R.state.mission ? `The team is working on ${R.state.mission.name}...` : "The team is working...")
      : "Eight agents check what is really known about fire in your scenario. The briefing appears here when they finish.")];
    out.push(h("div", { class: "ag-sections" }, AGENTS.map((a) => {
      const st = R.statuses[a.id];
      const said = lastThought(a.id);
      return h("section", { class: "ag-card ag-sec ag-mini", style: { borderLeftColor: colorOf(a.id) }, "data-status": st || "idle", tabindex: "0",
        onclick: () => selectTab(a.id), onkeydown: (e) => { if (e.key === "Enter") selectTab(a.id); } },
      h("h3", {}, avatar(a.id, 22), a.label, chip(st ? SUB[st] : "waiting", { active: "accent", done: "ok", interrupt: "warn", error: "bad" }[st] || "muted")),
      h("p", { class: "ag-p muted" }, said || a.role));
    })));
    return out;
  }

  function traceFilters() {
    const agentSel = h("select", { onchange: (e) => { traceUi.agent = e.target.value; panelCache.ver = -1; renderPanel(); } },
      h("option", { value: "" }, "All agents"), ["supervisor", ...AGENT_IDS, "reporter"].map((id) => h("option", { value: id, selected: traceUi.agent === id }, meta(id).label)));
    const kindSel = h("select", { onchange: (e) => { traceUi.kind = e.target.value; panelCache.ver = -1; renderPanel(); } },
      h("option", { value: "" }, "All kinds"), ["thought", "tool", "result", "handoff", "warning", "llm"].map((k) => h("option", { value: k, selected: traceUi.kind === k }, k)));
    let t;
    const input = h("input", { type: "search", placeholder: "Filter text", value: traceUi.q,
      oninput: (e) => { clearTimeout(t); t = setTimeout(() => { traceUi.q = e.target.value; panelCache.ver = -1; renderPanel(); }, 200); } });
    return h("div", { class: "ag-filters" }, agentSel, kindSel, input);
  }
  function viewTrace() {
    const needle = traceUi.q.trim().toLowerCase();
    const list = R.messages.filter((m) => (!traceUi.agent || m.agent === traceUi.agent) && (!traceUi.kind || m.kind === traceUi.kind)
      && (!needle || String(m.text || "").toLowerCase().includes(needle)));
    if (!list.length) return h("div", { class: "ag-empty" }, R.messages.length ? "No lines match the filter." : "No trace yet.");
    return [h("div", { class: "ag-more" }, `${list.length} of ${R.messages.length} lines`),
      h("div", { class: "ag-trace" }, list.slice(-800).map((m) => h("div", { class: "ag-line" },
        h("span", { class: "ag-time" }, clock(m.t)), h("span", { class: "ag-who", style: { color: colorOf(m.agent) } }, meta(m.agent).short),
        h("span", { class: `ag-kind k-${m.kind}` }, m.kind), h("span", { class: "ag-text" }, m.text,
          m.data && Object.keys(m.data).length ? h("details", { class: "ag-data" }, h("summary", {}, "data"), h("pre", {}, JSON.stringify(m.data, null, 2).slice(0, 4000))) : null))))];
  }

  function askBox(agent) {
    if (askBoxes[agent]) return askBoxes[agent];
    const log = h("div", { class: "ag-asklog" });
    const input = h("input", { type: "text", placeholder: `Ask the ${meta(agent).label} a question`, "aria-label": `Question for ${meta(agent).label}` });
    const btn = h("button", { class: "ag-btn sm", type: "submit" }, "Ask");
    const form = h("form", { class: "ag-askform", onsubmit: async (e) => {
      e.preventDefault();
      const question = input.value.trim();
      if (!question) return;
      input.value = ""; btn.disabled = true;
      const a = h("div", { class: "ag-a muted" }, "Thinking...");
      log.append(h("div", { class: "ag-q" }, question), a);
      try {
        const r = await call("/api/agents/ask", { agent, question, run_id: S.runId });
        a.replaceChildren(r.answer, " ", r.label ? label(r.label) : "");
      } catch (err) { a.textContent = err.message; }
      a.classList.remove("muted"); btn.disabled = false;
    } }, input, btn);
    askBoxes[agent] = h("section", { class: "ag-card ag-ask" }, h("h3", {}, "Ask this agent"), log, form);
    return askBoxes[agent];
  }

  window.pyraAgents = {
    show() {
      const view = document.getElementById("view-agents");
      if (view && !S.built) build(view);
    },
    demo() {
      this.show();
      if (S.built) demoRun();
    },
  };
})();
