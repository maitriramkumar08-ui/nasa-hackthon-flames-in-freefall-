"""The PYRA round table: several agents talk a SIMULATED cabin event through, then brief.

Every agent works the same way. PYRA's engines (concern, search, ranking,
gaps) produce the facts in code, a Groq model writes the agent's line from
those facts and the conversation so far, and the Auditor's checks run on the
line before it is shown. A line that still breaks a rule after one rewrite is
replaced by the agent's own template sentence, so the demo never shows an
unchecked claim. With no GROQ_API_KEY every agent speaks from its templates.

The chatbot (chat_stream) is the same idea for free questions: retrieval over
the findings and the project documents, a streamed Groq answer, and the checks
reported next to it.

    python -m pyra.crew --scenario overheating_wire
    python -m pyra.crew --chat "How does flow change flame spread?"
"""

import argparse
import functools
import json
import os
import re
import time

from . import agent, assistant, concern, evidence, paths, retrieval, telemetry

GROQ_MODEL = "openai/gpt-oss-120b"
# The agents are spread over several Groq models because each model has its own tokens-per-minute limit.
TABLE_MODELS = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b", "openai/gpt-oss-20b"]
DOC_FILES = [paths.ROOT / "data" / "eval" / "docs", paths.ROOT / "docs",
             paths.ROOT / "PYRA Predictive Hazard & Reliability Atlas for Spacecraft Fire Safety (1).md"]

ROSTER = [
    {"id": "incident", "name": "Incident Analyst", "role": "reads the cabin telemetry", "color": "#38bdf8", "emoji": "📡",
     "persona": "You watch the SIMULATED cabin telemetry. You report which channels tripped, by how much, and whether a reading could be a sensor fault rather than a fire."},
    {"id": "mission", "name": "Mission Profiles", "role": "frames the mission scenario", "color": "#f97316", "emoji": "🛰️",
     "persona": "You turn the cabin readings and the habitat's gravity into the mission scenario PYRA checks (oxygen, pressure, flow, gravity) and tell the others what to look for."},
    {"id": "librarian", "name": "Librarian", "role": "retrieves cited findings", "color": "#a78bfa", "emoji": "📚",
     "persona": "You search PYRA's indexed microgravity combustion findings and quote them with [S#] ids. You say plainly when the evidence is thin."},
    {"id": "ranker", "name": "Evidence Ranker", "role": "scores the closest studies", "color": "#14b8a6", "emoji": "📊",
     "persona": "You report PYRA's deterministic ranking of investigations against the scenario, quoting the scores exactly and saying what each top study does not match."},
    {"id": "gaps", "name": "Gap Hunter", "role": "finds untested conditions", "color": "#e879f9", "emoji": "🔍",
     "persona": "You report, axis by axis, whether the scenario was directly tested, bounded, one-sided or missing, and you hunt for the conditions nobody has measured."},
    {"id": "physicist", "name": "Physicist", "role": "explains flame behaviour", "color": "#f43f5e", "emoji": "🔥",
     "persona": "You explain what the conditions mean for flame behaviour, using only the passages, ranking and gap results the others gave. You never invent numbers."},
    {"id": "skeptic", "name": "Skeptic", "role": "challenges every claim", "color": "#eab308", "emoji": "🧐",
     "persona": "You challenge the table: which claims rest on thin or unverified evidence, which lines the audit sent back, and what would change the conclusion. You never call anything safe or unsafe."},
    {"id": "safety", "name": "Safety Officer", "role": "issues the checked brief", "color": "#22c55e", "emoji": "🛡️",
     "persona": "You turn the discussion into ILLUSTRATIVE next checks for the crew, always deferring to the crew's real approved procedure, and you deliver the decision brief."},
]
AGENTS = {a["id"]: a for a in ROSTER}

TABLE_RULES = """You are {name}, the {role} at PYRA's fire-safety round table. {persona}
Rules for every line you say:
- Use ONLY the FACTS given. Never write a number that is not in FACTS.
- Cite passages only with their [S#] ids from FACTS, ASCII brackets.
- Never call anything safe or unsafe. Never say results apply to the Moon or Mars.
- The cabin data is SIMULATED and the alert limits are PLACEHOLDER values; say so when you use them.
- Speak to the others by name when you build on what they said. Plain text, no markdown, at most {words} words."""

