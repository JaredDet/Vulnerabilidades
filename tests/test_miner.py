import json
from unittest.mock import Mock

import pytest

from miner import pipeline as miner
from miner.clone import CloneError
from miner.codeql import CodeQLError
from miner.github_api import GitHubAPIError
from miner.models import Finding, Repository
from miner.sarif import SarifError


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr(miner, "get_available_languages",
                        Mock(return_value={"python", "javascript"}))
    monkeypatch.setattr(miner, "get_organization_repositories", Mock(return_value=[
        Repository(full_name="org/b",
                   clone_url="https://github.com/org/b.git"),
        Repository(full_name="org/a",
                   clone_url="https://github.com/org/a.git"),
    ]))
    monkeypatch.setattr(miner, "clone_repository", Mock(return_value=tmp_path))
    monkeypatch.setattr(miner, "get_repository_languages",
                        Mock(return_value=["Python"]))
    monkeypatch.setattr(miner, "create_database", Mock(return_value=tmp_path))
    monkeypatch.setattr(miner, "analyze_database", Mock(
        return_value=tmp_path / "output.sarif"))
    monkeypatch.setattr(miner, "parse_sarif", Mock(
        return_value=[Finding(rule_id="py/a", message="Example")]))
    return lambda: miner.scan_organization("org", "test-token", tmp_path / "results.json",
                                           workspace=tmp_path / "work", progress=lambda _: None)


def test_complete_pipeline(pipeline, tmp_path):
    result = pipeline()
    assert result.summary.analyzed == 2
    assert result.summary.findings == 2
    data = json.loads((tmp_path / "results.json").read_text())
    assert [repo["name"]
            for repo in data["repositories"]] == ["org/a", "org/b"]
    assert data["summary"]["findings"] == 2
    miner.clone_repository.assert_called()
    assert miner.clone_repository.call_args.kwargs["token"] == "test-token"


@pytest.mark.parametrize("component,error,status", [
    ("clone_repository", CloneError("clone"), "clone_failed"),
    ("get_repository_languages", GitHubAPIError(
        "languages"), "language_detection_failed"),
    ("create_database", CodeQLError("database"), "database_failed"),
    ("analyze_database", CodeQLError("analysis"), "analysis_failed"),
    ("parse_sarif", SarifError("sarif"), "sarif_failed"),
])
def test_continue_after_failure(pipeline, component, error, status):
    function = getattr(miner, component)
    function.side_effect = [error, function.return_value]
    result = pipeline()
    assert [repo.status for repo in result.repositories] == [
        status, "analyzed"]
    assert result.summary.failed == 1


def test_partial_languages(pipeline):
    miner.get_repository_languages.return_value = ["Python", "TypeScript"]
    miner.create_database.side_effect = [CodeQLError(
        "bad"), miner.create_database.return_value] * 2
    result = pipeline()
    assert result.summary.partial == 2
    assert result.repositories[0].languages == ["python"]
    assert len(result.repositories[0].analyses) == 2


def test_unsupported(pipeline):
    miner.get_repository_languages.return_value = ["HTML"]
    assert pipeline().summary.unsupported == 2
    miner.create_database.assert_not_called()


def test_empty_organization(pipeline, tmp_path):
    miner.get_organization_repositories.return_value = []
    result = pipeline()
    assert result.summary.repositories == 0
    assert json.loads((tmp_path / "results.json").read_text()
                      )["repositories"] == []


def test_failed_list_does_not_replace_report(pipeline, tmp_path):
    output = tmp_path / "results.json"
    output.write_text("existing report")
    miner.get_organization_repositories.side_effect = GitHubAPIError(
        "failed page")
    with pytest.raises(GitHubAPIError):
        pipeline()
    assert output.read_text() == "existing report"
