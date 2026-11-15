import json

from . import paths, units

QUANTITIES = ["o2_percent", "pressure", "flow_speed", "gravity", "temperature"]

# Our own choice, not NASA data. Change it in one place if the team disagrees.
GRAVITY_WORDS = {
    "microgravity": 0.0,
    "micro-gravity": 0.0,
    "0 g": 0.0,
    "0g": 0.0,
    "normal gravity": 1.0,
    "1 g": 1.0,
    "1g": 1.0,
    "earth gravity": 1.0,
}

DECISIONS = paths.ROOT / "config" / "decisions.json"


def decisions():
    """config/decisions.json as {name: value}, without the why/confirmed_by notes."""
    raw = json.loads(DECISIONS.read_text(encoding="utf-8"))
    return {name: entry["value"] for name, entry in raw.items() if isinstance(entry, dict)}


def gravity_number(original_value, normalized_value):
    """(number, from_words). A number we were given wins over a word."""
    if normalized_value is not None:
        return normalized_value, False
    if isinstance(original_value, str) and original_value.strip().lower() in GRAVITY_WORDS:
        return GRAVITY_WORDS[original_value.strip().lower()], True
    return None, False


def _measurements(conn, condition_ids):
    """{condition_id: [measurement rows]}"""
    found = {cid: [] for cid in condition_ids}
    if not condition_ids:
        return found
    marks = ", ".join("?" for _ in condition_ids)
    for row in conn.execute(f"SELECT * FROM measurements WHERE condition_id IN ({marks})",
                            list(condition_ids)):
        found[row["condition_id"]].append(row)
    return found


def _value(rows, quantity, bound):
    for row in rows:
        if row["quantity"] == quantity and row["bound"] == bound:
            return row
    return None


def _number(row, quantity):
    """(number or None, from_words) for one measurement row."""
    if row is None or row["is_missing"]:
        return None, False
    if quantity == "gravity":
        return gravity_number(row["original_value"], row["normalized_value"])
    return row["normalized_value"], False


def _original(row):
    if row is None or row["is_missing"]:
        return None
    return {"value": row["original_value"], "unit": row["original_unit"],
            "page": row["page_or_table"], "source_id": row["source_id"]}


def _ranges(rows):
    """Reported ranges for one condition set: {quantity: {min, max, original, from_words}}"""
    ranges = {}
    for quantity in QUANTITIES:
        low, low_words = _number(_value(rows, quantity, "min"), quantity)
        high, high_words = _number(_value(rows, quantity, "max"), quantity)
        single, single_words = _number(_value(rows, quantity, "value"), quantity)
        if single is not None:
            low = single if low is None else low
            high = single if high is None else high
        if low is None and high is None:
            continue
        originals = [_original(_value(rows, quantity, b)) for b in ("min", "max", "value")]
        ranges[quantity] = {
            "min": low, "max": high,
            "from_words": low_words or high_words or single_words,
            "original": [o for o in originals if o],
        }
    return ranges


def _merge(into, more):
    """Widen ranges when several papers report the same investigation."""
    for quantity, found in more.items():
        if quantity not in into:
            into[quantity] = dict(found, original=list(found["original"]))
            continue
        have = into[quantity]
        for bound, pick in (("min", min), ("max", max)):
            values = [v for v in (have[bound], found[bound]) if v is not None]
            have[bound] = pick(values) if values else None
        have["from_words"] = have["from_words"] or found["from_words"]
        have["original"].extend(found["original"])