CHAT_RULES = """You are PYRA, a research assistant for NASA microgravity combustion and spacecraft fire safety.
Answer from the CONTEXT passages only and cite each fact with its [S#] id in ASCII brackets.
If the context does not cover the question, say so and suggest what to search for.
Never call a material or design safe or unsafe. Never claim microgravity results apply to the Moon or Mars;
say 'bounded by' or 'not directly measured'.
Use short paragraphs or bullet lists; markdown is fine. End with 'Confidence: low|medium|high' and why."""


# ---------- environment and model ----------

paths.load_env()


class Groq:
    """A thin wrapper over Groq's OpenAI-compatible API."""

    def __init__(self, model=None):
        import openai
        self.openai = openai
        self.model = model or os.environ.get("GROQ_MODEL", GROQ_MODEL)
        self.client = openai.OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url=agent.GROQ_BASE_URL)
        self.extra = {"reasoning_effort": "low"} if "gpt-oss" in self.model else {}

    def ask(self, system, user, max_tokens=700, model=None):
        """One completion. Groq limits tokens per minute per model, so a rate limit waits and retries,
        then moves to the next model in TABLE_MODELS before giving up."""
        models = [model or self.model] + [m for m in TABLE_MODELS if m != (model or self.model)]
        last = None
        for attempt, name in enumerate(models[:3]):
            try:
                response = self.client.chat.completions.create(
                    model=name, max_tokens=max_tokens,
                    extra_body={"reasoning_effort": "low"} if "gpt-oss" in name else {},
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
                return re.sub(r"<think>.*?</think>", "", response.choices[0].message.content or "", flags=re.DOTALL)
            except (self.openai.RateLimitError, self.openai.NotFoundError) as err:
                last = err
                time.sleep(1.5 * (attempt + 1))
        raise last

    def stream(self, messages, max_tokens=1200):
        for chunk in self.client.chat.completions.create(model=self.model, max_tokens=max_tokens, stream=True,
                                                         extra_body=self.extra, messages=messages):
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta


def make_llm(kind="auto"):
    """A Groq client, or None for the offline templates."""
    if kind == "offline" or not agent.groq_ready():
        return None
    return Groq()


# ---------- checks ----------

def _sourced(number, allowed_numbers):
    """A number counts as sourced when it is a source number rounded to the precision it was written with.
    Whole numbers up to 10 are allowed for counting ("three checks", "2 runs")."""
    if number in allowed_numbers or (number.is_integer() and 0 <= number <= 10):
        return True
    places = len(repr(number).split(".")[1]) if not number.is_integer() else 0
    return any(round(value, places) == number for value in allowed_numbers)


def unsourced(text, allowed):
    known = assistant._numbers(allowed)
    return sorted(n for n in assistant._numbers(text) if not _sourced(n, known))


def check_brief(text, ids, allowed):
    """assistant.check_answer, with rounded source numbers accepted."""
    known = assistant._numbers(allowed)
    return [p for p in assistant.check_answer(text, ids, allowed)
            if not (p.startswith("Number ") and _sourced(float(p.split()[1]), known))]


def audit(text, allowed, ids):
    """Rule breaks in one line at the table. [] means it passed."""
    problems = []
    numbers = unsourced(text, allowed)
    problems += [f"number {n:g} is not in the facts" for n in sorted(numbers)]
    cited = {sid.strip() for group in assistant.CITATION.findall(text) for sid in group.split(",")}
    problems += [f"cites {sid}, which was not retrieved" for sid in sorted(cited - set(ids))]
    problems += [f"uses the word '{w.lower()}'" for w in re.findall(r"\b(?:un)?safe\b", text, re.IGNORECASE)]
    for sentence in assistant.sentences(text):
        if assistant.OTHER_WORLDS.search(sentence) and assistant.APPLIES.search(sentence) \
                and not assistant.HEDGED.search(sentence):
            problems.append("claims results apply to the Moon or Mars")
    return problems


# ---------- the round table ----------

class Table:
    def __init__(self, llm, corpus):
        self.llm, self.corpus = llm, corpus
        self.transcript, self.fixes = [], []

    def transcript_text(self, last=8):
        return "\n".join(f"{AGENTS[m['agent']]['name']} ({AGENTS[m['agent']]['role']}): {m['text']}"
                         for m in self.transcript[-last:]) or "(nobody has spoken yet)"

    def speak(self, agent_id, task, facts, draft, ids=(), words=70):
        """One agent's line: Groq writes it from the facts, the audit checks it, the template backs it up."""
        who = AGENTS[agent_id]
        allowed = json.dumps(facts, default=str) + "\n" + self.transcript_text(50)
        text, source, problems = draft, "template", []
        if self.llm:
            system = TABLE_RULES.format(words=words, **who)
            citable = (f"You may cite ONLY these ids: {', '.join('[' + i + ']' for i in ids)}." if ids
                       else "No passages are available to you: do NOT write any [S#] citation or square brackets.")
            user = (f"FACTS:\n{json.dumps(facts, default=str)}\n\nCONVERSATION SO FAR:\n"
                    f"{self.transcript_text()}\n\nCITATIONS: {citable}\n\nYOUR TASK: {task}")
            try:
                model = TABLE_MODELS[[a["id"] for a in ROSTER].index(agent_id) % len(TABLE_MODELS)]
                text = assistant.tidy(self.llm.ask(system, user, model=model))
                problems = audit(text, allowed, ids)
                if problems:
                    self.fixes.append({"agent": who["name"], "problems": problems})
                    text = assistant.tidy(self.llm.ask(system, user + "\n\nYour last attempt broke these rules, "
                                                       "rewrite it so none apply:\n- " + "\n- ".join(problems)
                                                       + "\n\nLast attempt:\n" + text, model=model))
                    problems = audit(text, allowed, ids)
                source = model.split("/")[-1]
                if problems or not text:
                    text, source = draft, "template (model line failed the audit)"
            except Exception as err:  # the demo must keep going if the network drops
                text, source = draft, f"template ({type(err).__name__})"
        message = {"type": "message", "agent": agent_id, "text": text, "source": source,
                   "label": "INTERPRETATION", "t": time.time()}
        self.transcript.append(message)
        return message


def _scenario_from_cabin(sample, gravity_g):
    return {"o2_percent": sample["o2_percent"], "pressure": sample["total_pressure_kpa"], "pressure_unit": "kPa",
            "flow_speed": sample["flow_cm_s"], "gravity_g": gravity_g}


def _query_for(alerts):
    words = {"smoke_level": "smoke overheating wire flame", "co_ppm": "carbon monoxide smoldering",
             "o2_percent": "oxygen concentration flame spread", "flow_cm_s": "flow speed flame spread",
             "temperature_c": "heating temperature ignition", "total_pressure_kpa": "pressure flame"}
    return " ".join(dict.fromkeys(words.get(a["channel"], a["channel"]) for a in alerts)) or "flame spread flow oxygen"


def mission(corpus, scenario="overheating_wire", seed=1, steps=90, gravity_g=0.0, llm="auto", pace=1.0):
    """Yield the events of one SIMULATED run: telemetry, the round-table conversation and the brief."""
    llm = make_llm(llm) if isinstance(llm, str) else llm
    pause = (lambda seconds: time.sleep(seconds * pace)) if pace else (lambda seconds: None)
    yield {"type": "roster", "agents": ROSTER, "scenario": scenario, "model": " · ".join(m.split("/")[-1] for m in TABLE_MODELS) if llm else "offline templates",
           "label": "SIMULATED"}

    history, alerts, sample = [], [], None
    for sample in telemetry.stream(scenario, seed, steps, 1.0, "habitat"):
        verdict = concern.evaluate(sample, corpus, "solid", history)
        history.append(sample)
        yield {"type": "telemetry", "sample": sample, "alerts": verdict["alerts"]}
        pause(0.08)
        if verdict["alerts"]:
            alerts = verdict["alerts"]
            break
    yield {"type": "convene", "t": sample["t"], "alerts": alerts}

    table = Table(llm, corpus)
    say = functools.partial(_turn, table, pause)
    tools = agent.Toolbox(corpus)
    found = {}

    def run_tool(agent_id, name, given):
        yield {"type": "typing", "agent": agent_id, "tool": f"{name}({json.dumps(given) if given else ''})"}
        step = tools.call({"id": name, "name": name, "input": given})
        found[name] = step["output"]
        yield {"type": "tool", "agent": agent_id, "tool": name, "input": given, "output": step["output"],
               "error": step["error"]}
        pause(0.4)

    # 1. Incident Analyst reports what tripped.
    alert_facts = [{k: a[k] for k in ("type", "channel", "value", "limit", "label", "message")} for a in alerts]
    reading = {k: sample[k] for k in telemetry.CHANNELS}
    draft = ("Nominal cabin. Every channel stayed inside the PLACEHOLDER limits for the whole SIMULATED run."
             if not alerts else f"Alert at t={sample['t']:g} s: " + "; ".join(a["message"] for a in alerts)
             + ". The data is SIMULATED and the limits are PLACEHOLDER values.")
    yield from say("incident", "Report what the telemetry shows and whether it could be a sensor fault.",
                   {"time_s": sample["t"], "alerts": alert_facts, "latest_reading": reading}, draft)

    # 2. Mission Profiles frames the scenario.
    scen = _scenario_from_cabin(sample, gravity_g)
    tools.scenario = scen
    draft = (f"Mission profile: O2 {sample['o2_percent']:g} %, pressure {sample['total_pressure_kpa']:g} kPa, "
             f"flow {sample['flow_cm_s']:g} cm/s, gravity {gravity_g:g} g. Librarian, find the evidence; Evidence "
             "Ranker and Gap Hunter, score and probe it against this profile.")
    yield from say("mission", "Turn the readings into the mission scenario and tell the Librarian, Evidence Ranker "
                              "and Gap Hunter what to check.", {"alerts": alert_facts, "cabin_scenario": scen},
                   draft, words=60)

    # 3. Librarian retrieves passages.
    query = _query_for(alerts)
    yield from run_tool("librarian", "search_evidence", {"query": query})
    passages = found["search_evidence"].get("passages", [])
    ids = [p["id"] for p in passages]
    quotable = [p for p in passages if agent._quotable(p["text"])][:3]
    draft = (" ".join(agent._cited(p) for p in quotable) if quotable
             else "No indexed passage reached the similarity threshold for these conditions.")
    yield from say("librarian", "Tell the table what the retrieved passages report, citing [S#] ids.",
                   {"query": query, "passages": passages}, draft, ids)

    # 4. Evidence Ranker scores the investigations.
    yield from run_tool("ranker", "rank_investigations", {})
    ranked = found["rank_investigations"]["ranked"]
    if ranked:
        draft = " ".join(f"{r['acronym']} scores {agent._number(r['total'])} ({r['evidence_class']})." for r in ranked[:3])
        if ranked[0]["unmatched"]:
            draft += f" {ranked[0]['acronym']} does not match on {', '.join(ranked[0]['unmatched'])}."
    else:
        draft = "No investigation could be ranked."
    yield from say("ranker", "Report the ranking against the mission profile, quoting the scores exactly.",
                   {"ranking": ranked}, draft, ids)

    # 5. Gap Hunter probes the untested conditions.
    yield from run_tool("gaps", "analyze_gaps", {})
    gap = found["analyze_gaps"]
    lines = [f"{agent.AXIS_NAMES.get(axis, axis)} is {agent.GAP_WORDS.get(r['class'], r['class'])}."
             for axis, r in gap["axes"].items() if r["class"]]
    lines.append("No single run matches every axis at once." if not gap["runs_matching_all_axes"]
                 else f"{gap['runs_matching_all_axes']} run(s) match every axis.")
    yield from say("gaps", "Report axis by axis what is tested, bounded or missing, and the biggest gap.",
                   {"gaps": gap, "cabin_scenario": scen}, " ".join(lines), ids, words=80)

    # 6. Physicist interprets.
    draft = ("Building on the Librarian's passages and the Gap Hunter's classes, the flame behaviour here is only "
             "bounded by the tests, not directly measured.")
    yield from say("physicist", "Explain what the passages, ranking and gaps mean for flame behaviour in this cabin, "
                                "building on the others by name.",
                   {"passages": passages, "ranking": ranked, "gaps": gap, "cabin_scenario": scen}, draft, ids, words=90)

    # 7. Skeptic challenges the table and reports the audit.
    fixes = list(table.fixes)
    draft = "Challenge: the evidence behind these lines is thin. " + (
        "Every line passed the audit first time." if not fixes else
        "The audit sent back " + ", ".join(sorted({f["agent"] for f in fixes})) + " before you saw their lines.")
    gap_classes = {a: r["class"] for a, r in gap["axes"].items()}
    yield from say("skeptic", "Challenge the weakest claims at the table, say which lines the audit sent back, and "
                              "what evidence would change the conclusion.",
                   {"fixes": fixes, "passages": passages, "gap_classes": gap_classes}, draft, ids, words=70)

    # 8. Safety Officer: ILLUSTRATIVE checks, then the brief held to the full answer check.
    draft = ("ILLUSTRATIVE checks: confirm the reading on a second sensor, tell mission control which compartment "
             "it is in, and follow the crew's approved procedure. This is not a procedure.")
    yield from say("safety", "Propose three short ILLUSTRATIVE next checks, answering the Skeptic, deferring to the "
                             "approved procedure.", {"alerts": alert_facts, "gap_classes": gap_classes},
                   draft, words=60)
    yield {"type": "typing", "agent": "safety"}
    brief = _brief(table, corpus, scen, found, alerts)
    yield {"type": "brief", "agent": "safety", **brief}
    yield {"type": "done", "fixes": table.fixes}


def _turn(table, pause, agent_id, task, facts, draft, ids=(), words=70):
    yield {"type": "typing", "agent": agent_id}
    pause(0.6)
    yield table.speak(agent_id, task, facts, draft, ids, words)
    pause(0.3)


def _brief(table, corpus, scen, found, alerts):
    tools = agent.Toolbox(corpus, scen)
    tools.results = list(found.values())
    tools.passages = {p["id"]: p for p in found["search_evidence"].get("passages", [])}
    planner = agent.OfflinePlanner()
    planner.task = {"question": "cabin alert", "scenario": scen, "audience": "engineer"}
    planner.seen = {"search": found["search_evidence"], "rank": found["rank_investigations"],
                    "gaps": found["analyze_gaps"]}
    fallback = planner.write()
    allowed = tools.allowed_text() + "\n" + json.dumps(alerts, default=str)
    if not tools.passages:
        return {"text": assistant.no_data_reply("cabin alert"), "passed": True, "source": "template", "problems": []}
    if table.llm:
        system = assistant.system_prompt() + agent.AGENT_RULES
        user = (f"SCENARIO:\n{json.dumps(scen)}\nAUDIENCE: engineer\nTOOL_RESULTS:\n"
                f"{json.dumps({k: v for k, v in found.items() if k != 'search_evidence'}, default=str)}\n"
                f"CONTEXT:\n" + "\n\n".join(assistant.context_block(p) for p in tools.passages.values())
                + f"\nROUND TABLE:\n{table.transcript_text(20)}\n\nQUESTION:\nWrite the decision brief for this "
                  f"SIMULATED cabin alert.")
        try:
            text = assistant.tidy(table.llm.ask(system, user, 1500))
            problems = check_brief(text, list(tools.passages), allowed)
            if problems:
                text = assistant.tidy(table.llm.ask(system, user + "\n\nYour draft broke these rules, rewrite it:\n- "
                                                    + "\n- ".join(problems) + "\n\nDraft:\n" + text, 1500))
                problems = check_brief(text, list(tools.passages), allowed)
            if not problems:
                return {"text": text, "passed": True, "source": "groq", "problems": []}
            table.fixes.append({"agent": "Safety Officer", "problems": problems})
        except Exception as err:
            table.fixes.append({"agent": "Safety Officer", "problems": [f"model call failed: {type(err).__name__}"]})
    problems = check_brief(fallback, list(tools.passages), allowed)
    return {"text": fallback, "passed": not problems, "source": "template", "problems": problems}


# ---------- RAG chatbot ----------

_INDEX = {}


def chat_index(corpus):
    """Findings plus the project documents, indexed once per corpus."""
    key = id(corpus)
    if key not in _INDEX:
        index = retrieval.Index()
        index.index_corpus(corpus)
        for target in DOC_FILES:
            files = sorted(target.glob("*")) if target.is_dir() else [target]
            for path in files:
                if path.suffix.lower() in (".txt", ".md") and path.is_file():
                    index.add_file(path, path.stem)
        _INDEX[key] = index
    return _INDEX[key]


def chat_stream(question, corpus, history=None, llm="auto"):
    """Yield {"type": "sources"}, then "token" pieces, then "done" with the audit of the full answer."""
    question = (question or "").strip()
    if not question:
        raise ValueError("chat needs a question")
    llm = make_llm(llm) if isinstance(llm, str) else llm
    context_query = " ".join([m["content"] for m in (history or [])[-2:] if m.get("role") == "user"] + [question])
    hits = chat_index(corpus).search(context_query, k=6)
    yield {"type": "sources", "sources": hits, "model": llm.model if llm else "offline"}
    if not hits:
        text = assistant.no_data_reply(question)
        yield {"type": "token", "text": text}
        yield {"type": "done", "text": text, "problems": []}
        return
    if llm is None:
        text = "\n\n".join(f"- {agent._clip(h['text'], 40)} [{h['id']}]" for h in hits[:4]) + \
               "\n\nConfidence: low, these are the closest passages; no language model is configured."
        for piece in re.split(r"(\s+)", text):
            yield {"type": "token", "text": piece}
        yield {"type": "done", "text": text, "problems": []}
        return
    messages = [{"role": "system", "content": CHAT_RULES}]
    for turn in (history or [])[-6:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": str(turn["content"])[:3000]})
    messages.append({"role": "user", "content": "CONTEXT:\n" + "\n\n".join(assistant.context_block(h) for h in hits)
                     + "\n\nQUESTION:\n" + question})
    text = ""
    try:
        for piece in llm.stream(messages):
            text += piece
            yield {"type": "token", "text": piece}
    except Exception as err:
        yield {"type": "error", "error": f"Groq call failed: {err}"}
    allowed = "\n".join(h["text"] for h in hits) + question
    yield {"type": "done", "text": text, "problems": audit(assistant.tidy(text), allowed, [h["id"] for h in hits])}


# ---------- command line ----------

def main(argv=None):
    agent._console_safe()
    parser = argparse.ArgumentParser(prog="python -m pyra.crew", description="PYRA round table and chatbot")
    parser.add_argument("--scenario", default="overheating_wire", choices=sorted(telemetry.SCENARIOS))
    parser.add_argument("--gravity", type=float, default=0.0)
    parser.add_argument("--offline", action="store_true", help="templates only, no Groq")
    parser.add_argument("--chat", help="ask the RAG chatbot one question instead")
    args = parser.parse_args(argv)
    from .server import load_corpus
    corpus = load_corpus()
    kind = "offline" if args.offline else "auto"
    if args.chat:
        for event in chat_stream(args.chat, corpus, llm=kind):
            if event["type"] == "sources":
                print(f"[{event['model']}] sources: {', '.join(h['id'] for h in event['sources'])}\n")
            elif event["type"] == "token":
                print(event["text"], end="", flush=True)
            elif event["type"] == "done":
                print("\n\nchecks:", event["problems"] or "passed")
            else:
                print("\n", event)
        return 0
    for event in mission(corpus, args.scenario, gravity_g=args.gravity, llm=kind, pace=0):
        kind_ = event["type"]
        if kind_ == "roster":
            print(f"Round table, {len(event['agents'])} agents, model: {event['model']}")
        elif kind_ == "convene":
            print(f"\n-- table convened at t={event['t']:g} s, {len(event['alerts'])} alert(s) --")
        elif kind_ == "tool":
            print(f"   [{AGENTS[event['agent']]['name']} ran {event['tool']}]")
        elif kind_ == "message":
            who = AGENTS[event["agent"]]
            print(f"\n{who['name']} ({who['role']}, {event['source']}):\n  {event['text']}")
        elif kind_ == "brief":
            print(f"\n=== Brief ({event['source']}, {'passed' if event['passed'] else 'FAILED'} checks) ===\n"
                  f"{event['text']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
