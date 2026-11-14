"""Put checked fact sheets into the database.

Each sheet is checked first (factsheet.py). Sheets with errors are rejected and
nothing from them is stored. Several sheets can describe the same investigation
(one per paper): they share one investigations row, matched by acronym.
"""

import json
from pathlib import Path

from . import units
from .factsheet import RANGES, RUN_VALUES, SINGLE_VALUES, check_factsheet

NOTE_LISTS = {
    "limitations": "limitation",
    "missing_information": "missing_information",
    "variables_varied": "variable_varied",
    "variables_held_constant": "variable_held_constant",
}


def insert(conn, table, **values):
    """INSERT one row and return its id."""
    columns = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    cursor = conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", list(values.values()))
    return cursor.lastrowid


def hardware_id(conn, name):
    if not name:
        return None
    row = conn.execute("SELECT id FROM hardware WHERE name = ?", (name,)).fetchone()
    return row["id"] if row else insert(conn, "hardware", name=name)


def investigation_id(conn, sheet, warnings):
    """Find the investigation by acronym, or create it from this sheet."""
    row = conn.execute("SELECT * FROM investigations WHERE acronym = ?",
                       (sheet["acronym"],)).fetchone()
    if row is None:
        return insert(conn, "investigations",
                      acronym=sheet["acronym"], name=sheet["investigation_name"],
                      psi_id=sheet.get("psi_id"), pillar=sheet["pillar"],
                      evidence_class=sheet.get("evidence_class"), scale=sheet["scale"],
                      platform=sheet.get("platform"), objective=sheet.get("objective"),
                      hardware_id=hardware_id(conn, sheet.get("hardware")))

    # An earlier sheet already created it. Don't overwrite, but say if they disagree.
    for field in ["pillar", "scale"]:
        if sheet[field] != row[field]:
            warnings.append(f"{field} is {sheet[field]!r} here but {row[field]!r} "
                            f"in an earlier sheet for {sheet['acronym']}; kept the earlier one")
    return row["id"]


def add_measurement(conn, ids, condition_id, quantity, bound, value, unit, page):
    kind = RUN_VALUES[quantity]   # RUN_VALUES lists every quantity we measure
    normalized, normalized_unit, method = units.normalize(value, unit, kind)
    insert(conn, "measurements",
           condition_id=condition_id, source_id=ids["publication"],
           quantity=quantity, bound=bound,
           original_value=value, original_unit=unit,
           normalized_value=normalized, normalized_unit=normalized_unit,
           conversion_method=method, page_or_table=page,
           is_missing=1 if value is None else 0)


def add_condition_set(conn, ids, test_run_id=None, flow_direction=None,
                      diluent=None, concentration=None):
    return insert(conn, "conditions",
                  investigation_id=ids["investigation"], publication_id=ids["publication"],
                  test_run_id=test_run_id, flow_direction=flow_direction,
                  diluent_or_suppressant=diluent, concentration=concentration)


def add_reported_conditions(conn, ids, conditions):
    """The ranges the paper reports for the whole investigation."""
    flow = conditions.get("flow_speed") or {}
    diluent = conditions.get("diluent_or_suppressant") or {}
    condition_id = add_condition_set(conn, ids, flow_direction=flow.get("direction"),
                                     diluent=diluent.get("type"),
                                     concentration=diluent.get("concentration"))
    for name in RANGES:
        item = conditions.get(name) or {}
        for bound in ["min", "max"]:
            add_measurement(conn, ids, condition_id, name, bound,
                            item.get(bound), item.get("unit"), item.get("page"))
    for name in SINGLE_VALUES:
        item = conditions.get(name) or {}
        add_measurement(conn, ids, condition_id, name, "value",
                        item.get("value"), item.get("unit"), item.get("page"))


def add_test_runs(conn, ids, runs):
    for run in runs:
        run_row = insert(conn, "test_runs",
                         investigation_id=ids["investigation"], publication_id=ids["publication"],
                         run_id=run["run_id"], experiment=run.get("experiment"),
                         outcome=run.get("outcome"), page_or_table=run.get("page_or_table"))
        condition_id = add_condition_set(conn, ids, test_run_id=run_row)
        for name in RUN_VALUES:
            item = run.get(name) or {}
            add_measurement(conn, ids, condition_id, name, "value",
                            item.get("value"), item.get("unit"), run.get("page_or_table"))


def add_lists(conn, ids, sheet):
    common = {"investigation_id": ids["investigation"], "publication_id": ids["publication"]}
    fuel = sheet["fuel"]
    for material in fuel.get("materials") or [None]:
        insert(conn, "fuels", **common, phase=fuel["phase"], material=material,
               geometry=fuel.get("geometry"), dimensions=fuel.get("dimensions"))
    for sensor in sheet.get("sensors_and_measurements") or []:
        insert(conn, "sensors", **common, description=sensor)
    for finding in sheet.get("key_findings") or []:
        insert(conn, "findings", **common, text=finding["text"],
               page_or_table=finding.get("page_or_table"), type=finding["type"])
    for field, kind in NOTE_LISTS.items():
        for text in sheet.get(field) or []:
            insert(conn, "notes", **common, kind=kind, text=text)


def load_sheet(conn, sheet, filename):
    """Load one sheet. Returns (errors, warnings); errors mean nothing was stored."""
    errors, warnings = check_factsheet(sheet)
    if errors:
        return errors, warnings

    with conn:  # one transaction: the whole sheet goes in, or none of it does
        ids = {"investigation": investigation_id(conn, sheet, warnings)}
        source, review = sheet["source"], sheet["_review"]
        ids["publication"] = insert(conn, "publications",
                                    investigation_id=ids["investigation"],
                                    title=source["title"], url=source.get("url"),
                                    ntrs_id=source.get("ntrs_id"), factsheet_file=filename,
                                    extracted_by=review["extracted_by"],
                                    checked_by=review["checked_by"])
        add_reported_conditions(conn, ids, sheet.get("conditions") or {})
        add_test_runs(conn, ids, sheet.get("test_runs") or [])
        add_lists(conn, ids, sheet)
    return errors, warnings


def read_sheet(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_folder(conn, folder):
    """Load every *.json in a folder. Returns {filename: (errors, warnings)}."""
    results = {}
    for path in sorted(Path(folder).glob("*.json")):
        try:
            results[path.name] = load_sheet(conn, read_sheet(path), path.name)
        except (ValueError, KeyError, TypeError, AttributeError) as problem:
            # bad JSON, or a field with the wrong shape (e.g. text where a {...} belongs)
            results[path.name] = ([f"could not read this sheet: {problem}"], [])
    return results
