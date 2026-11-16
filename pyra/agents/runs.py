"""Agent runs for the web server: one background thread per run, an event log the
page streams (Server-Sent Events), and the human-approval pause.

    run = runs.start(request, corpus)           # returns at once
    run.events_since(0, timeout=15)             # what the stream sends
    run.resume({"decision": "approve", "ids": ["R1"]})
"""

import json
import threading
import time
import uuid

from . import team
from .ctx import Cancelled, OfflineLLM
from .llm import get_llm

APPROVAL_TIMEOUT_S = 30 * 60
MAX_RUNS = 30


def jsonable(value):
    return json.loads(json.dumps(value, default=str))


class Run:
    def __init__(self, request, corpus, llm=None):
        self.id = uuid.uuid4().hex[:12]
        self.request = request
        self.corpus = corpus
        base = llm or get_llm()
        self.llm = base.fresh() if hasattr(base, "fresh") else base   # its own time budget
        self.events = []
        self.cond = threading.Condition()
        self.finished = False
        self.waiting = None          # the interrupt payload while a person has to decide
        self._decision = None
        self._decided = threading.Event()
        self._stop = threading.Event()
        self.state = {}
        self.created = time.time()

    # ---- events --------------------------------------------------------------
    def push(self, event):
        event = jsonable(event)
        with self.cond:
            event["seq"] = len(self.events)
            self.events.append(event)
            if event.get("type") in ("done", "error"):
                self.finished = True
            self.cond.notify_all()

    def events_since(self, index, timeout=15):
        """(new events, finished). Waits up to timeout seconds for something new."""
        with self.cond:
            if index >= len(self.events) and not self.finished:
                self.cond.wait(timeout)
            return self.events[index:], self.finished

    # ---- approval ------------------------------------------------------------
    def approver(self, agent, payload):
        self._decided.clear()
        self.waiting = {"agent": agent, **payload}
        self.push({"type": "interrupt", "agent": agent, "data": payload})
        asked = time.time()
        while not self._decided.wait(0.5):
            if self._stop.is_set():
                raise Cancelled("run stopped while waiting for approval")
            if time.time() - asked > APPROVAL_TIMEOUT_S:
                self._decision = {"decision": "reject", "ids": [], "reason": "nobody answered in time"}
                break
        self.waiting = None
        decision = dict(self._decision or {"decision": "reject", "ids": []})
        self.push({"type": "resumed", "agent": agent, "data": decision})
        return decision

    def resume(self, decision):
        if self.waiting is None:
            return False
        self._decision = decision
        self._decided.set()
        return True

    def stop(self):
        self._stop.set()

    # ---- the run -------------------------------------------------------------
    def execute(self):
        self.push({"type": "run_start", "run_id": self.id, "goal": self.request.get("goal") or "",
                   "mode": self.request.get("mode") or "full", "llm": self.llm.name,
                   "scenario": self.request.get("scenario") or {}})
        try:
            self.state = team.run_team(self.request, self.corpus, self.llm, self.push, self.approver, self._stop.is_set)
            self.push({"type": "done", "state": public_state(self.state),
                       "llm_rejected": getattr(self.llm, "rejected", [])})
        except Cancelled as err:
            self.push({"type": "error", "text": str(err)})
        except Exception as err:  # noqa: BLE001
            self.push({"type": "error", "text": f"{type(err).__name__}: {err}"})

    def snapshot(self):
        return {"run_id": self.id, "finished": self.finished, "waiting": self.waiting,
                "events": len(self.events), "state": public_state(self.state)}


def public_state(state):
    return jsonable({k: v for k, v in (state or {}).items() if k != "messages"})


RUNS = {}
LOCK = threading.Lock()


def start(request, corpus, llm=None):
    run = Run(request, corpus, llm)
    with LOCK:
        RUNS[run.id] = run
        finished = sorted((r for r in RUNS.values() if r.finished), key=lambda r: r.created)
        for old in finished[:max(0, len(RUNS) - MAX_RUNS)]:
            RUNS.pop(old.id, None)
    threading.Thread(target=run.execute, name=f"pyra-agents-{run.id}", daemon=True).start()
    return run


def get(run_id):
    return RUNS.get(run_id)


def latest_state():
    for run in sorted(RUNS.values(), key=lambda r: r.created, reverse=True):
        if run.state:
            return run.state
    return {}


def ask(agent, question, state, llm=None):
    """One agent answers from its own results. Scripted unless a model is connected."""
    llm = llm or OfflineLLM()
    label = team.LABELS.get(agent, agent)
    key = team.STATE_KEY.get(agent)
    if agent == "supervisor":
        done = list(dict.fromkeys(state.get("done") or []))
        fallback = (f"I routed the goal through {', '.join(done)}. {(state.get('report') or {}).get('headline', '')}"
                    if done else "No run yet. Start a run and I will route it through the team.")
        mine = {"done": done, "report": (state.get("report") or {}).get("headline")}
    elif not key or not state.get(key):
        return {"answer": f"{label}: I have not run yet, so I have nothing to report.", "label": "INTERPRETATION",
                "llm": llm.name}
    else:
        mine = state[key]
        sections = [s for s in team.nodes.build_report(state)["sections"] if s["agent"] == agent]
        bullets = [b for s in sections for b in s["bullets"] if b][:6]
        fallback = f"{label}: " + (" ".join(bullets) if bullets else (mine.get("summary") if isinstance(mine, dict) else "")
                                   or (state.get("report") or {}).get("headline", "done."))
    if not question or not getattr(llm, "live", False):
        return {"answer": fallback, "label": "INTERPRETATION", "llm": llm.name}
    answer = llm.think(agent, f"You are the {label} agent. Your role: {team.ROLES.get(agent, '')} Answer the "
                              "question using only your results. If they do not cover it, say so.",
                       {"question": question[:500], "my_results": jsonable(mine)}, fallback)
    return {"answer": answer, "label": "INTERPRETATION", "llm": llm.name}
