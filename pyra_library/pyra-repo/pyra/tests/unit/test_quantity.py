"""P1: Quantity construction rules, status propagation and artifact identity."""

import dataclasses
import itertools

import pytest

from pyrakit.provenance.status import (
    Quantity,
    Status,
    StatusError,
    StatusInputError,
    join,
)

SRC_REF = "doi:10.0000/placeholder|file-sha256:00|row 1"   # placeholder, not a real source


def measured(value: float = 1.0, u: float | None = 0.1) -> Quantity:
    return Quantity.measured(
        value, "kW", u, "type_b" if u is not None else "unknown", source_ref=SRC_REF
    )


def at_status(status: Status) -> Quantity:
    """Build one quantity of each status by legitimate routes."""
    if status is Status.MEASURED:
        return measured()
    if status is Status.SCENARIO:
        return Quantity.scenario(2.0, "kPa", None, "unknown", activity="user_input")
    return Quantity.derive(
        3.0, "kW", 0.2, "assumed", parents=[measured()], activity="m", method_status=status
    )


def test_measured_requires_a_source_reference() -> None:
    with pytest.raises(ValueError, match="source_ref"):
        Quantity.measured(1.0, "kW", 0.1, "type_b", source_ref="  ")


def test_measured_has_status_measured_and_no_parents() -> None:
    q = measured()
    assert q.status is Status.MEASURED
    assert q.prov.parents == ()
    assert q.prov.source_ref == SRC_REF


def test_uncertainty_and_kind_must_agree() -> None:
    with pytest.raises(ValueError):
        Quantity.measured(1.0, "kW", None, "type_b", source_ref=SRC_REF)
    with pytest.raises(ValueError):
        Quantity.measured(1.0, "kW", 0.1, "unknown", source_ref=SRC_REF)
    with pytest.raises(ValueError):
        Quantity.measured(1.0, "kW", 0.1, "guess", source_ref=SRC_REF)
    assert measured(u=None).u_kind == "unknown"


def test_negative_or_nan_uncertainty_is_rejected() -> None:
    with pytest.raises(ValueError):
        measured(u=-0.1)
    with pytest.raises(ValueError):
        measured(u=float("nan"))


def test_unit_must_be_nonempty() -> None:
    with pytest.raises(ValueError):
        Quantity.measured(1.0, "  ", 0.1, "type_b", source_ref=SRC_REF)


def test_derived_status_is_join_of_inputs_for_every_combination() -> None:
    for a, b in itertools.product(list(Status), list(Status)):
        child = Quantity.derive(
            0.0, "kW", 0.0, "assumed",
            parents=[at_status(a), at_status(b)], activity="combine",
        )
        assert child.status >= a and child.status >= b
        assert child.status == join(Status.DERIVED, a, b)


def test_a_result_touching_a_scenario_is_never_measured() -> None:
    child = Quantity.derive(
        1.0, "kW", 0.1, "assumed", parents=[measured(), at_status(Status.SCENARIO)], activity="x"
    )
    assert child.status is Status.SCENARIO


def test_derive_cannot_produce_measured_or_use_no_inputs() -> None:
    with pytest.raises(StatusError):
        Quantity.derive(
            1.0, "kW", 0.1, "assumed", parents=[measured()], activity="x",
            method_status=Status.MEASURED,
        )
    with pytest.raises(ValueError):
        Quantity.derive(1.0, "kW", 0.1, "assumed", parents=[], activity="x")


def test_max_input_status_is_enforced_at_call_time() -> None:
    sim = at_status(Status.SIMULATED)
    with pytest.raises(StatusInputError):
        Quantity.derive(
            1.0, "kW", 0.1, "assumed", parents=[measured(), sim], activity="hrr",
            max_input_status=Status.DERIVED,
        )


def test_artifact_id_is_deterministic_and_environment_independent() -> None:
    a = Quantity.measured(
        1.0, "kW", 0.1, "type_b", source_ref=SRC_REF,
        code_version="aaa", env_hash="e1", created_utc="2026-01-01T00:00:00Z",
    )
    b = Quantity.measured(
        1.0, "kW", 0.1, "type_b", source_ref=SRC_REF,
        code_version="bbb", env_hash="e2", created_utc="2030-06-06T00:00:00Z",
    )
    assert a.prov.artifact_id == b.prov.artifact_id


def test_modifying_any_parent_changes_the_child_id() -> None:
    def child(parent: Quantity) -> Quantity:
        return Quantity.derive(5.0, "kW", 0.5, "assumed", parents=[parent], activity="scale")

    base = child(measured(value=1.0))
    assert child(measured(value=1.0)).prov.artifact_id == base.prov.artifact_id
    assert child(measured(value=1.0001)).prov.artifact_id != base.prov.artifact_id
    assert child(measured(value=1.0, u=0.2)).prov.artifact_id != base.prov.artifact_id


def test_changing_parameters_or_activity_changes_the_id() -> None:
    p = measured()

    def mk(activity: str, k: float) -> Quantity:
        return Quantity.derive(
            1.0, "kW", 0.1, "assumed", parents=[p], activity=activity, params={"k": k}
        )
    assert mk("f@1", 1.0).prov.artifact_id != mk("f@1", 2.0).prov.artifact_id
    assert mk("f@1", 1.0).prov.artifact_id != mk("f@2", 1.0).prov.artifact_id


def test_verify_detects_tampering() -> None:
    q = measured()
    assert q.verify()
    assert not dataclasses.replace(q, value=99.0).verify()
    assert not dataclasses.replace(q, status=Status.DERIVED).verify()


def test_quantity_is_frozen() -> None:
    q = measured()
    with pytest.raises(dataclasses.FrozenInstanceError):
        q.value = 2.0  # type: ignore[misc]


def test_status_must_be_a_status() -> None:
    q = measured()
    with pytest.raises(TypeError):
        dataclasses.replace(q, status=1)  # type: ignore[arg-type]