def load(conn):
    """The whole database as {"investigations": [...], "runs": [...]}."""
    publications = {row["id"]: dict(row) for row in conn.execute("SELECT * FROM publications")}
    hardware = {row["id"]: row["name"] for row in conn.execute("SELECT * FROM hardware")}

    investigations = {}
    for row in conn.execute("SELECT * FROM investigations ORDER BY acronym"):
        investigations[row["id"]] = {
            "id": row["id"], "acronym": row["acronym"], "name": row["name"],
            "psi_id": row["psi_id"], "pillar": row["pillar"],
            "evidence_class": row["evidence_class"], "scale": row["scale"],
            "platform": row["platform"], "objective": row["objective"],
            "hardware": hardware.get(row["hardware_id"]),
            "publications": [], "fuels": [], "sensors": [], "findings": [],
            "notes": {}, "ranges": {},
        }

    for pub in publications.values():
        investigations[pub["investigation_id"]]["publications"].append(
            {k: pub[k] for k in ("id", "title", "url", "ntrs_id")})
    for row in conn.execute("SELECT * FROM fuels"):
        investigations[row["investigation_id"]]["fuels"].append(
            {k: row[k] for k in ("phase", "material", "geometry", "dimensions")})
    for row in conn.execute("SELECT * FROM sensors"):
        investigations[row["investigation_id"]]["sensors"].append(row["description"])
    for row in conn.execute("SELECT * FROM findings"):
        investigations[row["investigation_id"]]["findings"].append(
            {"text": row["text"], "page_or_table": row["page_or_table"], "type": row["type"],
             "source_id": row["publication_id"]})
    for row in conn.execute("SELECT * FROM notes"):
        investigations[row["investigation_id"]]["notes"].setdefault(row["kind"], []).append(row["text"])

    conditions = list(conn.execute("SELECT * FROM conditions"))
    rows_by_condition = _measurements(conn, [c["id"] for c in conditions])
    run_conditions = {}
    for cond in conditions:
        if cond["test_run_id"] is None:
            _merge(investigations[cond["investigation_id"]]["ranges"], _ranges(rows_by_condition[cond["id"]]))
        else:
            run_conditions[cond["test_run_id"]] = cond

    runs = []
    for row in conn.execute("SELECT * FROM test_runs ORDER BY id"):
        inv = investigations[row["investigation_id"]]
        cond = run_conditions.get(row["id"])
        rows = rows_by_condition.get(cond["id"], []) if cond else []
        values, original, from_words = {}, {}, []
        for quantity in QUANTITIES:
            measured = _value(rows, quantity, "value")
            number, words = _number(measured, quantity)
            values[quantity] = number
            original[quantity] = _original(measured)
            if words:
                from_words.append(quantity)
        pub = publications[row["publication_id"]]
        runs.append({
            "id": row["id"], "run_id": row["run_id"], "experiment": row["experiment"],
            "outcome": row["outcome"], "page_or_table": row["page_or_table"],
            "investigation_id": inv["id"], "acronym": inv["acronym"],
            "hardware": inv["hardware"], "scale": inv["scale"], "pillar": inv["pillar"],
            "fuel_phases": sorted({f["phase"] for f in inv["fuels"]}),
            "materials": [f["material"] for f in inv["fuels"] if f["material"]],
            "source": {"publication_id": pub["id"], "title": pub["title"],
                       "url": pub["url"], "ntrs_id": pub["ntrs_id"]},
            "values": values, "original": original, "from_words": from_words,
            "flow_direction": cond["flow_direction"] if cond else None,
        })

    return {"investigations": list(investigations.values()), "runs": runs}


def scenario(raw):
    """Turn a user scenario into standard units. Everything in it is HYPOTHETICAL.

    raw = {"o2_percent": 34, "pressure": 8.2, "pressure_unit": "psi",
           "flow_speed": 10, "flow_unit": "cm/s", "gravity_g": 0.16,
           "material": "...", "fuel_phase": "solid", "pillar": "prevention",
           "scale": "bench", "outputs": ["flame spread"]}
    """
    def number(key, unit_key, kind, default_unit):
        value = units.to_number(raw.get(key))
        if value is None:
            return None
        return units.convert(value, raw.get(unit_key) or default_unit, units.STANDARD[kind])

    return {
        "o2_percent": units.to_number(raw.get("o2_percent")),
        "pressure": number("pressure", "pressure_unit", "pressure", "kPa"),
        "flow_speed": number("flow_speed", "flow_unit", "speed", "cm/s"),
        "gravity": units.to_number(raw.get("gravity_g")),
        "temperature": number("temperature", "temperature_unit", "temperature", "K"),
        "material": raw.get("material"),
        "fuel_phase": raw.get("fuel_phase"),
        "pillar": raw.get("pillar"),
        "scale": raw.get("scale"),
        "outputs": list(raw.get("outputs") or []),
        "label": "HYPOTHETICAL",
    }

