"""Data-quality checks on the finished database.

Each check is one SQL query plus the message to show for each row it finds.
To add a check, add one entry to CHECKS.
"""

CHECKS = [
    ("O2 outside 0-100 %",
     """SELECT i.acronym, m.original_value, m.original_unit, m.page_or_table
        FROM measurements m JOIN conditions c ON c.id = m.condition_id
        JOIN investigations i ON i.id = c.investigation_id
        WHERE m.quantity = 'o2_percent' AND (m.normalized_value < 0 OR m.normalized_value > 100)""",
     "{acronym}: O2 of {original_value} {original_unit} (page {page_or_table})"),

    ("Negative pressure",
     """SELECT i.acronym, m.original_value, m.original_unit, m.page_or_table
        FROM measurements m JOIN conditions c ON c.id = m.condition_id
        JOIN investigations i ON i.id = c.investigation_id
        WHERE m.quantity = 'pressure' AND m.normalized_value < 0""",
     "{acronym}: pressure of {original_value} {original_unit} (page {page_or_table})"),

    ("Number given but not converted",
     """SELECT i.acronym, m.quantity, m.original_value, m.original_unit, m.conversion_method
        FROM measurements m JOIN conditions c ON c.id = m.condition_id
        JOIN investigations i ON i.id = c.investigation_id
        WHERE m.is_missing = 0 AND m.normalized_value IS NULL
          AND m.conversion_method != 'not a number, kept as text only'""",
     "{acronym}: {quantity} = {original_value} {original_unit} ({conversion_method})"),

    ("Publication without a source link",
     """SELECT p.factsheet_file, p.title FROM publications p
        WHERE COALESCE(TRIM(p.url), '') = '' AND COALESCE(TRIM(p.ntrs_id), '') = ''""",
     "{factsheet_file}: {title!r} has no url or ntrs_id"),

    ("Same paper loaded twice",
     """SELECT COALESCE(NULLIF(ntrs_id, ''), url) AS paper, GROUP_CONCAT(factsheet_file, ', ') AS files
        FROM publications GROUP BY paper HAVING COUNT(*) > 1""",
     "{paper} appears in {files}"),

    ("Same finding twice",
     """SELECT i.acronym, f.text FROM findings f JOIN investigations i ON i.id = f.investigation_id
        GROUP BY f.investigation_id, LOWER(TRIM(f.text)) HAVING COUNT(*) > 1""",
     "{acronym}: {text!r}"),

    ("Investigation with no O2, pressure or flow at all",
     """SELECT i.acronym FROM investigations i
        WHERE NOT EXISTS (
            SELECT 1 FROM measurements m JOIN conditions c ON c.id = m.condition_id
            WHERE c.investigation_id = i.id AND m.is_missing = 0
              AND m.quantity IN ('o2_percent', 'pressure', 'flow_speed'))""",
     "{acronym}: Phase 1 needs at least one of these from a source"),
]


def run_checks(conn):
    """Returns {check name: [problem, ...]} with an entry for every check."""
    results = {}
    for name, sql, message in CHECKS:
        rows = conn.execute(sql).fetchall()
        results[name] = [message.format(**dict(row)) for row in rows]
    return results


def spot_check_rows(conn, how_many=10):
    """A random handful of numbers, with their source, for a person to check by hand."""
    return conn.execute(
        """SELECT i.acronym, m.quantity, m.bound, m.original_value, m.original_unit,
                  m.page_or_table, p.title, COALESCE(p.url, p.ntrs_id) AS link
           FROM measurements m
           JOIN publications p ON p.id = m.source_id
           JOIN conditions c ON c.id = m.condition_id
           JOIN investigations i ON i.id = c.investigation_id
           WHERE m.is_missing = 0
           ORDER BY RANDOM() LIMIT ?""", (how_many,)).fetchall()
