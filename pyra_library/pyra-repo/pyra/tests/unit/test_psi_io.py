"""Readers for the supplied PSI metadata and raw setpoint formats."""

from pathlib import Path

from pyrakit.io import read_psi159_setpoints, read_psi_metadata_zip

DATASETS = Path(__file__).resolve().parents[5] / "datasets"


def test_metadata_zip_preserves_investigation_identity() -> None:
    metadata = read_psi_metadata_zip(DATASETS / "PSI-25_metadata_PSI_metadata_PSI-101_BASS-II.zip")
    assert metadata.investigation_id == "PSI-25"
    assert metadata.title == "Burning and Suppression of Solids - II"
    assert metadata.doi == "10.60555/4qc4-de67"
    assert "s_PSI-25.txt" in metadata.members


def test_psi159_setpoints_keep_raw_columns_and_metadata() -> None:
    result = read_psi159_setpoints(DATASETS / "PSI-159_Raw Data_21235L1_mfcSetpoints.csv")
    assert result.metadata["Test Point"] == "21235L1"
    assert result.rows[0]["MFCA1Setpoint(V)"] == "0.000000"
    assert "MFCA3Setpoint(V)" in result.rows[0]
