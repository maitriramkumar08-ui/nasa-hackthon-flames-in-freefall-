import csv

# a source only counts as checked once these are filled in
REQUIRED = ["url", "access_date", "verified_by"]


def missing_fields(row):
    return [col for col in REQUIRED if not (row.get(col) or "").strip()]


def check_sources(csv_path):
    problems = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            missing = missing_fields(row)
            if missing:
                problems.append(f"{row['id']} ({row['investigation']}): missing {', '.join(missing)}")
    return problems
