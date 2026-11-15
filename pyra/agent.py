"""The research agent: answers a question by calling PYRA's own engines.

The planner only decides which tool to call next and writes the words. The
tools (search, ranking, gaps, compare) do every calculation, and the final
text goes through assistant.check_answer() before anyone sees it. An answer
that still breaks a rule after one rewrite is withheld, not shown.

Three planners come with PYRA:

    offline  fixed rules and sentence templates, no language model at all
    groq     a Groq-hosted model through the openai package (pip install
             openai) and GROQ_API_KEY, also optional
    claude   Claude through the anthropic package, which is optional
             (pip install anthropic). Without it, or without a key, the
             offline planner is used.

Any object with begin(system, user, task), reply(results) and revise(note)
can drive the loop, which is how the tests run it with a scripted planner.

    python -m pyra.agent "Which runs used low pressure?"
"""

import argparse
import json
import os
import re

from . import assistant, compare, evidence, gaps, paths, ranking, retrieval

paths.load_env()

MAX_STEPS = 6
REVISIONS = 1
TOP_RANKED = 5
DEFAULT_MODEL = "claude-opus-5-5"
SCENARIO_KEYS = ("o2_percent", "pressure", "flow_speed", "gravity", "temperature")

AGENT_RULES = """

AGENT MODE: in this mode the request holds only SCENARIO, AUDIENCE and QUESTION. CONTEXT and TOOL_RESULTS reach you as tool results:
- search_evidence returns the passages. Call it before answering. Only the [S#] ids it returned may be cited.
- rank_investigations, analyze_gaps and compare_investigations return DERIVED numbers. Quote them as given, never recompute or round them.
- Leave out the scenario argument to use the user's own scenario.
- When you have enough, stop calling tools and write the answer with the headings 'MEASURED:', 'INTERPRETATION:' and 'Limits and gaps:', ending with the Confidence line.
- Plain text only, no markdown. Cite with ASCII square brackets like [S1], and start the last line with exactly 'Confidence: low', 'Confidence: medium' or 'Confidence: high'."""

SCENARIO_SCHEMA = {
    "type": "object",
    "description": "Raw scenario values: o2_percent, pressure with pressure_unit (kPa or psi), flow_speed "
                   "(cm/s), gravity_g, material, pillar, scale. Leave out to use the user's scenario.",
}
TOOL_SPECS = [
    {"name": "search_evidence",
     "description": "Search the indexed findings. Returns passages with [S#] ids, investigation and page.",
     "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "list_investigations",
     "description": "Every indexed investigation: acronym, name, pillar and how many test runs it has.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "rank_investigations",
     "description": "PYRA's deterministic ranking of investigations against a scenario, best first.",
     "input_schema": {"type": "object", "properties": {"scenario": SCENARIO_SCHEMA}}},
    {"name": "analyze_gaps",
     "description": "Per axis, whether the scenario was directly tested, bounded, one-sided or missing.",
     "input_schema": {"type": "object", "properties": {"scenario": SCENARIO_SCHEMA}}},
    {"name": "compare_investigations",
     "description": "Side-by-side comparison of two or more investigations, with a comparability verdict.",
     "input_schema": {"type": "object", "properties": {"acronyms": {"type": "array", "items": {"type": "string"}}},
                      "required": ["acronyms"]}},
]


class ToolInputError(ValueError):
    pass


class PlannerError(RuntimeError):
    pass


def system_prompt():
    return assistant.system_prompt() + AGENT_RULES


def user_message(question, scenario, audience):
    return "\n\n".join(["SCENARIO:\n" + json.dumps(scenario or {}, indent=2, default=str),
                        "AUDIENCE: " + audience, "QUESTION:\n" + question])


