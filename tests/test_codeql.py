import subprocess
from unittest.mock import Mock

import pytest

from codeql import CodeQLError, analyze_database, create_database, get_available_languages


def test_analyze_database(tmp_path, monkeypatch):
    database = tmp_path / "database"
    database.mkdir()
    (database / "codeql-database.yml").touch()
    output = tmp_path / "results" / "result.sarif"
    run = Mock(side_effect=lambda *args, **kwargs: output.write_text('{}'))
    monkeypatch.setattr("codeql.subprocess.run", run)
    assert analyze_database(database, "python", output) == output.resolve()
    assert "codeql/python-queries:codeql-suites/python-code-scanning.qls" in run.call_args.args[0]
    assert "--format=sarifv2.1.0" in run.call_args.args[0]
    with pytest.raises(CodeQLError, match="ya existe"):
        analyze_database(database, "python", output)


@pytest.mark.parametrize("failure", [None, FileNotFoundError(), subprocess.TimeoutExpired("codeql", 1), subprocess.CalledProcessError(2, "codeql")])
def test_analysis_failure(tmp_path, monkeypatch, failure):
    database = tmp_path / "database"
    database.mkdir()
    (database / "codeql-database.yml").touch()
    monkeypatch.setattr("codeql.subprocess.run", Mock(side_effect=failure))
    with pytest.raises(CodeQLError):
        analyze_database(database, "python", tmp_path / "result.sarif")


def test_resolve_languages(monkeypatch):
    run = Mock(return_value=Mock(stdout=b'{"python": ["extractor"], "java": []}'))
    monkeypatch.setattr("codeql.subprocess.run", run)
    assert get_available_languages("custom/codeql") == {"python"}
    assert run.call_args.args[0] == ["custom/codeql", "resolve", "languages", "--format=json"]


@pytest.mark.parametrize("data", [b"invalid", b"[]", b'{"python": "path"}', b'{"python": [null]}'])
def test_invalid_output(monkeypatch, data):
    monkeypatch.setattr("codeql.subprocess.run", Mock(return_value=Mock(stdout=data)))
    with pytest.raises(CodeQLError):
        get_available_languages()


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("codeql", 30), subprocess.CalledProcessError(2, "codeql")])
def test_execution_error(monkeypatch, error):
    monkeypatch.setattr("codeql.subprocess.run", Mock(side_effect=error))
    with pytest.raises(CodeQLError):
        get_available_languages()


def test_create_database(tmp_path, monkeypatch):
    source = tmp_path / "source with spaces"
    source.mkdir()
    destination = tmp_path / "databases" / "python"
    run = Mock()
    monkeypatch.setattr("codeql.subprocess.run", run)
    assert create_database(source, "python", destination) == destination.resolve()
    assert f"--source-root={source.resolve()}" in run.call_args.args[0]
    assert "--language=python" in run.call_args.args[0]
    assert destination.parent.is_dir()


def test_database_paths(tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr("codeql.subprocess.run", run)
    with pytest.raises(CodeQLError):
        create_database(tmp_path / "missing", "python", tmp_path / "db")
    with pytest.raises(CodeQLError):
        create_database(tmp_path, "python", tmp_path / "db")
    with pytest.raises(CodeQLError):
        create_database(tmp_path, "python", tmp_path)
    run.assert_not_called()


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("codeql", 1), subprocess.CalledProcessError(2, "codeql")])
def test_database_errors(tmp_path, monkeypatch, error):
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setattr("codeql.subprocess.run", Mock(side_effect=error))
    with pytest.raises(CodeQLError):
        create_database(source, "python", tmp_path / "db")
