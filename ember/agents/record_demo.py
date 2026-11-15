"""Re-record agents/data/demo_run.json (offline, lunar habitat, approve). Run from ember/:
    python -m agents.record_demo [mission]"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from langgraph.types import Command

from .ctx import OfflineLLM
from .graph import build_graph
from .server import jsonable, strip_state


def main(mission: str = "lunar") -> None:
    events: list[dict] = []
    t0 = time.time()

    def sink(e):
        events.append(jsonable({**e, "dt": round(time.time() - t0, 3)}))

    g = build_graph(OfflineLLM(), sink)
    cfg = {"configurable": {"thread_id": "demo"}}
    req = {"goal": "Full fire-safety assessment", "mode": "full",
           "scenario": {"mission": mission, "pilot_mode": "approve"}}
    events.append({"type": "run_start", "thread_id": "demo", "llm": "replay (recorded offline run)", **req})
    r = g.invoke({**req, "agents": [], "done": [], "risk_iterations": 0, "approvals": [], "messages": []}, cfg)
    if r.get("__interrupt__"):
        seen = {(e.get("type"), (e.get("data") or {}).get("text")) for e in events if e.get("agent") == "safety_officer"}
        n_before = len(events)
        events.append(jsonable({"type": "interrupt", "agent": "safety_officer", "data": r["__interrupt__"][0].value}))
        g.invoke(Command(resume={"decision": "approve", "ids": []},
                         update={"approvals": [{"decision": "approve", "ids": [], "agent": "safety_officer"}]}), cfg)
        # LangGraph re-runs the interrupted node on resume: drop the repeated start and messages.
        head, tail = events[:n_before + 1], events[n_before + 1:]
        tail = [e for e in tail if not (e.get("agent") == "safety_officer" and
                (e.get("type"), (e.get("data") or {}).get("text")) in seen)]
        events[:] = head + tail
    events.append({"type": "done", "state": strip_state(g.get_state(cfg).values)})
    for i, e in enumerate(events):
        e["seq"] = i
    out = Path(__file__).with_name("data") / "demo_run.json"
    out.write_text(json.dumps({"mission": mission, "events": events}, indent=1), encoding="utf-8")
    print(f"wrote {out} ({len(events)} events)")


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["lunar"]))