class Toolbox:
    """Runs tool calls against one corpus and keeps what they returned for the answer check."""

    def __init__(self, corpus, scenario=None, index=None):
        self.corpus = corpus
        self.scenario = scenario or {}
        self.index = index
        self.passages = {}
        self.results = []

    def _scenario(self, given):
        if given is not None and not isinstance(given, dict):
            raise ToolInputError(f"scenario must be an object of raw values, got {type(given).__name__}")
        return evidence.scenario(given if given else self.scenario)

    def search_evidence(self, query):
        if not isinstance(query, str) or not query.strip():
            raise ToolInputError("search_evidence needs a non-empty 'query' string")
        if self.index is None:
            self.index = retrieval.Index()
            self.index.index_corpus(self.corpus)
        hits = self.index.search(query)
        for hit in hits:
            self.passages[hit["id"]] = hit
        return {"passages": [{key: hit[key] for key in ("id", "investigation", "page", "section", "text")}
                             for hit in hits],
                "note": None if hits else "No passage reached the similarity threshold."}

    def list_investigations(self):
        runs = {}
        for run in self.corpus["runs"]:
            runs[run["acronym"]] = runs.get(run["acronym"], 0) + 1
        return {"investigations": [{"acronym": inv["acronym"], "name": inv.get("name"),
                                    "pillar": inv.get("pillar"), "runs": runs.get(inv["acronym"], 0)}
                                   for inv in self.corpus["investigations"]]}

    def rank_investigations(self, scenario=None):
        scen = self._scenario(scenario)
        ranked = ranking.rank(self.corpus, scen)[:TOP_RANKED]
        return {"label": "DERIVED", "ranked": [{key: entry[key] for key in
                                                ("acronym", "total", "evidence_class", "unmatched", "explanation")}
                                               for entry in ranked]}

    def analyze_gaps(self, scenario=None):
        found = gaps.analyze(self.corpus, self._scenario(scenario))
        axes = {axis: {key: value for key, value in result.items()
                       if key in ("class", "tested_min", "tested_max", "nearest_value", "runs_within")}
                for axis, result in found["axes"].items()}
        nearest = [{key: run[key] for key in ("acronym", "run_id", "distance")} for run in found["nearest_runs"][:3]]
        return {"label": "DERIVED", "axes": axes, "combination": found["combination"]["class"],
                "runs_matching_all_axes": len(found["combination"]["runs_matching"]), "nearest_runs": nearest}

    def compare_investigations(self, acronyms):
        if not isinstance(acronyms, list) or len(acronyms) < 2:
            raise ToolInputError("compare_investigations needs a list of at least two acronyms")
        known = {inv["acronym"] for inv in self.corpus["investigations"]}
        unknown = [a for a in acronyms if a not in known]
        if unknown:
            raise ToolInputError(f"not in the corpus: {', '.join(unknown)}. Known: {', '.join(sorted(known))}")
        found = compare.compare(self.corpus, acronyms)
        return {"label": "DERIVED", "comparable": found["verdict"]["comparable"],
                "reasons": found["verdict"]["reasons"], "can_conclude": found["can_conclude"],
                "cannot_conclude": found["cannot_conclude"]}

    def call(self, call):
        """{"id", "name", "input"} -> a step record with the result, or the error the planner gets back."""
        name, given = call["name"], call.get("input") or {}
        if name not in {spec["name"] for spec in TOOL_SPECS}:
            output, error = {"error": f"unknown tool '{name}'"}, True
        else:
            try:
                output, error = getattr(self, name)(**given), False
            except (ToolInputError, TypeError) as err:
                output, error = {"error": f"{name}: {err}"}, True
        self.results.append(output)
        return {"id": call.get("id"), "tool": name, "input": given, "output": output, "error": error}

    def allowed_text(self):
        """Everything an answer's numbers may come from."""
        return "\n".join([json.dumps(result, default=str) for result in self.results]
                         + [json.dumps(self.scenario, default=str)]
                         + [hit["text"] for hit in self.passages.values()])


