import json
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

import cli
import miner
from clone import CloneError
from codeql import CodeQLError
from github_api import GitHubAPIError
from models import Finding, OrganizationResult, Repository, RepositoryResult
from report import write_report
from sarif import SarifError


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr(miner, "get_available_languages", Mock(return_value={"python", "javascript"}))
    monkeypatch.setattr(miner, "get_organization_repositories", Mock(return_value=[
        Repository(full_name="org/b", clone_url="https://github.com/org/b.git"),
        Repository(full_name="org/a", clone_url="https://github.com/org/a.git"),
    ]))
    monkeypatch.setattr(miner, "clone_repository", Mock(return_value=tmp_path))
    monkeypatch.setattr(miner, "get_repository_languages", Mock(return_value=["Python"]))
    monkeypatch.setattr(miner, "create_database", Mock(return_value=tmp_path))
    monkeypatch.setattr(miner, "analyze_database", Mock(return_value=tmp_path / "output.sarif"))
    monkeypatch.setattr(miner, "parse_sarif", Mock(return_value=[Finding(rule_id="py/a", message="Example")]))
    return lambda: miner.scan_organization("org", "test-token", tmp_path / "results.json",
                                           workspace=tmp_path / "work", progress=lambda _: None)


def test_complete_pipeline(pipeline, tmp_path):
    result = pipeline()
    assert result.summary.analyzed == 2
    assert result.summary.findings == 2
    data = json.loads((tmp_path / "results.json").read_text())
    assert [repo["name"] for repo in data["repositories"]] == ["org/a", "org/b"]
    assert data["summary"]["findings"] == 2
    miner.clone_repository.assert_called()
    assert miner.clone_repository.call_args.kwargs["token"] == "test-token"


@pytest.mark.parametrize("component,error,status", [
    ("clone_repository", CloneError("clone"), "clone_failed"),
    ("get_repository_languages", GitHubAPIError("languages"), "language_detection_failed"),
    ("create_database", CodeQLError("database"), "database_failed"),
    ("analyze_database", CodeQLError("analysis"), "analysis_failed"),
    ("parse_sarif", SarifError("sarif"), "sarif_failed"),
])
def test_continue_after_failure(pipeline, component, error, status):
    function = getattr(miner, component)
    function.side_effect = [error, function.return_value]
    result = pipeline()
    assert [repo.status for repo in result.repositories] == [status, "analyzed"]
    assert result.summary.failed == 1


def test_partial_languages(pipeline):
    miner.get_repository_languages.return_value = ["Python", "TypeScript"]
    miner.create_database.side_effect = [CodeQLError("bad"), miner.create_database.return_value] * 2
    result = pipeline()
    assert result.summary.partial == 2
    assert result.repositories[0].languages == ["python"]
    assert len(result.repositories[0].analyses) == 2


def test_unsupported(pipeline):
    miner.get_repository_languages.return_value = ["HTML"]
    assert pipeline().summary.unsupported == 2
    miner.create_database.assert_not_called()


def test_report_stable(tmp_path):
    findings = [Finding(rule_id="z", message="z"), Finding(rule_id="a", message="a")]
    repos = [RepositoryResult(name=name, url="https://github.com/" + name,
                              status="analyzed", findings=list(findings)) for name in ["org/b", "org/a"]]
    result = OrganizationResult(organization="org", repositories=repos)
    first = write_report(result, tmp_path / "a.json").read_bytes()
    result.repositories.reverse()
    for repo in repos:
        repo.findings.reverse()
    assert write_report(result, tmp_path / "b.json").read_bytes() == first


def test_scan_cli(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    scan = Mock(return_value=OrganizationResult(organization="org", repositories=[]))
    monkeypatch.setattr(cli, "scan_organization", scan)
    result = CliRunner().invoke(cli.app, ["scan", "--organization", "org", "--output", str(tmp_path / "out.json")])
    assert result.exit_code == 0
    assert scan.call_args.args[:2] == ("org", "test-token")
    monkeypatch.delenv("GITHUB_TOKEN")
    assert CliRunner().invoke(cli.app, ["scan", "--organization", "org"]).exit_code == 2


def test_empty_organization(pipeline, tmp_path):
    miner.get_organization_repositories.return_value = []
    result = pipeline()
    assert result.summary.repositories == 0
    assert json.loads((tmp_path / "results.json").read_text())["repositories"] == []


def test_failed_list_does_not_replace_report(pipeline, tmp_path):
    output = tmp_path / "results.json"
    output.write_text("existing report")
    miner.get_organization_repositories.side_effect = GitHubAPIError("failed page")
    with pytest.raises(GitHubAPIError):
        pipeline()
    assert output.read_text() == "existing report"


def test_atomic_write_failure_preserves_report(tmp_path, monkeypatch):
    output = tmp_path / "out.json"
    output.write_text("existing report")
    monkeypatch.setattr("report.os.replace", Mock(side_effect=OSError("disk error")))
    with pytest.raises(OSError):
        write_report(OrganizationResult(organization="org", repositories=[]), output)
    assert output.read_text() == "existing report"
    assert not list(tmp_path.glob("*.tmp"))


def test_git_auth_not_in_arguments(tmp_path, monkeypatch):
    from clone import clone_repository
    run = Mock()
    monkeypatch.setattr("clone.subprocess.run", run)
    clone_repository(Repository(full_name="org/repo", clone_url="https://github.com/org/repo.git"),
                     tmp_path, token="fake-private-token")
    assert "fake-private-token" not in repr(run.call_args.args)
    assert run.call_args.kwargs["env"]["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
