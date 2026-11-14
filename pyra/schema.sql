-- PYRA database (SQLite). Built fresh from the fact sheets every time, so never edit it by hand.
--
-- How it fits together:
--   investigation  1 --- many  publications   (one fact sheet = one publication)
--   publication    1 --- many  fuels, sensors, findings, notes, condition sets
--   condition set  1 --- many  measurements   (the numbers: O2, pressure, flow, gravity, temperature)
--   test run       1 --- 1     condition set  (only for the investigations the demo needs)
--
-- Rule 4: every measurement keeps original_value + original_unit. Converted values go in
-- normalized_value + normalized_unit. Missing stays NULL with is_missing = 1, never 0.
-- Every row that holds a fact points at the publication it came from (publication_id).

CREATE TABLE hardware (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE              -- e.g. the MSG flow duct, ACME in CIR
);

CREATE TABLE investigations (
    id             INTEGER PRIMARY KEY,
    acronym        TEXT NOT NULL UNIQUE,
    name           TEXT NOT NULL,
    psi_id         TEXT,
    pillar         TEXT NOT NULL,           -- prevention | detection | suppression | supporting | unknown
    evidence_class TEXT,                    -- direct | supporting | background, NULL until the team decides
    scale          TEXT NOT NULL,           -- bench | spacecraft-scale | unknown
    platform       TEXT,
    objective      TEXT,
    hardware_id    INTEGER REFERENCES hardware(id)
);

CREATE TABLE publications (
    id               INTEGER PRIMARY KEY,
    investigation_id INTEGER NOT NULL REFERENCES investigations(id),
    title            TEXT NOT NULL,
    url              TEXT,
    ntrs_id          TEXT,
    factsheet_file   TEXT NOT NULL,         -- which JSON file this came from
    extracted_by     TEXT,
    checked_by       TEXT
);

CREATE TABLE fuels (                        -- one row per material named in the sheet
    id               INTEGER PRIMARY KEY,
    investigation_id INTEGER NOT NULL REFERENCES investigations(id),
    publication_id   INTEGER NOT NULL REFERENCES publications(id),
    phase            TEXT NOT NULL,         -- solid | liquid | gas | aerosol | unknown
    material         TEXT,
    geometry         TEXT,
    dimensions       TEXT
);

CREATE TABLE sensors (
    id               INTEGER PRIMARY KEY,
    investigation_id INTEGER NOT NULL REFERENCES investigations(id),
    publication_id   INTEGER NOT NULL REFERENCES publications(id),
    description      TEXT NOT NULL
);

CREATE TABLE findings (
    id               INTEGER PRIMARY KEY,
    investigation_id INTEGER NOT NULL REFERENCES investigations(id),
    publication_id   INTEGER NOT NULL REFERENCES publications(id),
    text             TEXT NOT NULL,
    page_or_table    TEXT,
    type             TEXT NOT NULL          -- MEASURED | AUTHOR_INTERPRETATION
);

CREATE TABLE notes (                        -- the plain lists of text in a fact sheet
    id               INTEGER PRIMARY KEY,
    investigation_id INTEGER NOT NULL REFERENCES investigations(id),
    publication_id   INTEGER NOT NULL REFERENCES publications(id),
    kind             TEXT NOT NULL,         -- limitation | missing_information | variable_varied | variable_held_constant
    text             TEXT NOT NULL
);

CREATE TABLE test_runs (
    id               INTEGER PRIMARY KEY,
    investigation_id INTEGER NOT NULL REFERENCES investigations(id),
    publication_id   INTEGER NOT NULL REFERENCES publications(id),
    run_id           TEXT NOT NULL,         -- the run name used in the paper
    experiment       TEXT,                  -- sub-experiment, if the paper groups runs
    outcome          TEXT,
    page_or_table    TEXT
);

CREATE TABLE conditions (                   -- a set of conditions: a sheet's reported range, or one test run
    id                     INTEGER PRIMARY KEY,
    investigation_id       INTEGER NOT NULL REFERENCES investigations(id),
    publication_id         INTEGER NOT NULL REFERENCES publications(id),
    test_run_id            INTEGER REFERENCES test_runs(id),   -- NULL = the reported range for the whole sheet
    flow_direction         TEXT,
    diluent_or_suppressant TEXT,
    concentration          TEXT
);

CREATE TABLE measurements (
    id                INTEGER PRIMARY KEY,
    condition_id      INTEGER NOT NULL REFERENCES conditions(id),
    source_id         INTEGER NOT NULL REFERENCES publications(id),
    quantity          TEXT NOT NULL,        -- o2_percent | pressure | flow_speed | gravity | temperature
    bound             TEXT NOT NULL,        -- min | max | value
    original_value,                         -- no type on purpose: a number, or text like 'microgravity'
    original_unit     TEXT,
    normalized_value  REAL,
    normalized_unit   TEXT,
    conversion_method TEXT NOT NULL,
    page_or_table     TEXT,
    is_missing        INTEGER NOT NULL      -- 1 when the source doesn't give this value
);