def run(question, corpus, scenario=None, audience="student", planner=None, index=None, max_steps=MAX_STEPS):
    """Plan, call tools, write, check. Returns the answer with every step that led to it."""
    question = (question or "").strip()
    if not question:
        raise ValueError("the agent needs a question")
    if audience not in assistant.AUDIENCES:
        raise ValueError(f"audience must be one of {', '.join(assistant.AUDIENCES)}, got {audience!r}")
    planner = planner or OfflinePlanner()
    tools = Toolbox(corpus, scenario, index)
    task = {"question": question, "scenario": scenario or {}, "audience": audience}
    reply = planner.begin(system_prompt(), user_message(question, scenario, audience), task)
    steps, stopped = [], None
    while reply.get("calls"):
        if len(steps) >= max_steps:
            stopped = f"stopped after {max_steps} tool calls"
            break
        done = [tools.call(call) for call in reply["calls"]]
        steps.extend(done)
        reply = planner.reply([{"id": step["id"], "output": step["output"], "error": step["error"]} for step in done])

    result = {"question": question, "planner": planner.name, "label": "INTERPRETATION",
              "steps": [{key: step[key] for key in ("tool", "input", "output", "error")} for step in steps]}
    if not tools.passages:
        # Rule 2: without retrieved context there is nothing to cite, whatever the planner wrote.
        return dict(result, answer=assistant.no_data_reply(question), problems=[], passed=True,
                    revised=False, draft=None, stopped=stopped, context=[])

    text, problems, revised = assistant.tidy(reply.get("text")), [], False
    # A stopped planner still has tool calls waiting for results, so it cannot be asked to rewrite.
    revisions = 0 if stopped else REVISIONS
    for attempt in range(revisions + 1):
        if text.startswith(assistant.NO_DATA):
            # Rule 2 tells the model to say exactly this when the passages do not answer the question.
            # The model's own search suggestions are unchecked, so the fixed reply is shown instead.
            return dict(result, answer=assistant.no_data_reply(question), problems=[], passed=True,
                        revised=revised, draft=None, stopped=stopped,
                        context=sorted(tools.passages.values(), key=lambda hit: -hit["score"]))
        problems = assistant.check_answer(text, list(tools.passages), tools.allowed_text())
        if not problems or attempt == revisions:
            break
        reply, revised = planner.revise("Your answer broke these rules. Rewrite it so none apply:\n- "
                                        + "\n- ".join(problems)), True
        text = assistant.tidy(reply.get("text"))
    return dict(result, answer=None if problems else text, problems=problems, passed=not problems,
                revised=revised, draft=text if problems else None, stopped=stopped,
                context=sorted(tools.passages.values(), key=lambda hit: -hit["score"]))


# ---------- offline planner ----------

GAP_WORDS = {"DIRECTLY_TESTED": "directly tested", "BOUNDED": "bounded by tests on both sides",
             "ONE_SIDED": "beyond the tests on one side", "INSUFFICIENT": "near too few runs",
             "NOT_COMPARABLE": "not comparable with the indexed tests", "NO_INDEXED_DATA": "not in the indexed data"}
AXIS_NAMES = {"o2_percent": "Oxygen", "pressure": "Pressure", "flow_speed": "Flow speed", "gravity": "Gravity",
              "material_class": "Material class", "pillar": "Pillar"}
AUDIENCE_NOTE = {
    "student": "Bounded means tests sit on both sides of your value, so the answer lies between them, "
               "but nobody measured that exact point.",
    "researcher": "Classes follow the gap tolerances in config/decisions.json.",
    "engineer": "Treat a bounded or one-sided axis as an open requirement, not as a design margin.",
}
SYNONYMS = {"o2": "oxygen", "oxygen": "o2", "psi": "pressure", "kpa": "pressure", "microgravity": "gravity",
            "spread": "flame spread", "extinction": "extinguish", "burn": "flame"}


def _number(value):
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _clip(text, words=35):
    """The first sentence, shortened, with no end mark so the citation can go before the full stop."""
    first = assistant.sentences(text)[0] if assistant.sentences(text) else text
    parts = first.split()
    return " ".join(parts[:words]).rstrip(".!?") + (" ..." if len(parts) > words else "")


def _cited(passage):
    # check_answer splits sentences at ". ", so "p. 5" would orphan the citation.
    page = re.sub(r"\.\s+", ".", str(passage["page"])) if passage["page"] else "page not given"
    return f"{passage['investigation'] or 'A source'} ({page}): {_clip(passage['text'])} [{passage['id']}]."


def _quotable(text):
    """Passages we can quote without breaking a rule on our own words."""
    return not re.search(r"\b(?:un)?safe\b", text, re.IGNORECASE) and not assistant.OTHER_WORLDS.search(text)


