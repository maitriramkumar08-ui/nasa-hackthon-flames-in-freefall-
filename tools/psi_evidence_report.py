"""Read the supplied NASA PSI archives and report what their evidence actually covers.

Run it from the repository root:

    python tools/psi_evidence_report.py

Three things happen, in order, and the order matters:

1. Every supplied dataset is checked against the SHA-256 in `datasets/manifest.csv`.
   A file that does not match is reported and then ignored; nothing downstream is
   allowed to quietly use it.
2. Each PSI metadata archive is read with `pyrakit.io.psi.read_psi_metadata_zip`, which
   returns the investigation's own identifier, title and DOI. That is NASA's metadata,
   read from the supplied file, not re-typed here.
3. A small table of conditions -- hand-entered, each line citing where it came from --
   is turned into PYRA model-card envelopes, and a set of habitat scenarios is checked
   against them with the same claim gate the library uses everywhere else.

The point of step 3 is the honest answer to "what does this evidence support?". Most
scenarios come back uncovered, and that is the finding, not a failure of the tool.

Nothing here interprets the experiments or makes a fire-safety claim.
"""

from __future__ import annotations

import csv
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"

# Make the library importable when it has not been pip-installed.
_LIB = ROOT / "pyra_library" / "pyra-repo" / "pyra" / "src"
if _LIB.is_dir():
    sys.path.insert(0, str(_LIB))

from pyrakit.adapters import check_envelope  # noqa: E402
from pyrakit.io.psi import read_psi_metadata_zip  # noqa: E402
from pyrakit.schema import (  # noqa: E402
    Conditions,
    FuelSpec,
    Measure,
    ModelCard,
    Scenario,
    ValidationEvidence,
)


@dataclass(frozen=True)
class RecordedConditions:
    """Conditions transcribed by hand from one investigation, with its citation.

    `source` must say exactly where the numbers came from, and `signed_off_by` stays
    empty until a person has read that source and confirmed them. An entry nobody has
    signed is still shown, and still marked unsigned.
    """

    investigation: str
    source: str
    envelope: dict[str, object]
    signed_off_by: str = ""


# Transcribed from the `Comment[Approach]` text inside the supplied PSI archives and from
# the NTRS records listed in sources/verification_log.md. Only values stated explicitly in
# those documents appear here. Ranges are NOT widened to make scenarios fit.
RECORDED = (
    RecordedConditions(
        investigation="PSI-98 Saffire-I",
        source="PSI-98 i_Investigation.txt Comment[Approach]; DOI 10.60555/0t15-1z43",
        envelope={
            # "Saffire-I was conducted at an air flow velocity of 20 cm/s."
            "flow_velocity": {"min": 0.20, "max": 0.20, "unit": "m/s"},
            # "approximately 0.94 meters long and 0.4 meters wide"
            "length_scale": {"min": 0.4, "max": 0.94, "unit": "m"},
            "fuel_material": ["SIBAL fabric"],
            "flow_mode": ["forced"],
            # Pressure, O2 and gravity were MEASURED by onboard sensors but their values
            # are not stated in this metadata, so no range is recorded for them.
        },
    ),
    RecordedConditions(
        investigation="PSI-25 BASS-II",
        source="PSI-25 Comment[Approach] and NTRS 20210011385; DOI 10.60555/4qc4-de67",
        envelope={
            # "a small wind tunnel which could impose airflow speeds up to 40 cm/s"
            "flow_velocity": {"min": 0.0, "max": 0.40, "unit": "m/s"},
            # "oxygen varied below 21% by adding nitrogen"
            "o2_mole_fraction": {"min": 0.0, "max": 0.21},
            "flow_mode": ["forced"],
        },
    ),
)

HABITAT_SCENARIOS = (
    ("iss-like-bench", 1.0, 0.21, 101.3, 0.20, "SIBAL fabric"),
    ("saffire-i-replay", 1e-5, 0.21, 101.3, 0.20, "SIBAL fabric"),
    ("low-oxygen-habitat", 1e-5, 0.16, 70.0, 0.20, "SIBAL fabric"),
    ("spacesuit-high-o2", 1e-5, 1.00, 29.6, 0.05, "Nomex"),
    ("quiescent-stowage", 1e-5, 0.21, 101.3, 0.01, "PMMA"),
)


