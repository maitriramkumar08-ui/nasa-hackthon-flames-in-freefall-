"""What every agent gets: AgentCtx, plus the offline stand-in for a language model.

The rule that keeps the agents honest (PYRA rule 8): numbers come from plain
Python tools; a model only rewords text or picks between options, and every
model call carries a scripted fallback. A node must give the right answer
with OfflineLLM, so the whole team runs with nothing installed and no key.

Inside a node (pyra/agents/nodes.py):

    ctx.emit("thought", "Reading the corpus")
    found = ctx.tool("rank", ranking.rank, corpus=corpus, scen=scen)   # logs the call and its result
    text = ctx.llm.think(agent, system="...", payload={...}, fallback="Scripted sentence.")
    decision = ctx.ask_human({...})                                    # human approval (blocks)
"""

import json
import time


class OfflineLLM:
    """Deterministic stand-in. pyra.agents.llm.ChatLLM has the same three methods."""
    name = "offline (scripted, no model)"
    live = False

    def think(self, agent, system, payload, fallback):
        return fallback

    def choose(self, agent, question, options, payload, fallback=0):
        return fallback

    def json(self, agent, system, payload, fallback):
        return dict(fallback)


def summarize(value, limit=600):
    """Keep tool results small enough to stream to the page."""
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)[:limit]
    if len(text) <= limit:
        return value
    if isinstance(value, list):
        return {"items": len(value), "first": value[:2]}
    if isinstance(value, dict):
        return {k: (v if len(json.dumps(v, default=str)) < 160 else "...") for k, v in list(value.items())[:14]}
    return text[:limit]


class Cancelled(Exception):
    """Raised between steps when someone stopped the run."""


class AgentCtx:
    def __init__(self, agent, llm=None, sink=None, approver=None, corpus=None):
        self.agent = agent
        self.llm = llm or OfflineLLM()
        self.sink = sink or (lambda event: None)
        self.approver = approver
        self.corpus = corpus
        self.messages = []

    def emit(self, kind, text, data=None):
        """kind: thought | tool | result | handoff | warning | llm"""
        message = {"agent": self.agent, "kind": kind, "text": text, "t": time.time()}
        if data is not None:
            message["data"] = summarize(data)
        self.messages.append(message)
        self.sink({"type": "message", "agent": self.agent, "data": message})

    def tool(self, name, fn, **kwargs):
        shown = ", ".join(f"{k}={v!r}" for k, v in kwargs.items()
                          if isinstance(v, (str, int, float, bool)) or v is None)
        self.emit("tool", f"{name}({shown})", {"tool": name})
        started = time.time()
        out = fn(**kwargs)
        self.emit("result", f"{name} done in {int((time.time() - started) * 1000)} ms",
                  {"tool": name, "result": summarize(out)})
        return out

    def handoff(self, to, why):
        self.emit("handoff", f"Handing over to {to}: {why}", {"to": to})

    def ask_human(self, payload):
        """Block until a person decides. Without an approver nothing is approved."""
        if self.approver is None:
            return {"decision": "reject", "ids": [], "reason": "no reviewer connected"}
        decision = self.approver(self.agent, payload)
        return decision if isinstance(decision, dict) else {"decision": "reject", "ids": []}