class OfflinePlanner:
    """A fixed plan: look around, search, then rank, find gaps and compare when the question calls for it."""

    name = "offline"

    def begin(self, system, user, task):
        self.task, self.seen, self.round = task, {}, 0
        return {"calls": [{"id": "list", "name": "list_investigations", "input": {}},
                          {"id": "search", "name": "search_evidence", "input": {"query": task["question"]}}]}

    def reply(self, results):
        for result in results:
            self.seen[result["id"]] = result["output"]
        self.round += 1
        if self.round > 1:
            return {"text": self.write()}
        calls = []
        if not self.seen["search"].get("passages"):
            wider = [SYNONYMS[w] for w in retrieval.words(self.task["question"]) if w in SYNONYMS]
            material = (self.task["scenario"] or {}).get("material")
            extra = " ".join(wider + ([material] if material else []))
            if extra:
                calls.append({"id": "search2", "name": "search_evidence", "input": {"query": extra}})
        scen = evidence.scenario(self.task["scenario"])
        if any(scen[key] is not None for key in SCENARIO_KEYS) or scen["material"]:
            calls += [{"id": "rank", "name": "rank_investigations", "input": {}},
                      {"id": "gaps", "name": "analyze_gaps", "input": {}}]
        named = [inv["acronym"] for inv in self.seen["list"]["investigations"]
                 if re.search(rf"(?<![\w-]){re.escape(inv['acronym'])}(?![\w-])", self.task["question"], re.IGNORECASE)]
        if len(named) >= 2:
            calls.append({"id": "compare", "name": "compare_investigations", "input": {"acronyms": named}})
        return {"calls": calls} if calls else {"text": self.write()}

    def revise(self, note):
        # The templates cannot do better a second time; the loop withholds the answer instead.
        return {"text": self.write()}

    def write(self):
        passages = [p for key in ("search", "search2") for p in (self.seen.get(key) or {}).get("passages", [])]
        passages = [p for p in passages if _quotable(p["text"])][:3]
        measured = [_cited(p) for p in passages]
        meaning, limits = [], []

        ranked = (self.seen.get("rank") or {}).get("ranked") or []
        if ranked:
            lead = ranked[0]
            line = f"PYRA's ranking puts {lead['acronym']} first at {_number(lead['total'])} ({lead['evidence_class']} evidence)"
            if len(ranked) > 1:
                line += f", then {ranked[1]['acronym']} at {_number(ranked[1]['total'])}"
            meaning.append(line + ".")
            if lead["unmatched"]:
                limits.append(f"{lead['acronym']} does not match the scenario on {', '.join(lead['unmatched'])}.")

        found = self.seen.get("gaps")
        if found:
            for axis, result in found["axes"].items():
                if not result["class"]:
                    continue
                words = f"{AXIS_NAMES.get(axis, axis)} is {GAP_WORDS.get(result['class'], result['class'])}"
                if result.get("tested_min") is not None and result.get("tested_max") is not None:
                    words += f" (tested {_number(result['tested_min'])} to {_number(result['tested_max'])})"
                (meaning if result["class"] in ("DIRECTLY_TESTED", "BOUNDED") else limits).append(words + ".")
            matching = found["runs_matching_all_axes"]
            limits.append(f"Runs matching every axis at once: {_number(matching)}." if matching
                          else "No single run matches every axis at once.")
            meaning.append(AUDIENCE_NOTE[self.task["audience"]])

        verdict = self.seen.get("compare")
        if verdict:
            meaning.append("These investigations can be compared directly." if verdict["comparable"]
                           else "They are not directly comparable: " + verdict["reasons"][0].split(": ", 1)[-1] + ".")

        gravity = evidence.scenario(self.task["scenario"])["gravity"]
        if gravity is not None and 0 < gravity < 1:
            limits.append(f"A {_number(gravity)} g scenario is not directly measured here; at best it is bounded by "
                          "microgravity and 1 g tests.")
        if not meaning:
            meaning.append("Set a scenario in the Scenario Lab to get a ranking and gap check for it.")
        limits.append("Written by PYRA's offline templates, without a language model.")

        level = "high" if len(passages) >= 3 and found and found["combination"] == "DIRECTLY_TESTED" else \
            "medium" if len(passages) >= 2 else "low"
        why = {"high": "several passages were found and one run covers the whole scenario",
               "medium": "more than one passage was found, but the scenario is not fully covered",
               "low": "only one passage was found"}[level]
        return "\n".join(["MEASURED:", *measured, "", "INTERPRETATION:", *meaning, "", "Limits and gaps:", *limits,
                          "", f"Confidence: {level}, because {why}."])


# ---------- Claude planner ----------

