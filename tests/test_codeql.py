import subprocess
from unittest.mock import Mock

import pytest

from core.exceptions import AppException
from miner.analysis.analysis_code_ql import codeql
from miner.analysis.analysis_code_ql.codeql import analyze_database, create_database
from miner.analysis.analysis_code_ql.errors import CodeQLErrors


def test_analyze_database(tmp_path, monkeypatch):
    database = tmp_path / "database"
    database.mkdir()
    (database / "codeql-database.yml").touch()
    output = tmp_path / "results" / "result.sarif"
    run = Mock(side_effect=lambda *args, **kwargs: output.write_text('{}'))
    monkeypatch.setattr(codeql.subprocess, "run", run)
    assert analyze_database(database, "python", output) == output.resolve()
    assert "codeql/python-queries:codeql-suites/python-code-scanning.qls" in run.call_args.args[0]
    assert "--format=sarifv2.1.0" in run.call_args.args[0]
    with pytest.raises(AppException) as raised:
        analyze_database(database, "python", output)
    assert raised.value is CodeQLErrors.SarifAlreadyExists


@pytest.mark.parametrize("failure", [None, FileNotFoundError(), subprocess.TimeoutExpired("codeql", 1), subprocess.CalledProcessError(2, "codeql")])
def test_analysis_failure(tmp_path, monkeypatch, failure):
    database = tmp_path / "database"
    database.mkdir()
    (database / "codeql-database.yml").touch()
    monkeypatch.setattr(codeql.subprocess, "run", Mock(side_effect=failure))
    with pytest.raises(AppException):
        analyze_database(database, "python", tmp_path / "result.sarif")


def test_create_database(tmp_path, monkeypatch):
    source = tmp_path / "source with spaces"
    source.mkdir()
    destination = tmp_path / "databases" / "python"
    run = Mock()
    monkeypatch.setattr(codeql.subprocess, "run", run)
    assert create_database(
        source, destination, token="test-token") == destination.resolve()
    assert f"--source-root={source.resolve()}" in run.call_args.args[0]
    assert "--db-cluster" in run.call_args.args[0]
    assert run.call_args.kwargs["env"]["GITHUB_TOKEN"] == "test-token"
    assert "test-token" not in repr(run.call_args.args)
    assert destination.parent.is_dir()


def test_database_paths(tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr(codeql.subprocess, "run", run)
    with pytest.raises(AppException):
        create_database(tmp_path / "missing", tmp_path / "db", token="test-token")
    with pytest.raises(AppException):
        create_database(tmp_path, tmp_path / "db", token="test-token")
    with pytest.raises(AppException):
        create_database(tmp_path, tmp_path, token="test-token")
    run.assert_not_called()


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("codeql", 1), subprocess.CalledProcessError(2, "codeql")])
def test_database_errors(tmp_path, monkeypatch, error):
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setattr(codeql.subprocess, "run", Mock(side_effect=error))
    with pytest.raises(AppException):
        create_database(source, tmp_path / "db", token="test-token")
