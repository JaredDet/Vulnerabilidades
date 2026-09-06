from unittest.mock import Mock

import pytest

from miner.models import Finding, OrganizationResult, RepositoryResult
from miner.report import write_report




def test_report_stable(tmp_path):
    findings = [Finding(rule_id="z", message="z"),
                Finding(rule_id="a", message="a")]
    repos = [RepositoryResult(name=name, url="https://github.com/" + name,
                              status="analyzed", findings=list(findings)) for name in ["org/b", "org/a"]]
    result = OrganizationResult(organization="org", repositories=repos)
    first = write_report(result, tmp_path / "a.json").read_bytes()
    result.repositories.reverse()
    for repo in repos:
        repo.findings.reverse()
    assert write_report(result, tmp_path / "b.json").read_bytes() == first


def test_atomic_write_failure_preserves_report(tmp_path, monkeypatch):
    output = tmp_path / "out.json"
    output.write_text("existing report")
    monkeypatch.setattr("miner.report.os.replace", Mock(
        side_effect=OSError("disk error")))
    with pytest.raises(OSError):
        write_report(OrganizationResult(
            organization="org", repositories=[]), output)
    assert output.read_text() == "existing report"
    assert not list(tmp_path.glob("*.tmp"))
