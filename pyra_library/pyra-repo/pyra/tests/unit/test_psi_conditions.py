import pytest
from pydantic import ValidationError

from pyra.io import PSI159Setpoints, psi159_condition_record
from pyra.schema import PSIConditionRecord


def test_psi159_condition_record_preserves_raw_values() -> None:
    data = PSI159Setpoints(
        metadata={"Test Point": "A-01"},
        rows=({"MFCA1Setpoint(V)": "1.25"},),
    )
    record = psi159_condition_record(data, row_index=0, source_id="file-sha256:abc")
    assert record.investigation_id == "PSI-159"
    assert record.test_point_id == "A-01"
    assert record.raw_fields["setpoint.MFCA1Setpoint(V)"] == "1.25"
    assert record.normalized_conditions is None


def test_psi_condition_requires_review_for_normalized_values() -> None:
    with pytest.raises(ValidationError, match="reviewed"):
        PSIConditionRecord(
            investigation_id="PSI-159",
            source_id="source",
            mapping_status="reviewed",
        )


def test_psi_condition_rejects_negative_row_index() -> None:
    data = PSI159Setpoints(metadata={}, rows=({"x": "1"},))
    with pytest.raises(IndexError, match="non-negative"):
        psi159_condition_record(data, row_index=-1, source_id="source")
