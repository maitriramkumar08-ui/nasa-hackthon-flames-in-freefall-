"""Check one fact sheet before it goes into the database.

A fact sheet is the JSON that Prompt 1 produces, plus two things we add by hand:
  "_review":        who extracted it, who checked it, did it pass Prompt 12
  "evidence_class": direct | supporting | background (optional)
and optionally "test_runs" for the one or two investigations the demo uses.
See data/factsheets/TEMPLATE.json.

check_factsheet(sheet) returns (errors, warnings):
  errors   -> the loader rejects the sheet
  warnings -> the sheet is loaded, but a person should look at it
"""

from . import units

PILLARS = {"prevention", "detection", "suppression", "supporting", "unknown"}
SCALES = {"bench", "spacecraft-scale", "unknown"}
FUEL_PHASES = {"solid", "liquid", "gas", "aerosol", "unknown"}
EVIDENCE_CLASSES = {"direct", "supporting", "background"}
FINDING_TYPES = {"MEASURED", "AUTHOR_INTERPRETATION"}

# condition name -> the kind of unit it must use (see units.STANDARD)
RANGES = {"o2_percent": "o2", "pressure": "pressure", "flow_speed": "speed"}
SINGLE_VALUES = {"gravity": "gravity", "temperature": "temperature"}
RUN_VALUES = {**RANGES, **SINGLE_VALUES}


def has_text(value):
    return isinstance(value, str) and value.strip() != ""


def is_number_or_none(value):
    return value is None or (isinstance(value, (int, float)) and not isinstance(value, bool))


def check_unit(where, value, unit, kind, warnings):
    """Warn when a value is given but its unit can't be converted."""
    if value is None:
        return
    _, _, method = units.normalize(value, unit, kind)
    if units.to_number(value) is not None and method.startswith("unit"):
        warnings.append(f"{where}: {method}, so the converted value stays empty")


def check_basics(sheet, errors):
    for field in ["investigation_name", "acronym"]:
        if not has_text(sheet.get(field)):
            errors.append(f"{field} is missing")
    if sheet.get("pillar") not in PILLARS:
        errors.append(f"pillar must be one of {sorted(PILLARS)}")
    if sheet.get("scale") not in SCALES:
        errors.append(f"scale must be one of {sorted(SCALES)}")
    if sheet.get("evidence_class") not in EVIDENCE_CLASSES | {None}:
        errors.append(f"evidence_class must be one of {sorted(EVIDENCE_CLASSES)} or null")
    fuel = sheet.get("fuel") or {}
    if fuel.get("phase") not in FUEL_PHASES:
        errors.append(f"fuel.phase must be one of {sorted(FUEL_PHASES)}")


def check_source(sheet, errors):
    """Rule 3: no source, no entry."""
    source = sheet.get("source") or {}
    if not has_text(source.get("title")):
        errors.append("source.title is missing")
    if not (has_text(source.get("url")) or has_text(source.get("ntrs_id"))):
        errors.append("source needs a url or an ntrs_id")


def check_review(sheet, errors):
    """Only sheets a second person has checked may enter the database."""
    review = sheet.get("_review") or {}
    if not has_text(review.get("extracted_by")):
        errors.append("_review.extracted_by is missing")
    if not has_text(review.get("checked_by")):
        errors.append("_review.checked_by is missing: a second person must check the sheet")
    if review.get("prompt12_passed") is not True:
        errors.append("_review.prompt12_passed must be true")


def check_conditions(sheet, errors, warnings):
    conditions = sheet.get("conditions") or {}
    for name, kind in RANGES.items():
        item = conditions.get(name) or {}
        low, high = item.get("min"), item.get("max")
        if not (is_number_or_none(low) and is_number_or_none(high)):
            errors.append(f"conditions.{name}: min and max must be numbers or null")
            continue
        if low is not None and high is not None and low > high:
            errors.append(f"conditions.{name}: min ({low}) is bigger than max ({high})")
        for value in (low, high):
            check_unit(f"conditions.{name}", value, item.get("unit"), kind, warnings)
        if (low is not None or high is not None) and not has_text(item.get("page")):
            warnings.append(f"conditions.{name}: no page given for these numbers")
    for name, kind in SINGLE_VALUES.items():
        item = conditions.get(name) or {}
        check_unit(f"conditions.{name}", item.get("value"), item.get("unit"), kind, warnings)


def check_findings(sheet, errors, warnings):
    for i, finding in enumerate(sheet.get("key_findings") or []):
        if not has_text(finding.get("text")):
            errors.append(f"key_findings[{i}]: text is missing")
        if finding.get("type") not in FINDING_TYPES:
            errors.append(f"key_findings[{i}]: type must be MEASURED or AUTHOR_INTERPRETATION")
        if not has_text(finding.get("page_or_table")):
            warnings.append(f"key_findings[{i}]: no page or table given")


def check_test_runs(sheet, errors, warnings):
    seen = set()
    for i, run in enumerate(sheet.get("test_runs") or []):
        run_id = run.get("run_id")
        if not has_text(run_id):
            errors.append(f"test_runs[{i}]: run_id is missing")
        elif run_id in seen:
            errors.append(f"test_runs[{i}]: run_id {run_id!r} is used twice")
        seen.add(run_id)
        if not has_text(run.get("page_or_table")):
            warnings.append(f"test_runs[{i}]: no page or table given")
        for name, kind in RUN_VALUES.items():
            item = run.get(name) or {}
            check_unit(f"test_runs[{i}].{name}", item.get("value"), item.get("unit"), kind, warnings)


def check_factsheet(sheet):
    if not isinstance(sheet, dict):
        return ["the file must contain one JSON object"], []
    errors, warnings = [], []
    check_basics(sheet, errors)
    check_source(sheet, errors)
    check_review(sheet, errors)
    check_conditions(sheet, errors, warnings)
    check_findings(sheet, errors, warnings)
    check_test_runs(sheet, errors, warnings)
    return errors, warnings
