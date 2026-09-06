from unittest.mock import Mock

import pytest

from miner.models import Finding, OrganizationResult, RepositoryResult
from miner.report import write_report


def test_findings_sorted_by_file_line_and_rule(tmp_path):
    findings = [
        Finding(rule_id=rule, message="Example", file=file, start_line=line)
        for file, line, rule in [("z.py", 1, "a"), ("a.py", 20, "a"),
                                 ("a.py", 2, "z"), ("a.py", 2, "a")]
    ]
    result = OrganizationResult(organization="org", repositories=[
        RepositoryResult(name="org/repo", url="https://github.com/org/repo",
                         status="analyzed", findings=findings)
    ])
    output = write_report(result, tmp_path / "out.json")
    restored = OrganizationResult.model_validate_json(
        output.read_text(encoding="utf-8"))
    assert [(f.file, f.start_line, f.rule_id) for f in restored.repositories[0].findings] == [
        ("a.py", 2, "a"), ("a.py", 2, "z"), ("a.py", 20, "a"), ("z.py", 1, "a")
    ]
    assert result.repositories[0].findings[0].file == "z.py"


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
