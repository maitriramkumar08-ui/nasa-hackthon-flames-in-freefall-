"""The commands. Run from the project folder:

    python -m pyra build                 build data/pyra.db from data/factsheets/verified
    python -m pyra check                 run the data-quality checks on the database
    python -m pyra validate FILE...      check fact sheets without loading them (use on drafts)
    python -m pyra spotcheck             print 10 random numbers to check by hand against the paper
    python -m pyra serve                 start the web app on http://127.0.0.1:8000
"""

import argparse

from . import db, paths, quality
from .factsheet import check_factsheet
from .loader import load_folder, read_sheet


def show(label, items):
    for item in items:
        print(f"    {label}: {item}")


def cmd_build(args):
    folder, db_path = paths.VERIFIED, paths.DATABASE
    conn = db.create(db_path)
    results = load_folder(conn, folder)
    if not results:
        print(f"No fact sheets in {folder} yet. Put checked sheets there and run again.")
        return 0

    rejected = 0
    for filename, (errors, warnings) in results.items():
        print(f"  {'REJECTED' if errors else 'loaded  '} {filename}")
        show("error", errors)
        show("warning", warnings)
        rejected += bool(errors)
    print(f"\n{len(results) - rejected} sheet(s) loaded, {rejected} rejected -> {db_path}")
    return 1 if rejected else 0


def open_database(args):
    """The built database, or None (with a hint) if it hasn't been built yet."""
    db_path = paths.DATABASE
    if not db_path.exists():
        print(f"{db_path} doesn't exist yet. Run: python -m pyra build")
        return None
    return db.connect(db_path)


def cmd_check(args):
    conn = open_database(args)
    if conn is None:
        return 1
    results = quality.run_checks(conn)
    total = 0
    for name, problems in results.items():
        print(f"== {name} == {'ok' if not problems else ''}")
        show("problem", problems)
        total += len(problems)
    print(f"\n{total} data-quality problem(s).")
    return 1 if total else 0


def cmd_validate(args):
    bad = 0
    for path in args.files:
        errors, warnings = check_factsheet(read_sheet(path))
        print(f"  {'NOT READY' if errors else 'ready    '} {path}")
        show("error", errors)
        show("warning", warnings)
        bad += bool(errors)
    return 1 if bad else 0


def cmd_spotcheck(args):
    conn = open_database(args)
    if conn is None:
        return 1
    rows = quality.spot_check_rows(conn, args.n)
    print("Open each source and confirm the number, unit and page match.\n")
    for r in rows:
        print(f"  {r['acronym']}: {r['quantity']} {r['bound']} = {r['original_value']} "
              f"{r['original_unit'] or ''} (page {r['page_or_table']})\n"
              f"      {r['title']} -> {r['link']}")
    return 0


def cmd_serve(args):
    # Imported here so the data commands keep working without the web modules.
    from .server import serve
    serve(args.port, args.planner)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m pyra", description="PYRA data foundation")
    commands = parser.add_subparsers(dest="command", required=True)

    for name, func, help_text in [("build", cmd_build, "rebuild the database from fact sheets"),
                                  ("check", cmd_check, "run data-quality checks"),
                                  ("spotcheck", cmd_spotcheck, "print random numbers to verify")]:
        sub = commands.add_parser(name, help=help_text)
        sub.set_defaults(func=func)
    commands.choices["spotcheck"].add_argument("-n", type=int, default=10, help="how many rows")

    validate = commands.add_parser("validate", help="check fact sheets without loading them")
    validate.add_argument("files", nargs="+")
    validate.set_defaults(func=cmd_validate)

    serve = commands.add_parser("serve", help="start the web app")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--planner", default="auto", choices=("auto", "offline", "claude", "groq"))
    serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)