class ClaudePlanner:
    """Claude picks the tools and writes the answer. Needs the anthropic package and a credential."""

    name = "claude"

    def __init__(self, model=None, effort=None, client=None):
        try:
            import anthropic
        except ImportError:
            raise PlannerError("The Claude planner needs the anthropic package (pip install anthropic). "
                               "Use the offline planner until it is installed.") from None
        self.anthropic = anthropic
        self.client = client or anthropic.Anthropic()
        self.model = model or claude_model()
        self.effort = effort or os.environ.get("PYRA_EFFORT", "medium")
        self.name = f"claude ({self.model})"

    def _send(self):
        errors = self.anthropic
        try:
            # fallbacks="default" lets the API retry a policy refusal on another model inside the same call.
            response = self.client.beta.messages.create(
                model=self.model, max_tokens=16000, system=self.system, tools=TOOL_SPECS,
                messages=self.messages, output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        except errors.AuthenticationError:
            raise PlannerError("Claude rejected the credential. Set ANTHROPIC_API_KEY or run 'ant auth login'.") from None
        except errors.RateLimitError as err:
            raise PlannerError(f"Claude is rate limiting PYRA; retry after "
                               f"{err.response.headers.get('retry-after', 'a minute')} seconds.") from None
        except errors.APIStatusError as err:
            raise PlannerError(f"Claude answered {err.status_code}: {err.message}") from None
        except errors.APIConnectionError:
            raise PlannerError("Could not reach the Claude API. Check the network, or use the offline planner.") from None
        if response.stop_reason == "refusal":
            raise PlannerError("Claude declined this question. Try rephrasing it, or use the offline planner.")
        self.messages.append({"role": "assistant", "content": response.content})
        calls = [{"id": block.id, "name": block.name, "input": block.input}
                 for block in response.content if block.type == "tool_use"]
        text = "".join(block.text for block in response.content if block.type == "text")
        if response.stop_reason == "max_tokens":
            text += "\n[cut off at the token limit]"
        return {"calls": calls, "text": text}

    def begin(self, system, user, task):
        self.system, self.messages = system, [{"role": "user", "content": user}]
        return self._send()

    def reply(self, results):
        self.messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": result["id"], "is_error": result["error"],
             "content": json.dumps(result["output"], default=str)} for result in results]})
        return self._send()

    def revise(self, note):
        self.messages.append({"role": "user", "content": note})
        return self._send()


# ---------- Groq planner ----------

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_DEFAULT_MODEL = "openai/gpt-oss-120b"


class GroqPlanner:
    """A Groq-hosted model picks the tools and writes the answer, through Groq's OpenAI-compatible API.
    Needs the openai package and GROQ_API_KEY."""

    name = "groq"

    def __init__(self, model=None, client=None):
        try:
            import openai
        except ImportError:
            raise PlannerError("The Groq planner needs the openai package (pip install openai). "
                               "Use the offline planner until it is installed.") from None
        if client is None and not os.environ.get("GROQ_API_KEY"):
            raise PlannerError("The Groq planner needs GROQ_API_KEY. Put it in .env or the environment.")
        self.openai = openai
        self.client = client or openai.OpenAI(api_key=os.environ["GROQ_API_KEY"], base_url=GROQ_BASE_URL)
        self.model = model or groq_model()
        self.name = f"groq ({self.model})"
        self.tools = [{"type": "function", "function": {"name": spec["name"], "description": spec["description"],
                                                        "parameters": spec["input_schema"]}}
                      for spec in TOOL_SPECS]

    def _send(self):
        errors = self.openai
        try:
            response = self.client.chat.completions.create(
                model=self.model, max_tokens=4096, messages=self.messages, tools=self.tools, tool_choice="auto")
        except errors.AuthenticationError:
            raise PlannerError("Groq rejected the key. Check GROQ_API_KEY in .env.") from None
        except errors.RateLimitError:
            raise PlannerError("Groq is rate limiting PYRA; wait a minute and retry.") from None
        except errors.APIStatusError as err:
            raise PlannerError(f"Groq answered {err.status_code}: {err.message}") from None
        except errors.APIConnectionError:
            raise PlannerError("Could not reach the Groq API. Check the network, or use the offline planner.") from None
        choice = response.choices[0]
        message = choice.message
        calls = []
        for call in message.tool_calls or []:
            try:
                given = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                given = {}
            calls.append({"id": call.id, "name": call.function.name, "input": given if isinstance(given, dict) else {}})
        entry = {"role": "assistant", "content": message.content or ""}
        if message.tool_calls:
            entry["tool_calls"] = [{"id": c.id, "type": "function",
                                    "function": {"name": c.function.name, "arguments": c.function.arguments or "{}"}}
                                   for c in message.tool_calls]
        self.messages.append(entry)
        text = message.content or ""
        if choice.finish_reason == "length":
            text += "\n[cut off at the token limit]"
        return {"calls": calls, "text": text}

    def begin(self, system, user, task):
        self.messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        return self._send()

    def reply(self, results):
        for result in results:
            self.messages.append({"role": "tool", "tool_call_id": result["id"],
                                  "content": json.dumps(result["output"], default=str)})
        return self._send()

    def revise(self, note):
        self.messages.append({"role": "user", "content": note})
        return self._send()


