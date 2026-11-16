"""The in-app research assistant (Prompt 7): prompt building and answer checking.

The model itself is not called from here. answer() takes ask_model, any
function (system, user) -> text, so the app can plug in whichever provider it
uses and tests can pass a fake. Whatever comes back is checked against our
rules by check_answer() before anyone sees it, and the whole answer is labeled
INTERPRETATION. With no retrieved context the model is never asked.
"""

import json
import re

from . import evidence

NO_DATA = "No data found in the indexed sources."
AUDIENCES = ("student", "researcher", "engineer")

SYSTEM_PROMPT = """You are the PYRA research assistant. You answer questions about NASA microgravity combustion investigations using ONLY the retrieved context provided in each request. You are not a fire-safety authority.

RULES:
1. Use only the provided CONTEXT blocks. Each block has an id like [S12]. Cite every factual sentence with its id(s).
2. If the context does not contain the answer, reply exactly: 'No data found in the indexed sources.' and suggest what to search for.
3. Never state or compute numbers that are not in the context. If a calculation is needed, request the tool result; do not do it yourself.
4. Separate your answer into: (a) What the sources report (MEASURED), (b) What this means for the user's scenario (INTERPRETATION), (c) Limits and gaps.
5. Never say a material or design is safe or unsafe. Never say microgravity results apply to the Moon or Mars. Say 'bounded by' or 'not directly measured'.
6. Match the explanation depth to AUDIENCE: student | researcher | engineer.
7. Keep answers under {word_limit} words unless asked for detail. End with 'Confidence: low|medium|high' and one sentence why.

INPUT FORMAT: SCENARIO (json), AUDIENCE, TOOL_RESULTS (ranking and gap json), CONTEXT (blocks with ids), QUESTION."""

CITATION = re.compile(r"\[(S\d+(?:\s*,\s*S\d+)*)\]")
NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?")
OTHER_WORLDS = re.compile(r"\b(moon|lunar|mars|martian)\b", re.IGNORECASE)
APPLIES = re.compile(r"\b(appl(y|ies|icable)|valid|transfers?|holds?|same as|extends?|carr(y|ies) over)\b",
                     re.IGNORECASE)
HEDGED = re.compile(r"\b(not|bounded by|cannot|can't|no)\b", re.IGNORECASE)


def word_limit():
    return evidence.decisions()["assistant_word_limit"]


def system_prompt():
    return SYSTEM_PROMPT.format(word_limit=word_limit())


def context_block(chunk):
    """One CONTEXT entry: the id, where it came from, then the text."""
    where = ", ".join(f"{name} {chunk[name]}" for name in ("investigation", "source_id", "page", "section")
                      if chunk.get(name) is not None)
    return f"[{chunk['id']}] ({where})\n{chunk['text']}"


def build_messages(scenario, audience, tool_results, context_chunks, question):
    """{"system", "user"} in the Prompt 7 INPUT FORMAT."""
    if audience not in AUDIENCES:
        raise ValueError(f"audience must be one of {', '.join(AUDIENCES)}, got {audience!r}")
    user = "\n\n".join([
        "SCENARIO:\n" + json.dumps(scenario or {}, indent=2, default=str),
        "AUDIENCE: " + audience,
        "TOOL_RESULTS:\n" + json.dumps(tool_results or {}, indent=2, default=str),
        "CONTEXT:\n" + "\n\n".join(context_block(chunk) for chunk in context_chunks),
        "QUESTION:\n" + question,
    ])
    return {"system": system_prompt(), "user": user}


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]


def measured_section(text):
    """The text between the MEASURED heading and the INTERPRETATION one, or None."""
    found = re.search(r"MEASURED\)?:?(.*?)(?=^[^\n]*(?:INTERPRETATION|Limits)|\Z)", text,
                      re.DOTALL | re.MULTILINE)
    return found.group(1) if found else None


ODD_BRACKETS = str.maketrans({"【": "[", "】": "]", "［": "[", "］": "]", "〔": "[", "〕": "]"})


def tidy(text):
    """Undo formatting habits of hosted models that the checks would otherwise reject:
    full-width brackets around ids (【S1】), markdown bold or italics on headings
    (**MEASURED:**) and trailing double-space line breaks. The wording is not touched."""
    text = (text or "").translate(ODD_BRACKETS)
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"(?m)^(\s*)\*(?=\S)(.*?)\*(?=\s*$)", r"\1\2", text)
    return re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE).strip()


def _numbers(text):
    return {float(n) for n in NUMBER.findall(CITATION.sub(" ", text))}


def check_answer(text, context_ids, allowed_text="", limit=None):
    """Rule breaks in a model answer, as plain sentences. [] means it passed.

    allowed_text is the context and tool results: any number the answer uses must appear there.
    """
    problems = []
    measured = measured_section(text)
    if measured is None:
        problems.append("No MEASURED section.")
    else:
        for sentence in sentences(measured):
            if re.search(r"[A-Za-z]{3}", sentence) and not CITATION.search(sentence):
                problems.append(f"MEASURED sentence without a citation: {sentence!r}")

    cited = {sid.strip() for group in CITATION.findall(text) for sid in group.split(",")}
    for sid in sorted(cited - set(context_ids)):
        problems.append(f"Cites [{sid}], which is not in the context.")

    body = re.sub(r"^\s*Confidence:.*$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    for number in sorted(_numbers(body) - _numbers(allowed_text)):
        problems.append(f"Number {number:g} is not in the context or tool results.")

    for word in sorted({w.lower() for w in re.findall(r"\b(?:un)?safe\b", text, re.IGNORECASE)}):
        problems.append(f"Uses the word '{word}'.")

    for sentence in sentences(text):
        if OTHER_WORLDS.search(sentence) and APPLIES.search(sentence) and not HEDGED.search(sentence):
            problems.append(f"Claims results apply to the Moon or Mars: {sentence!r}")

    if not re.search(r"^\s*Confidence:\s*(low|medium|high)\b", text, re.MULTILINE | re.IGNORECASE):
        problems.append("Missing the 'Confidence: low|medium|high' line.")

    limit = limit or word_limit()
    count = len(text.split())
    if count > limit:
        problems.append(f"{count} words, over the {limit} word limit.")
    return problems


def no_data_reply(question):
    return (f"{NO_DATA} Try searching for the investigation acronym, the material or the "
            f"quantity (oxygen, pressure, flow, gravity) behind: \"{question}\".")


def answer(question, context_chunks, scenario=None, audience="student", tool_results=None, ask_model=None):
    """{"text", "problems", "label", "messages"}. text is None when no ask_model is given."""
    if not context_chunks:
        return {"text": no_data_reply(question), "problems": [], "label": "INTERPRETATION",
                "messages": None}
    messages = build_messages(scenario, audience, tool_results, context_chunks, question)
    if ask_model is None:
        return {"text": None, "problems": [], "label": "INTERPRETATION", "messages": messages}
    text = tidy(ask_model(messages["system"], messages["user"]))
    allowed = "\n".join([chunk["text"] for chunk in context_chunks]
                        + [json.dumps(tool_results or {}, default=str), json.dumps(scenario or {}, default=str)])
    problems = check_answer(text, [chunk["id"] for chunk in context_chunks], allowed)
    return {"text": text, "problems": problems, "label": "INTERPRETATION", "messages": messages}
