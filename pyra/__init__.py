"""PYRA Phase 1: the data foundation.

The modules, in the order data flows through them:

    units.py      unit conversion (psi -> kPa, m/s -> cm/s, C -> K, ...)
    factsheet.py  checks one fact sheet (Prompt 1 JSON) before it is loaded
    schema.sql    the database tables
    db.py         opens / creates the SQLite file
    loader.py     puts checked fact sheets into the database
    quality.py    data-quality checks on the finished database
    cli.py        the commands you run: build, check, validate, spotcheck
"""
