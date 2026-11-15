"""P12 report contracts."""

from pyrakit.provenance import Quantity
from pyrakit.report import build_report


def test_report_contains_status_and_artifact_id(tmp_path) -> None:
    quantity = Quantity.measured(
        1.0, "kW", 0.1, "type_b", source_ref="doi:10.0000/example|synthetic"
    )
    output = build_report([quantity], tmp_path / "report.html")
    text = output.read_text(encoding="utf-8")
    assert "MEASURED" in text
    assert quantity.prov.artifact_id in text
    assert "1.0 kW" in text
