import json

import pytest

from core.exceptions import AppException
from miner.dependencies.errors import GrypeErrors
from miner.dependencies.parser import parse_grype


def test_parser_preserves_package_matches_and_locations(tmp_path):
    path = tmp_path / "grype.json"
    matches = [{
        "vulnerability": {"id": "CVE-2026-1234", "description": "Example", "severity": "High"},
        "artifact": {"name": name, "version": "1.0", "type": "python",
                     "locations": [{"path": "requirements.txt"}, {"path": "poetry.lock"}]},
    } for name in ["a", "b"]]
    path.write_text(json.dumps({"matches": matches}), encoding="utf-8")
    findings = parse_grype(path)
    assert [finding.package for finding in findings] == ["a", "b"]
    assert findings[0].locations == ["requirements.txt", "poetry.lock"]
    assert findings[0].description == "Example"
    assert findings[0].severity == "High"
    assert findings[0].version == "1.0"
    assert findings[0].package_type == "python"


def test_parser_accepts_empty_matches(tmp_path):
    path = tmp_path / "grype.json"
    path.write_text('{"matches": []}', encoding="utf-8")
    assert parse_grype(path) == []


def test_parser_preserves_all_cvss_sources(tmp_path):
    path = tmp_path / "grype.json"
    path.write_text(json.dumps({"matches": [{
        "vulnerability": {"id": "GHSA-example", "cvss": [{"source": "vendor", "version": "3.1",
            "vector": "CVSS:3.1/AV:N", "metrics": {"baseScore": 8.1}}]},
        "relatedVulnerabilities": [{"id": "CVE-example", "cvss": [{"source": "nvd",
            "version": "2.0", "metrics": {"baseScore": 7.5}}]}],
        "artifact": {"name": "a", "version": "1"},
    }]}), encoding="utf-8")
    scores = parse_grype(path)[0].scores
    assert [s.value for s in scores] == [8.1, 7.5]
    assert [s.source for s in scores] == ["vendor", "nvd"]
    assert scores[0].version == "3.1"
    assert scores[0].vector == "CVSS:3.1/AV:N"
    assert scores[1].vulnerability_id == "CVE-example"


@pytest.mark.parametrize("data", ["invalid", "null", "{}", '{"matches": {}}',
    '{"matches": [null]}', '{"matches": [{"vulnerability": {"id": "x"}, "artifact": {"name": 1, "version": "1"}}]}'])
def test_parser_rejects_invalid_results(tmp_path, data):
    path = tmp_path / "grype.json"
    path.write_text(data, encoding="utf-8")
    with pytest.raises(AppException) as error:
        parse_grype(path)
    assert error.value is GrypeErrors.InvalidResults
