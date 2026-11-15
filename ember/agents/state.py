"""Shared LangGraph state for the EMBER agent team. THIS FILE IS THE CONTRACT.

EMBER = Evidence-based Microgravity Burn Expert Reasoners (NASA Space Apps 2026,
"Flame in Freefall"). Same rules as HUKUM: every agent returns ONLY its own key,
`messages` is append-only, numbers come from deterministic tools in
agents/tools/fire_tools.py and the LLM only writes words.

Units: pressure psia, oxygen % by volume, gravity in multiples of Earth g (g0),
velocity m/s, length m.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class Message(TypedDict, total=False):
    agent: str
    kind: str      # "thought" | "tool" | "result" | "handoff" | "warning" | "llm"
    text: str
    data: Any
    t: float


class EmberState(TypedDict, total=False):
    # ---- request ---------------------------------------------------------
    goal: str
    mode: str                 # "full" | "risk" | "gaps" | "lessons" | "custom"
    agents: list[str]
    scenario: dict            # {"mission": "iss"|"gateway"|"lunar"|"mars_transit"|"mars_surface",
                              #  "pilot_mode": "shadow"|"approve", "materials": [ids], "fan_m_s": float}
    # ---- routing -----------------------------------------------------------
    route: list[str]
    done: list[str]
    next: str
    messages: Annotated[list[Message], operator.add]

    # ---- agent outputs (one key per agent) ---------------------------------
    corpus: dict       # librarian -> {"records": [...], "dropped": [...], "counts": {...}, "sources": [...]}
    mission: dict      # mission_profiler -> {"id","name","gravity_g","pressure_psia","o2_pct","ppo2_psia",
                       #   "fan_m_s","comm_delay_min","o2_sources":[...], "atmosphere_key", "notes"}
    physics: dict      # physicist -> {"buoyant_velocity_m_s","mixing_ratio","regime","earth_test_relevance",
                       #   "fan_shutdown_effect","assumptions":[...], "summary"}
    risk: dict         # risk_ranker -> {"iteration", "items":[{"material","name","loi_1g","eff_limit","margin",
                       #   "band","verdict","score","confidence","evidence":[ids],"why"}], "history":[...]}
    review: dict       # skeptic -> {"iteration","approved","issues":[{"code","severity","material","text","fix"}]}
    risk_iterations: int
    incidents: dict    # incident_analyst -> {"cases":[{"id","name","year","chain":{...},"match","match_reasons":[...]}]}
    gaps: dict         # gap_hunter -> {"matrix":{...}, "mission_cell":{...}, "gaps":[...], "proposal":{...}}
    actions: dict      # safety_officer -> {"recommendations":[...], "pilot_mode", "approved_ids", "rejected_ids"}
    approvals: list[dict]
    report: dict       # reporter -> {"headline","sections":[...],"kpis":{...}}


AGENTS: list[tuple[str, str, str]] = [
    ("librarian", "Librarian", "Loads NASA PSI combustion investigations, drops non-combustion records and tags each by topic, phase, materials and atmosphere."),
    ("mission_profiler", "Mission Profiler", "Turns the chosen mission into gravity, cabin pressure, oxygen, ventilation, comm delay and oxygen sources."),
    ("physicist", "Physicist", "Compares buoyant flow with fan flow to find the flame regime, and says how relevant Earth flammability tests are."),
    ("risk_ranker", "Risk Ranker", "Ranks cabin materials by oxygen margin to their flammability limit at mission conditions, with evidence and confidence."),
    ("skeptic", "Skeptic", "Rejects any risk claim that goes beyond the tested envelope and sends the ranking back until it is honest."),
    ("incident_analyst", "Incident Analyst", "Breaks Apollo 1, Apollo 13 and Mir into a fire chain and checks the mission for the same links."),
    ("gap_hunter", "Gap Hunter", "Maps which gravity, atmosphere and topic combinations NASA has tested and designs the experiment that fills the most important gap."),
    ("safety_officer", "Safety Officer", "Turns findings into crew and design recommendations and waits for human approval."),
]
AGENT_IDS: list[str] = [a for a, _, _ in AGENTS]
