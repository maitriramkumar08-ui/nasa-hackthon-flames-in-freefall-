"""Optional language model for the agents, standard library only.

get_llm() returns ChatLLM when GROQ_API_KEY (or PYRA_LLM_API_KEY) is set and
PYRA_AGENTS_OFFLINE is not "1"; otherwise the scripted OfflineLLM. Any
OpenAI-compatible chat endpoint works (PYRA_LLM_BASE_URL, default Groq).

The model never gets the last word. Every sentence it writes is checked by
rule_problems() before anyone sees it, and on any problem (a number that is
not in the tool data, "safe"/"unsafe", a claim that microgravity results
apply to the Moon or Mars, no answer, a timeout) the scripted text is used
instead. ChatLLM never raises.

Keys are read from the environment or from a .env file at the project root
(git-ignored). Only tool results are sent to the model, never the user's
personal details.
"""

import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .. import paths
from ..assistant import APPLIES, HEDGED, OTHER_WORLDS, sentences
from .ctx import OfflineLLM

ENV_FILE = paths.ROOT / ".env"
DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"
NUMBER = re.compile(r"(?<![\w.])-?\d[\d,]*(?:\.\d+)?")
THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_env_loaded = False


def load_env(path=None):
    """Minimal KEY=VALUE reader. Variables already set in the environment win."""
    global _env_loaded
    if _env_loaded and path is None:
        return
    _env_loaded = True
    try:
        lines = (path or ENV_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def numbers_in(value, out=None):
    """Every number in a payload, including numbers written inside strings."""
    out = [] if out is None else out
    if isinstance(value, bool):
        return out
    if isinstance(value, (int, float)):
        out.append(float(value))
    elif isinstance(value, str):
        for found in NUMBER.findall(value):
            try:
                out.append(float(found.replace(",", "")))
            except ValueError:
                pass
    elif isinstance(value, dict):
        for item in value.values():
            numbers_in(item, out)
    elif isinstance(value, (list, tuple)):
        for item in value:
            numbers_in(item, out)
    return out


def rule_problems(text, *sources):
    """PYRA's rules applied to one piece of model text. [] means it may be shown."""
    problems = []
    known = []
    for source in sources:
        numbers_in(source, known)
    for found in NUMBER.findall(text or ""):
        value = abs(float(found.replace(",", "")))
        if value <= 10 or (1900 <= value <= 2100 and value == int(value)):
            continue  # small counts and years
        if not any(abs(value - abs(k)) <= max(0.051, 0.012 * abs(k)) for k in known):
            problems.append(f"number {found} is not in the tool data")
    for word in sorted({w.lower() for w in re.findall(r"\b(?:un)?safe\b", text or "", re.I)}):
        problems.append(f"uses the word '{word}'")
    for sentence in sentences(text or ""):
        if OTHER_WORLDS.search(sentence) and APPLIES.search(sentence) and not HEDGED.search(sentence):
            problems.append("says microgravity results apply to the Moon or Mars")
    if re.search(r"\b(will|would) (ignite|burn|catch fire)\b", text or "", re.I):
        problems.append("predicts a fire (PYRA does not predict fires)")
    return problems


def clean(text):
    text = THINK.sub("", str(text or ""))
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    for a, b in ((" ", " "), (" ", " "), ("‑", "-"), ("–", "-"), ("—", " - "),
                 ("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), ("**", "")):
        text = text.replace(a, b)
    # gpt-oss cites as 【S1】 or 【S1†L3-L5】; PYRA's checks and UI expect [S1].
    text = CJK_CITE.sub(lambda m: "[" + re.sub(r"\s*[,;]\s*", ", ", m.group(1)) + "]", text)
    return text.strip()


CJK_CITE = re.compile(r"【\s*(S\d+(?:\s*[,;]\s*S\d+)*)[^】]*】")


def first_json_object(text):
    start = text.find("{")
    while start != -1:
        try:
            value, _ = json.JSONDecoder().raw_decode(text[start:])
            if isinstance(value, dict):
                return value
        except ValueError:
            pass
        start = text.find("{", start + 1)
    return None


class ChatLLM:
    """An OpenAI-compatible chat model with OfflineLLM's methods and safe fallbacks.

    A call slower than PYRA_LLM_TIMEOUT seconds (default 8) is abandoned. After
    PYRA_LLM_BUDGET seconds of waiting in one run (default 45), or 3 failures
    in a row, the rest of the run is scripted. The numbers never depend on it.
    """
    live = True

    def __init__(self, api_key, model=None, base_url=None, post=None):
        self.api_key = api_key
        self.model = model or os.getenv("PYRA_LLM_MODEL", DEFAULT_MODEL)
        self.base_url = (base_url or os.getenv("PYRA_LLM_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.name = f"{self.model} (checked against PYRA rules)"
        self.timeout = float(os.getenv("PYRA_LLM_TIMEOUT", "8") or 8)
        self.budget = float(os.getenv("PYRA_LLM_BUDGET", "45") or 45)
        self.max_chars = int(os.getenv("PYRA_LLM_MAX_CHARS", "2500") or 2500)
        self.post = post or self._post
        self.spent = 0.0
        self.fails_in_row = 0
        self.calls = 0
        self.rejected = []

    def fresh(self):
        """A copy with its own time budget, for one run."""
        return ChatLLM(self.api_key, self.model, self.base_url, self.post)

    def _post(self, body):
        request = Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode("utf-8"),
                          headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}",
                                   "User-Agent": "pyra-agents"})
        with urlopen(request, timeout=self.timeout) as response:
            return json.loads(response.read())

    def _ask(self, system, payload):
        if self.spent >= self.budget or self.fails_in_row >= 3:
            raise TimeoutError("model budget used up; scripted text from here on")
        user = payload if isinstance(payload, str) else json.dumps(payload, default=str, separators=(",", ":"))
        body = {"model": self.model, "temperature": 0.2, "max_tokens": 500,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user[:self.max_chars]}]}
        started = time.time()
        try:
            out = self.post(body)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            self.fails_in_row += 1
            raise
        finally:
            self.spent += time.time() - started
        self.calls += 1
        self.fails_in_row = 0
        return clean(out["choices"][0]["message"]["content"])

    def chat(self, system, user, max_tokens=900, timeout=None):
        """One plain chat call for the research assistant. Raises on failure; no run budget."""
        body = {"model": self.model, "temperature": 0.2, "max_tokens": max_tokens,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": str(user)[:16000]}]}
        if self.post is not self._post:
            out = self.post(body)
        else:
            request = Request(f"{self.base_url}/chat/completions", data=json.dumps(body).encode("utf-8"),
                              headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}",
                                       "User-Agent": "pyra-assistant"})
            with urlopen(request, timeout=timeout or max(self.timeout, 30)) as response:
                out = json.loads(response.read())
        return clean(out["choices"][0]["message"]["content"])

    def think(self, agent, system, payload, fallback):
        prompt = (f"{system}\nYou are the '{agent}' agent of PYRA, which shows what NASA microgravity combustion "
                  "data covers and where it stops. Answer in 1-3 short plain sentences, no markdown. Use only "
                  "numbers that appear in the data. Never call anything safe or unsafe. Never say microgravity "
                  "results apply to the Moon or Mars; say 'bounded by' or 'not directly measured'. Do not "
                  "predict fires.")
        try:
            text = self._ask(prompt, payload)
        except Exception:  # noqa: BLE001  any failure means the scripted text
            return fallback
        problems = rule_problems(text, payload, fallback) if text else ["empty answer"]
        if problems:
            self.rejected.append({"agent": agent, "problems": problems})
            return fallback
        return text

    def choose(self, agent, question, options, payload, fallback=0):
        if not options:
            return fallback
        listing = "\n".join(f"{i + 1}. {o}" for i, o in enumerate(options))
        try:
            text = self._ask(f"You are the '{agent}' agent of PYRA. {question}\nOptions:\n{listing}\n"
                             "Reply with the option number only.", payload)
        except Exception:  # noqa: BLE001
            return fallback
        found = re.search(r"\d+", text)
        pick = int(found.group()) - 1 if found else -1
        return pick if 0 <= pick < len(options) else fallback

    def json(self, agent, system, payload, fallback):
        try:
            text = self._ask(f"{system}\nYou are the '{agent}' agent of PYRA. Reply with one JSON object "
                             f"only, using these keys: {list(fallback)}.", payload)
        except Exception:  # noqa: BLE001
            return dict(fallback)
        found = first_json_object(text)
        return {**fallback, **found} if found else dict(fallback)


def get_llm(force_offline=False):
    load_env()
    key = os.getenv("PYRA_LLM_API_KEY") or os.getenv("GROQ_API_KEY")
    if force_offline or os.getenv("PYRA_AGENTS_OFFLINE", "0") == "1" or not key:
        return OfflineLLM()
    return ChatLLM(key)
