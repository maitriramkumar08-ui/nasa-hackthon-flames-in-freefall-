"""Model-ready export of test runs as CSV, JSON or XLSX (Prompt 10).

One row per test run, with the original value and unit next to the
normalized one (rule 4). A missing value is an empty cell, never 0, and the
row's is_missing flag is true when any of O2, pressure, flow or gravity is
missing. Columns the database has no field for (outcome_name, outcome_unit,
uncertainty) stay empty instead of being guessed.

The XLSX writer uses only zipfile and hand-written XML, so no extra package
is needed. It holds two sheets: the data and a README.
"""

import csv
import io
import json
import zipfile
from xml.sax.saxutils import escape

COLUMNS = [
    "investigation", "test_id", "fuel_phase", "material", "geometry", "dimension_original",
    "o2_percent", "pressure_original", "pressure_unit_original", "pressure_kpa",
    "flow_original", "flow_unit_original", "flow_cm_s", "gravity_g", "hardware", "scale",
    "sensor", "outcome_name", "outcome_value", "outcome_unit", "uncertainty", "is_missing",
    "source", "page_or_table",
]

# Quantities whose absence makes a row count as missing.
CORE = ["o2_percent", "pressure", "flow_speed", "gravity"]

README = [
    ("investigation", "Investigation acronym."),
    ("test_id", "Run name as used in the paper."),
    ("fuel_phase", "Fuel phases reported for the investigation, joined with '; '. Not linked to the single run."),
    ("material", "Fuel materials reported for the investigation, joined with '; '."),
    ("geometry", "Fuel geometries reported for the investigation, joined with '; '."),
    ("dimension_original", "Fuel dimensions as written in the source."),
    ("o2_percent", "Oxygen, % (normalized)."),
    ("pressure_original", "Pressure as written in the source."),
    ("pressure_unit_original", "Unit of pressure_original."),
    ("pressure_kpa", "Pressure converted to kPa by PYRA (DERIVED)."),
    ("flow_original", "Flow speed as written in the source."),
    ("flow_unit_original", "Unit of flow_original."),
    ("flow_cm_s", "Flow speed converted to cm/s by PYRA (DERIVED)."),
    ("gravity_g", "Gravity in g. When the source gave words such as 'microgravity', the number is "
                  "PYRA's own mapping (DERIVED), not a measured value."),
    ("hardware", "Hardware name."),
    ("scale", "Test scale."),
    ("sensor", "Sensors reported for the investigation, joined with '; '."),
    ("outcome_name", "Always empty: the database does not name outcomes separately."),
    ("outcome_value", "Run outcome as written in the source."),
    ("outcome_unit", "Always empty: the database has no outcome unit."),
    ("uncertainty", "Always empty: the database has no uncertainty field."),
    ("is_missing", "Per row: true when any of O2, pressure, flow or gravity is not given for the run."),
    ("source", "Publication title for the run."),
    ("page_or_table", "Page or table of the run in the source."),
    ("limitations", "Missing values are empty cells, never 0. Values are MEASURED unless marked DERIVED "
                    "above. Rows from different hardware, scale, fuel phase or sensors are not directly "
                    "comparable. Microgravity runs do not directly measure Moon or Mars conditions."),
]


def _joined(values):
    return "; ".join(dict.fromkeys(v for v in values if v))


def _blank(value):
    return "" if value is None else value


def _row(run, inv):
    original = run["original"]
    values = run["values"]
    pressure = original["pressure"] or {}
    flow = original["flow_speed"] or {}
    return {
        "investigation": run["acronym"],
        "test_id": run["run_id"],
        "fuel_phase": _joined(f["phase"] for f in inv["fuels"]),
        "material": _joined(run["materials"]),
        "geometry": _joined(f["geometry"] for f in inv["fuels"]),
        "dimension_original": _joined(f["dimensions"] for f in inv["fuels"]),
        "o2_percent": _blank(values["o2_percent"]),
        "pressure_original": _blank(pressure.get("value")),
        "pressure_unit_original": _blank(pressure.get("unit")),
        "pressure_kpa": _blank(values["pressure"]),
        "flow_original": _blank(flow.get("value")),
        "flow_unit_original": _blank(flow.get("unit")),
        "flow_cm_s": _blank(values["flow_speed"]),
        "gravity_g": _blank(values["gravity"]),
        "hardware": _blank(run["hardware"]),
        "scale": _blank(run["scale"]),
        "sensor": _joined(inv["sensors"]),
        "outcome_name": "",
        "outcome_value": _blank(run["outcome"]),
        "outcome_unit": "",
        "uncertainty": "",
        "is_missing": any(values[q] is None for q in CORE),
        "source": _blank(run["source"]["title"]),
        "page_or_table": _blank(run["page_or_table"]),
    }


def rows(corpus, acronyms=None):
    """Export rows for every run, or only the runs of the given investigations."""
    by_id = {inv["id"]: inv for inv in corpus["investigations"]}
    if acronyms is not None:
        known = {inv["acronym"] for inv in corpus["investigations"]}
        unknown = [a for a in acronyms if a not in known]
        if unknown:
            raise ValueError(f"no investigation with acronym {', '.join(unknown)} in the corpus")
    return [_row(run, by_id[run["investigation_id"]]) for run in corpus["runs"]
            if acronyms is None or run["acronym"] in acronyms]


def to_csv(export_rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in export_rows:
        writer.writerow(dict(row, is_missing="true" if row["is_missing"] else "false"))
    return out.getvalue()


def to_json(export_rows):
    return json.dumps(export_rows, indent=2, ensure_ascii=False)


def _column(index):
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def _cell(ref, value):
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}"><v>{value}</v></c>'
    if value == "":
        return ""
    return f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>'


def _sheet(lines):
    body = []
    for number, line in enumerate(lines, start=1):
        cells = "".join(_cell(f"{_column(i)}{number}", v) for i, v in enumerate(line))
        body.append(f'<row r="{number}">{cells}</row>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(body)}</sheetData></worksheet>')


PARTS = {
    "[Content_Types].xml":
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '<Override PartName="/xl/worksheets/sheet2.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        '</Types>',
    "_rels/.rels":
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="xl/workbook.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>'
        '</Relationships>',
    "xl/workbook.xml":
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheets><sheet name="data" sheetId="1" r:id="rId1"/>'
        '<sheet name="README" sheetId="2" r:id="rId2"/></sheets></workbook>',
    "xl/_rels/workbook.xml.rels":
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Target="worksheets/sheet1.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        '<Relationship Id="rId2" Target="worksheets/sheet2.xml" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>'
        '</Relationships>',
}


def to_xlsx(export_rows, path):
    """Write a two-sheet workbook (data, README) to path."""
    data = [COLUMNS] + [[row[c] for c in COLUMNS] for row in export_rows]
    readme = [["column or note", "meaning"]] + [list(line) for line in README]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as book:
        for name, xml in PARTS.items():
            book.writestr(name, xml)
        book.writestr("xl/worksheets/sheet1.xml", _sheet(data))
        book.writestr("xl/worksheets/sheet2.xml", _sheet(readme))
    return path
