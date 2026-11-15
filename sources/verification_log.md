# Source verification log

What was checked, how, and what came back. Rule 5 says a name goes in `verified_by`
only once a person has read the source themselves, so that column is still empty. This
log exists so that reading is a short confirmation instead of a search.

Checks dated 2026-11-15.

## What "checked" means here

Three things were checked mechanically, and they are the three that can be checked
mechanically:

1. **File integrity** — SHA-256 of each supplied dataset recomputed and compared with
   `datasets/manifest.csv`.
2. **Link resolution** — each NTRS citation opened and the page read.
3. **Record match** — the title, authors, document type and report number on the NTRS
   record compared against what `sources.csv` claims.

What a person still has to do is read the document and confirm the *numbers* we intend
to use are really in it. No automated check can stand in for that.

## Dataset integrity

All four PSI metadata archives match their recorded checksums.

| File | SHA-256 vs manifest | Study | DOI |
| --- | --- | --- | --- |
| `PSI-25_metadata_PSI_metadata_PSI-101_BASS-II.zip` | match | PSI-25 Burning and Suppression of Solids - II | 10.60555/4qc4-de67 |
| `PSI-69_metadata_PSI-133_FLEX.zip` | match | PSI-69 Flame Extinguishment Experiment | 10.60555/mbq8-0451 |
| `PSI-98_metadata_PSI-166_SAFFIRE-I.zip` | match | PSI-98 Spacecraft Fire Safety Experiment-I | 10.60555/0t15-1z43 |
| `PSI-107_metadata_PSI-176_SPICE.zip` | match | PSI-107 Smoke Point In Co-flow Experiment | 10.60555/9kbh-e962 |

`PSI-159_Raw Data_21235L1_mfcSetpoints.csv` was additionally parsed with
`pyrakit.io.psi.read_psi159_setpoints`, which returned a populated `PSI159Setpoints`
record (Experiment 5, Test Point 21235L1). The reader works against the real file, not
only against fixtures.

## Row-by-row

### S01 — NASA PSI database directory — confirmed

`psi.nasa.gov` redirects to the NASA BPS data page. The per-investigation archives
follow the ISA-Tab layout: `i_Investigation.txt` carries Study Identifier, Study Title,
`Comment[DOI]`, release date and a prose `Comment[Approach]`.

### S03 — BASS-II summary report (NTRS 20210011385) — confirmed

Title, authors (Olson; Ferkul) and document type (Technical Memorandum) all match the
row. The abstract names the variables we want: ambient O2 concentration, ventilation
flow velocity, and fuel type, thickness and geometry.

Two numbers worth carrying forward, both stated in the abstract:

- heat release computed from O2 consumption at **13.1 kJ per gram of O2**;
- most tests had heat release rates **well below 100 W**, with a mean global equivalence
  ratio of about **1.3** (fuel rich).

The 13.1 kJ/g figure is the same constant used in the library's heat-release example,
which is now traceable to this report rather than being an unattributed default.

### S05 — Saffire status presentation (NTRS 20170002628) — rejected as a results source

The row already carried the suspicion *"Title is a status update; check it really covers
I-III results."* That suspicion is correct.

NTRS lists this record as a **Presentation** with **no abstract available**, delivered at
ICES Vienna and published **2016-07-13**. Saffire-II flew in November 2016 and Saffire-III
in 2017, so a talk given in July 2016 cannot report results from them.

It should not be used as a source of Saffire I-III results. For Saffire-I conditions use
PSI-98 (DOI 10.60555/0t15-1z43) instead, whose `Comment[Approach]` gives the sample
(SIBAL fabric, 75% cotton / 25% fiberglass, about 0.94 m by 0.4 m), the forced flow
velocity (20 cm/s) and the instrument list (two cameras, thermocouples, two radiometers,
solid-state pressure / CO2 / O2 sensors, two anemometers).

### S14 — FLEX data release (NASA/TP-2015-216046, NTRS 20150023456) — confirmed

Title, authors (Dietrich et al.) and the report number `NASA/TP-2015-216046` all match.
The abstract confirms the first 284 tests are included, and states plainly that the
report's intent is to release data rather than interpret it, which is the right posture
for using it as evidence.

## Still open

19 of 23 rows remain unverified, and none of the four above has a human signature yet.
That is a statement of where the evidence stands, not an apology for it: the point of
this project is to say where the evidence runs out, and that has to apply to our own
source list first.
