from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from miner.sbom.models import SBOMReport, SBOMResult
from miner.sbom.report import write_report


def test_report_is_sorted_and_preserves_input(tmp_path):
    report = SBOMReport(organization="org", repositories=[
        SBOMResult(
            full_name=f"org/{name}", commit="abc123", generation_date=datetime(2026, 1, 1, tzinfo=UTC),
            syft_version="1.0.0", status="generated", component_count=2, sbom_path=f"{name}.json",
        ) for name in ["b", "a"]
    ])
    output = write_report(report, tmp_path / "out.json")
    restored = SBOMReport.model_validate_json(output.read_text(encoding="utf-8"))
    assert [item.full_name for item in restored.repositories] == ["org/a", "org/b"]
    assert report.repositories[0].full_name == "org/b"
    assert restored.repositories[0].component_count == 2
    first = output.read_bytes()
    report.repositories.reverse()
    assert write_report(report, output).read_bytes() == first


def test_atomic_failure_preserves_existing_report(tmp_path, monkeypatch):
    output = tmp_path / "out.json"
    output.write_text("existing report")
    monkeypatch.setattr("miner.sbom.report.os.replace", Mock(side_effect=OSError("disk error")))
    with pytest.raises(OSError):
        write_report(SBOMReport(organization="org"), output)
    assert output.read_text() == "existing report"
    assert not list(tmp_path.glob("*.tmp"))
