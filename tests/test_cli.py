import json
from unittest.mock import Mock

from typer.testing import CliRunner

from core.exceptions import AppException, ErrorType
from miner import cli
from miner.codeql.models import OrganizationResult
from miner.clone.errors import CloneErrors
from miner.clone.models import CloneResult, OrganizationCloneResult, Repository
from miner.dependencies.models import VulnerabilityReport


def test_cli_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr(
        cli,
        "clone_organization",
        Mock(side_effect=CloneErrors.GitHubRequestFailed),
    )
    result = CliRunner().invoke(
        cli.app, ["clone-repositories", "--organization", "org"]
    )
    assert result.exit_code == 1
    assert CloneErrors.GitHubRequestFailed.message in result.output
    assert "fake-token" not in result.output


def test_cli_validation_error_uses_central_handler(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr(
        cli,
        "clone_organization",
        Mock(
            side_effect=AppException(
                "organization_required",
                "La organización es obligatoria",
                ErrorType.VALIDATION,
            )
        ),
    )

    result = CliRunner().invoke(
        cli.app, ["clone-repositories", "--organization", "org"]
    )

    assert result.exit_code == 2
    assert "La organización es obligatoria" in result.output


def test_cli_uses_specific_exit_code_for_app_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    error = AppException(
        "already_exists",
        "El reporte ya existe",
        ErrorType.CONFLICT,
    )
    monkeypatch.setattr(
        cli,
        "clone_organization",
        Mock(side_effect=error),
    )

    result = CliRunner().invoke(
        cli.app, ["clone-repositories", "--organization", "org"]
    )

    assert result.exit_code == 3
    assert "El reporte ya existe" in result.output


def test_cli_os_error_uses_central_handler(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr(
        cli,
        "clone_organization",
        Mock(side_effect=OSError("disk error")),
    )

    result = CliRunner().invoke(
        cli.app, ["clone-repositories", "--organization", "org"]
    )

    assert result.exit_code == 8
    assert "No se pudo acceder al directorio" in result.output


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
        "analyze-code", "--organization", "org", "--output", str(tmp_path / "out.json"),
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
        cli.app, ["analyze-code", "--organization", "org"]).exit_code == 2


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
        "clone-repositories", "-o", "org", "--workspace", str(tmp_path), "--timeout", "42",
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["cloned"] == 1
    assert data["repositories"][0]["source"] == str(clones.repositories[0].source)
    assert "test-token" not in result.output
    assert clone.call_args.args == ("org", "test-token")
    assert clone.call_args.kwargs["workspace_path"] == tmp_path
    assert clone.call_args.kwargs["timeout"] == 42
    analyze.assert_not_called()


def test_clone_requires_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    clone = Mock()
    monkeypatch.setattr(cli, "clone_organization", clone)
    assert CliRunner().invoke(
        cli.app, ["clone-repositories", "-o", "org"]
    ).exit_code == 2
    clone.assert_not_called()


def test_analyze_without_clones_does_not_clone(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    clone = Mock()
    analyze = Mock()
    monkeypatch.setattr(cli, "clone_organization", clone)
    monkeypatch.setattr(cli, "analyze_organization", analyze)
    result = CliRunner().invoke(cli.app, [
        "analyze-code", "-o", "org",
    ])
    assert result.exit_code == 4
    assert "miner clone" in result.output
    clone.assert_not_called()
    analyze.assert_not_called()


def test_cli_help_keeps_command_names_and_options():
    runner = CliRunner()

    root_help = runner.invoke(cli.app, ["--help"])
    assert root_help.exit_code == 0
    assert "list" not in root_help.output
    assert "clone-repositories" in root_help.output
    assert "analyze-code" in root_help.output
    assert "generate-sbom" in root_help.output
    assert "scan-dependency-vulnerabilities" in root_help.output

    analyze_help = runner.invoke(cli.app, ["analyze-code", "--help"])
    assert analyze_help.exit_code == 0
    assert "--organization" in analyze_help.output
    assert "--run-id" in analyze_help.output
    assert "--timeout" in analyze_help.output


def test_dependency_vulnerabilities_cli_uses_selected_sbom_run(monkeypatch, tmp_path):
    report = VulnerabilityReport(organization="org", repositories=[])
    scan = Mock(return_value=report)
    monkeypatch.setattr(cli, "scan_organization_vulnerabilities", scan)

    result = CliRunner().invoke(cli.app, [
        "scan-dependency-vulnerabilities", "-o", "org", "--run-id", "example",
        "--output", str(tmp_path / "vulnerabilities.json"), "--grype", "custom-grype",
        "--timeout", "42",
    ])

    assert result.exit_code == 0
    assert scan.call_args.args == ("org", tmp_path / "vulnerabilities.json")
    assert scan.call_args.kwargs["run_id"] == "example"
    assert scan.call_args.kwargs["executable"] == "custom-grype"
    assert scan.call_args.kwargs["timeout"] == 42
    assert callable(scan.call_args.kwargs["progress"])
    assert "custom-grype" not in result.output


def test_dependency_vulnerabilities_help_names_repository_dependencies():
    result = CliRunner().invoke(cli.app, ["scan-dependency-vulnerabilities", "--help"])
    assert result.exit_code == 0
    assert "dependencias de los repositorios" in result.output


def test_cli_rejects_invalid_option_before_running_command(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    clone = Mock()
    monkeypatch.setattr(cli, "clone_organization", clone)

    result = CliRunner().invoke(
        cli.app,
        ["clone-repositories", "--organization", "org", "--timeout", "0"],
    )

    assert result.exit_code == 2
    assert "--timeout" in result.output
    clone.assert_not_called()


def test_cli_does_not_hide_unexpected_programming_errors(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        cli,
        "clone_organization",
        Mock(side_effect=RuntimeError("bug")),
    )

    result = CliRunner().invoke(
        cli.app, ["clone-repositories", "--organization", "org"]
    )

    assert result.exit_code == 1
    assert isinstance(result.exception, RuntimeError)
