from unittest.mock import Mock

from typer.testing import CliRunner

from miner import cli
from miner import github_api as api
from miner.models import OrganizationResult


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


def test_scan_cli(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    scan = Mock(return_value=OrganizationResult(
        organization="org", repositories=[]))
    monkeypatch.setattr(cli, "scan_organization", scan)
    result = CliRunner().invoke(cli.app, [
        "scan", "--organization", "org", "--output", str(tmp_path / "out.json")])
    assert result.exit_code == 0
    assert scan.call_args.args[:2] == ("org", "test-token")
    monkeypatch.delenv("GITHUB_TOKEN")
    assert CliRunner().invoke(
        cli.app, ["scan", "--organization", "org"]).exit_code == 2