def verify_datasets() -> tuple[list[str], list[str]]:
    """Recompute every checksum in the manifest. Returns (matched, mismatched)."""
    manifest = DATASETS / "manifest.csv"
    if not manifest.is_file():
        return [], []
    matched: list[str] = []
    mismatched: list[str] = []
    for row in csv.DictReader(manifest.open(encoding="utf-8")):
        target = DATASETS / row["file"]
        if not target.is_file():
            mismatched.append(f"{row['file']} (missing)")
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        (matched if digest == row["sha256"] else mismatched).append(row["file"])
    return matched, mismatched


def scenario_for(
    name: str, gravity: float, o2: float, pressure_kpa: float, flow: float, fuel: str
) -> Scenario:
    return Scenario(
        scenario_id=name,
        purpose="coverage check",
        conditions=Conditions(
            gravity_g=Measure(value=gravity, unit="dimensionless"),
            pressure=Measure(value=pressure_kpa, unit="kPa"),
            o2_mole_fraction=Measure(value=o2, unit="dimensionless"),
            diluent="nitrogen",
            flow_mode="forced",
            flow_velocity=Measure(value=flow, unit="m/s"),
            fuel=FuelSpec(material=fuel),
            configuration="concurrent",
            length_scale=Measure(value=0.5, unit="m"),
        ),
    )


def card_for(record: RecordedConditions) -> ModelCard:
    return ModelCard(
        name=record.investigation,
        version="as-supplied",
        code_hash="n/a",
        licence="NASA PSI terms",
        physics_summary="Recorded experimental conditions; not a model.",
        envelope=[
            ValidationEvidence(
                experiment_ids=[record.investigation],
                quantity="observed conditions",
                metric="range",
                result={"note": record.source},
                envelope=record.envelope,
            )
        ],
    )


def main() -> int:
    print("=" * 76)
    print("1. Dataset integrity")
    matched, mismatched = verify_datasets()
    print(f"   {len(matched)} of {len(matched) + len(mismatched)} supplied files match "
          f"their recorded SHA-256.")
    for bad in mismatched:
        print(f"   MISMATCH, not used: {bad}")

    print()
    print("=" * 76)
    print("2. Investigations, read from the supplied NASA archives")
    for archive in sorted(DATASETS.glob("*.zip")):
        if archive.name in mismatched:
            continue
        meta = read_psi_metadata_zip(archive)
        print(f"   {meta.investigation_id:<9} {meta.title}")
        print(f"             DOI {meta.doi}")

    print()
    print("=" * 76)
    print("3. What those recorded conditions cover")
    unsigned = [r.investigation for r in RECORDED if not r.signed_off_by]
    if unsigned:
        print(f"   NOTE: conditions for {'; '.join(unsigned)} are transcribed but not yet")
        print("   signed off by a person. Treat every verdict below as provisional.")
    print()

    covered = 0
    for name, gravity, o2, pressure, flow, fuel in HABITAT_SCENARIOS:
        scenario = scenario_for(name, gravity, o2, pressure, flow, fuel)
        hits = []
        reasons = []
        for record in RECORDED:
            check = check_envelope(card_for(record), scenario)
            if check.inside:
                hits.append(record.investigation)
            else:
                entry = check.evidence[0]
                if entry.missing_required_axes:
                    why = "does not state " + ", ".join(entry.missing_required_axes)
                else:
                    why = "; ".join(axis.reason for axis in entry.outside)
                reasons.append(f"{record.investigation}: {why}")
        if hits:
            covered += 1
            print(f"   COVERED     {name}")
            print(f"               by {', '.join(hits)}")
        else:
            print(f"   NO EVIDENCE {name}")
            for reason in reasons:
                print(f"               {reason}")

    total = len(HABITAT_SCENARIOS)
    print()
    print(f"   {covered} of {total} habitat scenarios are covered by the supplied evidence.")
    print()
    print("   The reasons above are the product. Note that no supplied investigation")
    print("   states gravity or pressure numerically in its metadata, even though both")
    print("   were measured in flight. Those values have to come from the papers before")
    print("   any of these scenarios can be called covered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
