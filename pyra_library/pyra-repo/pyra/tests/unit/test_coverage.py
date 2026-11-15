"""P6 evidence coverage contracts."""

from pyrakit.coverage import coverage
from pyrakit.matching import MatchPolicy
from pyrakit.schema import Conditions, ExperimentRecord, FuelSpec, Measure, Scenario, SourceRef


def conditions(gravity: float = 1e-5) -> Conditions:
    return Conditions(
        gravity_g=Measure(value=gravity, unit="dimensionless", u=1e-6, u_kind="type_a"),
        pressure=Measure(value=101, unit="kPa", u=0.1, u_kind="type_b"),
        o2_mole_fraction=Measure(value=0.21, unit="dimensionless", u=0.001, u_kind="type_b"),
        diluent="nitrogen",
        flow_mode="forced",
        flow_velocity=Measure(value=0.02, unit="m/s", u=0.001, u_kind="type_b"),
        fuel=FuelSpec(material="PMMA"),
        configuration="concurrent",
        length_scale=Measure(value=0.02, unit="m", u=0.001, u_kind="type_b"),
    )


def experiment(identifier: str, source: str, gravity: float = 1e-5) -> ExperimentRecord:
    return ExperimentRecord(
        experiment_id=identifier,
        investigation="synthetic",
        source=SourceRef(source_id=source),
        conditions=conditions(gravity),
    )


def test_empty_catalogue_is_explicit_no_coverage() -> None:
    report = coverage(Scenario(scenario_id="s", conditions=conditions()), [], MatchPolicy())
    assert report.verdict == "none"
    assert report.independent_sources == 0
    assert report.gaps == ("no matching experiment",)


def test_repeated_runs_from_one_source_count_once() -> None:
    scenario = Scenario(scenario_id="s", conditions=conditions())
    report = coverage(
        scenario,
        [experiment("e1", "apparatus-a"), experiment("e2", "apparatus-a")],
        MatchPolicy(),
    )
    assert report.verdict == "covered"
    assert report.independent_sources == 1
    assert report.nearest_distances == (0.0, 0.0)