def groq_model():
    return os.environ.get("GROQ_MODEL", GROQ_DEFAULT_MODEL)


def groq_ready():
    """True when the openai package is installed and GROQ_API_KEY is in the environment."""
    try:
        import openai  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("GROQ_API_KEY"))


def claude_model():
    return os.environ.get("PYRA_MODEL", DEFAULT_MODEL)


def claude_ready():
    """True when the anthropic package is installed and a credential is in the environment."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def make_planner(kind="auto"):
    """'offline', 'claude', 'groq', or 'auto' (Claude when claude_ready(), then Groq when groq_ready(),
    else offline). PYRA_PLANNER overrides auto."""
    if kind == "auto":
        kind = os.environ.get("PYRA_PLANNER") or (
            "claude" if claude_ready() else "groq" if groq_ready() else "offline")
    if kind == "offline":
        return OfflinePlanner()
    if kind == "claude":
        return ClaudePlanner()
    if kind == "groq":
        return GroqPlanner()
    raise ValueError(f"planner must be offline, claude, groq or auto, not {kind!r}")


SMOKE_QUESTIONS = [
    ("How does flow change flame spread?", {}),
    ("Is there evidence for a lunar habitat fire?", {"o2_percent": 30, "pressure": 70, "gravity_g": 0.16}),
    ("Compare the two closest investigations", {}),
]


def smoke(planner_kind="auto", out=print, corpus=None):
    """Test run: ask the agent a few fixed questions end to end and report PASS or FAIL for each.
    Returns 0 when every answer passed the checks, 1 otherwise."""
    from .server import load_corpus
    corpus = corpus if corpus is not None else load_corpus()
    failures = 0
    for question, scenario in SMOKE_QUESTIONS:
        try:
            planner = make_planner(planner_kind)
            found = run(question, corpus, scenario, planner=planner)
        except PlannerError as err:
            out(f"FAIL  {question}\n      planner error: {err}")
            failures += 1
            continue
        tools = ", ".join(step["tool"] + ("!" if step["error"] else "") for step in found["steps"]) or "none"
        verdict = "PASS" if found["passed"] else "FAIL"
        out(f"{verdict}  {question}\n      planner {found['planner']}, tools: {tools}"
            f"{', rewritten once' if found['revised'] else ''}")
        for problem in found["problems"]:
            out("      - " + problem)
        failures += not found["passed"]
    out(f"\n{len(SMOKE_QUESTIONS) - failures} of {len(SMOKE_QUESTIONS)} answers passed the checks.")
    return 1 if failures else 0


def _console_safe():
    # Model text can hold characters the Windows console code page cannot print (for example 【).
    import sys
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _console_safe()
    parser = argparse.ArgumentParser(prog="python -m pyra.agent", description="Ask the PYRA research agent")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--smoke", action="store_true",
                        help="test run: ask a few fixed questions and report PASS/FAIL for each")
    parser.add_argument("--audience", default="student", choices=assistant.AUDIENCES)
    parser.add_argument("--planner", default="auto", choices=("auto", "offline", "claude", "groq"))
    parser.add_argument("--o2", type=float, help="scenario O2 percent")
    parser.add_argument("--pressure-kpa", type=float, help="scenario pressure in kPa")
    parser.add_argument("--gravity", type=float, help="scenario gravity in g")
    args = parser.parse_args(argv)
    if args.smoke:
        return smoke(args.planner)
    if not args.question:
        parser.error("give a question, or --smoke for a test run")

    from .server import load_corpus
    scenario = {key: value for key, value in [("o2_percent", args.o2), ("pressure", args.pressure_kpa),
                                              ("gravity_g", args.gravity)] if value is not None}
    try:
        found = run(args.question, load_corpus(), scenario, args.audience, make_planner(args.planner))
    except PlannerError as err:
        raise SystemExit(str(err)) from None
    for step in found["steps"]:
        print(f"  step: {step['tool']}({json.dumps(step['input'])}){'  ERROR' if step['error'] else ''}")
    print(f"\n[{found['label']}, planner {found['planner']}]\n")
    if found["passed"]:
        print(found["answer"])
        return 0
    print("Answer withheld, it broke these rules:")
    for problem in found["problems"]:
        print("  - " + problem)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
