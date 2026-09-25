import json
from unittest.mock import Mock

from typer.testing import CliRunner

from miner import cli
from miner.clone import github_api as api
from miner.analysis.analysis_code_ql.models import OrganizationResult
from miner.clone.models import CloneResult, OrganizationCloneResult, Repository


def test_cli_environment(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    get = Mock(return_value=[])
    monkeypatch.setattr(cli, "get_organization_repositories", get)
    assert CliRunner().invoke(cli.app, ["list", "org"]).exit_code == 0
    get.assert_called_once_with("org", "fake-token")
    monkeypatch.delenv("GITHUB_TOKEN")
    get.reset_mock()
    assert CliRunner().invoke(cli.app, ["list", "org"]).exit_code == 2
    get.assert_not_called()


def test_cli_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr(cli, "get_organization_repositories", Mock(
        side_effect=api.GitHubAPIError("API unavailable")))
    result = CliRunner().invoke(cli.app, ["list", "org"])
    assert result.exit_code == 1
    assert "API unavailable" in result.output
    assert "fake-token" not in result.output


def test_analyze_cli_never_clones(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    clones = OrganizationCloneResult(organization="org", workspace=tmp_path, repositories=[])
    clone = Mock()
    monkeypatch.setattr(cli, "clone_organization", clone)
    load = Mock(return_value=clones)
    monkeypatch.setattr(cli, "load_latest_clones", load)
    analyze = Mock(return_value=OrganizationResult(
        organization="org", repositories=[]))
    monkeypatch.setattr(cli, "analyze_organization", analyze)
    result = CliRunner().invoke(cli.app, [
        "analyze", "--organization", "org", "--output", str(tmp_path / "out.json"),
        "--run-id", "example", "--codeql", "custom-codeql", "--timeout", "42",
    ])
    assert result.exit_code == 0
    clone.assert_not_called()
    load.assert_called_once_with("org", run_id="example")
    assert analyze.call_args.args == (clones, tmp_path / "out.json")
    assert analyze.call_args.kwargs["token"] == "test-token"
    assert analyze.call_args.kwargs["executable"] == "custom-codeql"
    assert analyze.call_args.kwargs["timeout"] == 42
    monkeypatch.delenv("GITHUB_TOKEN")
    assert CliRunner().invoke(
        cli.app, ["analyze", "--organization", "org"]).exit_code == 2


def test_clone_cli_does_not_analyze(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    clones = OrganizationCloneResult(
        organization="org", workspace=tmp_path,
        repositories=[CloneResult(
            repository=Repository(full_name="org/repo", clone_url="https://github.com/org/repo.git"),
            source=tmp_path / "repositories" / "org" / "repo",
        )],
    )
    clone = Mock(return_value=clones)
    analyze = Mock()
    monkeypatch.setattr(cli, "clone_organization", clone)
    monkeypatch.setattr(cli, "analyze_organization", analyze)
    result = CliRunner().invoke(cli.app, [
        "clone", "-o", "org", "--workspace", str(tmp_path), "--timeout", "42",
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["cloned"] == 1
    assert data["repositories"][0]["source"] == str(clones.repositories[0].source)
    assert "test-token" not in result.output
    assert clone.call_args.args == ("org", "test-token")
    assert clone.call_args.kwargs["workspace"] == tmp_path
    assert clone.call_args.kwargs["timeout"] == 42
    analyze.assert_not_called()


def test_clone_list_failure_stops_processing(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(cli, "clone_organization", Mock(side_effect=api.GitHubAPIError("failed page")))
    analyze = Mock()
    monkeypatch.setattr(cli, "analyze_organization", analyze)
    result = CliRunner().invoke(cli.app, ["clone", "-o", "org"])
    assert result.exit_code == 1
    assert "failed page" in result.output
    analyze.assert_not_called()


def test_clone_requires_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    clone = Mock()
    monkeypatch.setattr(cli, "clone_organization", clone)
    assert CliRunner().invoke(cli.app, ["clone", "-o", "org"]).exit_code == 2
    clone.assert_not_called()


def test_analyze_without_clones_does_not_clone(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    clone = Mock()
    analyze = Mock()
    monkeypatch.setattr(cli, "clone_organization", clone)
    monkeypatch.setattr(cli, "analyze_organization", analyze)
    result = CliRunner().invoke(cli.app, [
        "analyze", "-o", "org",
    ])
    assert result.exit_code == 1
    assert "miner clone --organization org" in result.output
    clone.assert_not_called()
    analyze.assert_not_called()
