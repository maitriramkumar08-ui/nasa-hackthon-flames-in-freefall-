"""Offline end-to-end tests. Run: python -m agents.tests.test_graph (from ember/)."""
from __future__ import annotations

from langgraph.types import Command

from agents.graph import build_graph
from agents.nodes.supervisor import normalise


def _run(mission, decision="approve", mode="full", pilot="approve", agents=None):
    g = build_graph()
    cfg = {"configurable": {"thread_id": f"{mission}-{decision}-{mode}"}}
    inp = {"goal": "", "mode": mode, "agents": agents or [], "done": [], "risk_iterations": 0, "messages": [],
           "scenario": {"mission": mission, "pilot_mode": pilot}}
    r = g.invoke(inp, cfg)
    if r.get("__interrupt__"):
        g.invoke(Command(resume={"decision": decision, "ids": []}), cfg)
    return g.get_state(cfg).values


def test_iss_passes_first_review():
    st = _run("iss")
    assert st["review"]["approved"] and st["risk_iterations"] == 1
    assert {"corpus", "mission", "physics", "risk", "incidents", "gaps", "actions", "report"} <= set(st)


def test_lunar_loops_and_relabels():
    st = _run("lunar")
    assert st["risk_iterations"] == 2 and st["review"]["approved"]
    assert all(i["confidence"] != "measured" for i in st["risk"]["items"])
    assert st["physics"]["regime"] == "buoyant"


def test_reject_marks_all_rejected():
    st = _run("mars_transit", decision="reject")
    assert st["actions"]["recommendations"] and all(r["status"] == "rejected" for r in st["actions"]["recommendations"])
    assert any(r["id"] == "R6" for r in st["actions"]["recommendations"])  # comm-delay playbook


def test_shadow_mode_no_interrupt():
    st = _run("gateway", pilot="shadow")
    assert all(r["status"] == "unreviewed" for r in st["actions"]["recommendations"])


def test_modes_and_custom():
    st = _run("iss", mode="gaps")
    assert "gaps" in st and "risk" not in st
    assert normalise(["skeptic"]) == ["librarian", "mission_profiler", "risk_ranker"]


def test_corpus_drops_non_combustion():
    st = _run("iss", mode="gaps")
    assert {d["id"] for d in st["corpus"]["dropped"]} == {"PSI-181", "PSI-108"}


def test_http_api():
    from fastapi.testclient import TestClient
    import time
    from agents.server import app
    c = TestClient(app)
    assert c.get("/api/health").json()["ok"]
    assert len(c.get("/api/graph").json()["nodes"]) == 12
    tid = c.post("/api/run", json={"mode": "full", "scenario": {"mission": "lunar", "pilot_mode": "approve"}}).json()["thread_id"]
    for _ in range(100):
        if c.get(f"/api/state/{tid}").json()["_meta"]["waiting"]:
            break
        time.sleep(0.05)
    assert c.post(f"/api/resume/{tid}", json={"decision": "approve", "ids": []}).json()["ok"]
    for _ in range(100):
        s = c.get(f"/api/state/{tid}").json()
        if s["_meta"]["finished"]:
            break
        time.sleep(0.05)
    assert s["report"]["headline"]
    assert "Lunar" in c.post("/api/ask", json={"agent": "mission_profiler", "thread_id": tid}).json()["answer"]


if __name__ == "__main__":
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print("PASS", name)
            except Exception as e:  # noqa: BLE001
                fails += 1
                print("FAIL", name, type(e).__name__, e)
    raise SystemExit(1 if fails else 0)
