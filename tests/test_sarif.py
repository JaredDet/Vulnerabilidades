import json

import pytest

from core.exceptions import AppException
from miner.analysis.analysis_code_ql.errors import SarifErrors
from miner.analysis.analysis_code_ql.sarif import parse_sarif


def write_sarif(tmp_path, runs):
    path = tmp_path / "results.sarif"
    path.write_text(json.dumps({"version": "2.1.0", "runs": runs}), encoding="utf-8")
    return path


def test_rule_location_and_severity(tmp_path):
    run = {
        "tool": {"driver": {"rules": [{"id": "py/test", "defaultConfiguration": {"level": "warning"}}]}},
        "artifacts": [{"location": {"uri": "src/my%20file.py"}}],
        "results": [{"ruleIndex": 0, "message": {"text": "Problem"}, "locations": [{
            "physicalLocation": {"artifactLocation": {"index": 0}, "region": {"startLine": 4, "startColumn": 2}}
        }]}],
    }
    finding, = parse_sarif(write_sarif(tmp_path, [run]))
    assert finding.model_dump() == {
        "rule_id": "py/test", "message": "Problem", "severity": "warning",
        "file": "src/my file.py", "start_line": 4, "start_column": 2,
    }
    run["results"][0]["level"] = "error"
    assert parse_sarif(write_sarif(tmp_path, [run]))[0].severity == "error"


def test_multiple_runs_and_missing_location(tmp_path):
    runs = [{"results": [{"ruleId": rule, "message": {"text": "Message"}}]} for rule in ["z", "a"]]
    findings = parse_sarif(write_sarif(tmp_path, runs))
    assert [f.rule_id for f in findings] == ["a", "z"]
    assert findings[0].file is None
    assert findings[0].severity is None
    assert findings == parse_sarif(write_sarif(tmp_path, list(reversed(runs))))


def test_empty_results(tmp_path):
    assert parse_sarif(write_sarif(tmp_path, [{"results": []}])) == []


@pytest.mark.parametrize("run", [
    {"results": [{}]},
    {"results": {}},
    {"results": [{"ruleIndex": -1, "message": {"text": "bad"}}]},
    {"invocations": [{"executionSuccessful": False}]},
])
def test_invalid_run(tmp_path, run):
    with pytest.raises(AppException):
        parse_sarif(write_sarif(tmp_path, [run]))


@pytest.mark.parametrize("contents", ["not json", "[]", '{"version": "2.0", "runs": []}'])
def test_invalid_document(tmp_path, contents):
    path = tmp_path / "bad.sarif"
    path.write_text(contents)
    with pytest.raises(AppException):
        parse_sarif(path)


def test_missing_file(tmp_path):
    with pytest.raises(AppException) as raised:
        parse_sarif(tmp_path / "missing.sarif")
    assert raised.value is SarifErrors.InvalidJson


def test_conflicting_rule_reference(tmp_path):
    run = {
        "tool": {"driver": {"rules": [{"id": "py/expected"}]}},
        "results": [{"ruleId": "py/other", "ruleIndex": 0, "message": {"text": "Problem"}}],
    }
    with pytest.raises(AppException) as raised:
        parse_sarif(write_sarif(tmp_path, [run]))
    assert raised.value is SarifErrors.RuleMismatch
