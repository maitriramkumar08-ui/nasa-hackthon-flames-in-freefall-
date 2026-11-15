"""PYRA agents: a supervised team of evidence agents over the PYRA engines.

Ported from the EMBER prototype (ember/agents, LangGraph + FastAPI) to the
standard library, and bound to PYRA's rules (docs/RULES.md): the agents use
the same corpus, ranking, gap and builder engines as the rest of the app,
every claim carries a label and a citation, a Skeptic sends drafts back until
they pass, and a person approves the recommendations.

    ctx.py    AgentCtx and the scripted OfflineLLM
    llm.py    optional OpenAI-compatible model, every answer checked by rule_problems()
    tools.py  deterministic tools: scenario, flow regime, claims, review, incidents, gaps, actions
    nodes.py  the eight agents and the reporter
    team.py   roster, supervisor routing, review loop and the graph runner
    runs.py   background runs, event stream and human approval for the web server
"""

from .team import AGENT_IDS, AGENTS, describe, run_team  # noqa: F401
