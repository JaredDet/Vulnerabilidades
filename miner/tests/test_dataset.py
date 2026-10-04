import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from core.exceptions import AppException
from miner import cli
from miner.clone.models import CloneResult, OrganizationCloneResult, Repository
from miner.dataset import Dataset, generate_dataset


def clones_at(root):
    return OrganizationCloneResult(organization="org", workspace=root, repositories=[
        CloneResult(repository=Repository(full_name="org/a", clone_url="https://github.com/org/a.git"), source=root / "a")
    ])


def test_dataset_merges_tools_and_preserves_provenance(tmp_path):
    clones = clones_at(tmp_path)
    codeql = tmp_path / "analysis_results/codeql-one/codeql-results.json"
    codeql.parent.mkdir(parents=True)
    codeql.write_text(json.dumps({"organization": "org", "repositories": [{
        "name": "org/a", "url": "https://github.com/org/a", "status": "analyzed",
        "languages": [{"language": "python", "status": "analyzed", "findings": [{
            "rule_id": "py/example", "message": "Example", "severity": "warning", "file": "a.py", "start_line": 5,
        }]}],
    }]}), encoding="utf-8")
    raw = tmp_path / "vulnerabilities/vulnerability-one/a.json"
    raw.parent.mkdir(parents=True)
    raw.write_text(json.dumps({"matches": [{"vulnerability": {"id": "CVE-example", "severity": "High"},
        "artifact": {"name": "pkg", "version": "1", "locations": [{"path": "requirements.txt"}]}}]}), encoding="utf-8")
    (raw.parent / "vulnerability-results.json").write_text(json.dumps({"organization": "org", "repositories": [{
        "full_name": "org/a", "commit": "abc", "analysis_date": "2026-10-02T00:00:00Z", "grype_version": "1",
        "status": "analyzed", "vulnerability_count": 0, "report_path": str(raw),
    }]}), encoding="utf-8")
    output = generate_dataset(clones)
    data = Dataset.model_validate_json(output.read_text(encoding="utf-8"))
    assert output == tmp_path / "dataset.json"
    assert data.findings_count == 2
    assert data.findings[0].start_line == 5
    assert data.findings[0].severity_kind == "sarif_level"
    assert data.findings[1].commit == "abc"
    assert data.findings[1].locations == ["requirements.txt"]
    assert data.repositories[0].grype_status == "analyzed"


def test_dataset_marks_missing_tools(tmp_path):
    output = generate_dataset(clones_at(tmp_path))
    data = Dataset.model_validate_json(output.read_text(encoding="utf-8"))
    assert data.repositories[0].codeql_status == "not_run"
    assert data.findings == []


def test_dataset_does_not_replace_output_on_invalid_source(tmp_path):
    output = tmp_path / "dataset.json"
    output.write_text("previous", encoding="utf-8")
    report = tmp_path / "analysis_results/codeql-one/codeql-results.json"
    report.parent.mkdir(parents=True)
    report.write_text("invalid", encoding="utf-8")
    with pytest.raises(AppException):
        generate_dataset(clones_at(tmp_path))
    assert output.read_text() == "previous"


def test_run_orders_stages_and_pins_runs(tmp_path, monkeypatch):
    root = tmp_path / "clone-example"
    clones = clones_at(root)
    calls = []
    monkeypatch.setenv("GITHUB_TOKEN", "test")
    mocks = {}
    for name, result in [
        ("clone_organization", clones), ("analyze_organization", None),
        ("generate_organization_sbom", SimpleNamespace(repositories=[SimpleNamespace(sbom_path=str(root / "sboms/sbom-selected/a.json"))])),
        ("scan_organization_vulnerabilities", None), ("generate_dataset", root / "dataset.json"),
    ]:
        def invoke(*args, _name=name, _result=result, **kwargs):
            calls.append(_name)
            return _result
        mocks[name] = Mock(side_effect=invoke)
        monkeypatch.setattr(cli, name, mocks[name])
    result = CliRunner().invoke(cli.app, ["run", "-o", "org", "--workspace", str(tmp_path), "--page-size", "7"])
    assert result.exit_code == 0, result.output
    assert calls == list(mocks)
    assert mocks["clone_organization"].call_args.kwargs["page_size"] == 7
    assert mocks["generate_organization_sbom"].call_args.kwargs["run_id"] == "example"
    assert mocks["scan_organization_vulnerabilities"].call_args.kwargs["clone_run_id"] == "example"
    assert mocks["scan_organization_vulnerabilities"].call_args.kwargs["run_id"] == "selected"
    for stage, name in enumerate([
        "clonación de repositorios",
        "análisis de código con CodeQL",
        "generación de SBOM con Syft",
        "análisis de dependencias con Grype",
        "generación del dataset integrado",
    ], 1):
        assert f"Etapa {stage}/5 iniciada: {name}" in result.output
        assert f"Etapa {stage}/5 completada: {name}" in result.output
