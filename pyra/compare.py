"""Put two or three investigations side by side (Prompt 6).

Every row is text taken from the database, so the cells are what the sources
report. The comparability verdict and the "can / cannot conclude" lists are
ours: fixed rules and fixed sentences, labelled DERIVED. Rule 7 is the reason
this file exists: numbers from different hardware, scale, fuel phase or
sensors are not put next to each other without a warning.

    table = compare.compare(corpus, ["BASS", "SAFFIRE"])
"""

NOT_PROVIDED = "not provided"

RANGES = [
    ("O2 range", "o2_percent", "%"),
    ("pressure range", "pressure", "kPa"),
    ("flow range", "flow_speed", "cm/s"),
    ("gravity", "gravity", "g"),
]
RANGE_ROWS = {name for name, _, _ in RANGES}

# The rows the verdict checks, and how each difference is worded.
CHECKS = [
    ("hardware", "they use different hardware"),
    ("scale", "they were run at different scales"),
    ("fuel phase", "they burn fuel in different phases"),
    ("sensors", "they measure outcomes with different sensors, so the outcome definitions may not match"),
]


def _listed(values):
    values = [v for v in values if v]
    return "; ".join(dict.fromkeys(values)) if values else NOT_PROVIDED


def _number(value):
    return f"{value:g}"


def _range(inv, quantity, unit):
    found = inv["ranges"].get(quantity)
    if not found:
        return NOT_PROVIDED
    low, high = found["min"], found["max"]
    span = _number(low) if low == high else f"{_number(low)} to {_number(high)}"
    originals = [f"{o['value']}{' ' + o['unit'] if o['unit'] else ''}"
                 + (f" ({o['page']})" if o["page"] else "") for o in found["original"]]
    text = f"{span} {unit}; original: {', '.join(originals)}"
    if found["from_words"]:
        text += "; number DERIVED by PYRA from the words"
    return text


def _findings(inv):
    measured = [f"{f['text']} ({f['page_or_table'] or 'page not given'})"
                for f in inv["findings"] if f["type"] == "MEASURED"]
    return _listed(measured)


def _papers(inv):
    return _listed(p["title"] + (f" <{p['url']}>" if p["url"] else "") for p in inv["publications"])


def _cells(inv):
    """{row name: display text} for one investigation, in table order."""
    cells = {
        "objective": inv["objective"] or NOT_PROVIDED,
        "fuel phase": _listed(f["phase"] for f in inv["fuels"]),
        "fuel geometry": _listed(f["geometry"] for f in inv["fuels"]),
        "hardware": inv["hardware"] or NOT_PROVIDED,
        "scale": inv["scale"] or NOT_PROVIDED,
    }
    for name, quantity, unit in RANGES:
        cells[name] = _range(inv, quantity, unit)
    cells.update({
        "sensors": _listed(inv["sensors"]),
        "variables varied": _listed(inv["notes"].get("variable_varied", [])),
        "variables held constant": _listed(inv["notes"].get("variable_held_constant", [])),
        "key measured findings": _findings(inv),
        "limitations": _listed(inv["notes"].get("limitation", [])),
        "linked papers": _papers(inv),
    })
    return cells


def _pick(corpus, acronyms):
    if not 2 <= len(acronyms) <= 3:
        raise ValueError(f"compare needs 2 or 3 investigations, got {len(acronyms)}: {list(acronyms)}")
    by_acronym = {inv["acronym"]: inv for inv in corpus["investigations"]}
    unknown = [a for a in acronyms if a not in by_acronym]
    if unknown:
        raise ValueError(f"no investigation with acronym {', '.join(unknown)} in the corpus")
    if len(set(acronyms)) != len(acronyms):
        raise ValueError(f"the same investigation is listed twice: {list(acronyms)}")
    return [by_acronym[a] for a in acronyms]


def _verdict(rows, acronyms):
    by_field = {row["field"]: row for row in rows}
    reasons = []
    for field, wording in CHECKS:
        values = by_field[field]["values"]
        if NOT_PROVIDED in values:
            missing = [a for a, v in zip(acronyms, values) if v == NOT_PROVIDED]
            reasons.append(f"NOT DIRECTLY COMPARABLE: {field} is not provided for {', '.join(missing)}, "
                           f"so we cannot check it matches")
        elif not by_field[field]["same"]:
            reasons.append(f"NOT DIRECTLY COMPARABLE: {wording} "
                           f"({'; '.join(f'{a}: {v}' for a, v in zip(acronyms, values))})")
    return {"comparable": not reasons, "reasons": reasons}


def _conclusions(rows, verdict, acronyms):
    names = " and ".join(acronyms)
    can = [f"Each cell shows what the cited sources for {names} report (MEASURED)."]
    covered = [row["field"] for row in rows
               if row["field"] in RANGE_ROWS and NOT_PROVIDED not in row["values"]]
    if covered:
        can.append(f"The reported test conditions can be read side by side for: {', '.join(covered)}.")
    cannot = ["Nothing here says a material or design is safe or unsafe.",
              "Microgravity results do not directly measure Moon or Mars conditions."]
    if verdict["comparable"]:
        can.append(f"Hardware, scale, fuel phase and sensors match, so measured outcomes of {names} "
                   f"can be compared with care.")
    else:
        cannot.append(f"Measured outcome numbers of {names} cannot be compared directly; "
                      f"see the reasons in the verdict.")
    for row in rows:
        if row["field"] in RANGE_ROWS and NOT_PROVIDED in row["values"]:
            cannot.append(f"The {row['field']} cannot be compared because it is not provided for every investigation.")
    return can, cannot


def compare(corpus, acronyms):
    """Side-by-side table, comparability verdict and conclusion lists for 2 or 3 investigations."""
    investigations = _pick(corpus, list(acronyms))
    cells = [_cells(inv) for inv in investigations]
    rows = []
    for field in cells[0]:
        values = [c[field] for c in cells]
        rows.append({"field": field, "values": values, "same": len(set(values)) == 1})
    acronyms = [inv["acronym"] for inv in investigations]
    verdict = _verdict(rows, acronyms)
    can, cannot = _conclusions(rows, verdict, acronyms)
    return {"investigations": acronyms, "rows": rows, "verdict": verdict,
            "can_conclude": can, "cannot_conclude": cannot, "label": "DERIVED"}


def summary_context(comparison):
    """The displayed rows as numbered text blocks, so an optional LLM summary can cite only them."""
    acronyms = comparison["investigations"]
    blocks = []
    for number, row in enumerate(comparison["rows"], start=1):
        cells = "; ".join(f"{a}: {v}" for a, v in zip(acronyms, row["values"]))
        blocks.append({"id": f"C{number}",
                       "text": f"{row['field']} ({'same' if row['same'] else 'different'}): {cells}"})
    verdict = comparison["verdict"]
    blocks.append({"id": "V1", "text": "verdict (DERIVED): "
                   + ("directly comparable" if verdict["comparable"] else " ".join(verdict["reasons"]))})
    return blocks
