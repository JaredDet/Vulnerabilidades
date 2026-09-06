from unittest.mock import Mock
import subprocess

import pytest
import requests
from pydantic import ValidationError
from typer.testing import CliRunner

import github_api as api
import cli
from clone import CloneError, clone_repository


def test_pagination(monkeypatch):
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    pages = [[{"full_name": "org/a", "clone_url": "https://github.com/org/a.git"}], []]
    session.get.side_effect = [Mock(json=Mock(return_value=page)) for page in pages]
    monkeypatch.setattr(api.requests, "Session", lambda: session)
    result = api.get_organization_repositories("org", "fake-token", page_size=1)
    assert result[0].full_name == "org/a"
    assert [call.kwargs["params"]["page"] for call in session.get.call_args_list] == [1, 2]
    session.headers.update.assert_called_once_with(api._build_headers("fake-token"))


def test_failed_page_propagates(monkeypatch):
    repo = api.Repository(full_name="org/a", clone_url="https://github.com/org/a.git")
    page = Mock(side_effect=[[repo], api.GitHubAPIError("timeout")])
    monkeypatch.setattr(api, "_get_repository_page", page)
    with pytest.raises(api.GitHubAPIError):
        api.get_organization_repositories("org", "fake", page_size=1)


@pytest.mark.parametrize("value", ["", "   ", 123, None])
def test_model_validation(value):
    with pytest.raises(ValidationError):
        api.Repository(full_name=value, clone_url="https://github.com/org/a.git")


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


def test_clone_local(tmp_path):
    source = tmp_path / "source"
    subprocess.run(["git", "init", str(source)], check=True, capture_output=True)
    (source / "example.py").write_text("print('hello')\n")
    subprocess.run(["git", "-C", str(source), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(source), "-c", "user.name=Test", "-c",
         "user.email=test@example.invalid", "commit", "-m", "test"],
        check=True, capture_output=True,
    )
    repo = api.Repository(full_name="org/a", clone_url=source.as_uri())
    target = clone_repository(repo, tmp_path / "clones")
    assert (target / "example.py").read_text() == "print('hello')\n"
    with pytest.raises(CloneError):
        clone_repository(repo, tmp_path / "clones")


def test_clone_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr("clone.subprocess.run", Mock(side_effect=subprocess.TimeoutExpired("git", 1)))
    repo = api.Repository(full_name="org/a", clone_url="https://github.com/org/a.git")
    with pytest.raises(CloneError):
        clone_repository(repo, tmp_path)


@pytest.mark.parametrize("status,headers,text", [
    (401, {}, "token"), (403, {}, "acceso"), (404, {}, "visible"),
    (429, {}, "límite"), (403, {"X-RateLimit-Remaining": "0"}, "límite"),
    (403, {"Retry-After": "60"}, "límite"), (503, {}, "503"),
])
def test_http_errors(status, headers, text):
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers)
    session = Mock(get=Mock(return_value=response))
    with pytest.raises(api.GitHubHTTPError, match=text) as error:
        api._get_repository_page(session, "org", 1, 10)
    assert error.value.status_code == status


@pytest.mark.parametrize("failure", [requests.Timeout("secret"), requests.ConnectionError("secret")])
def test_network_errors_hide_details(failure):
    with pytest.raises(api.GitHubAPIError) as error:
        api._get_repository_page(Mock(get=Mock(side_effect=failure)), "org", 1, 10)
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("body", [b"not json", b"{}", b'[{}]'])
def test_invalid_response(body):
    response = requests.Response()
    response.status_code = 200
    response._content = body
    with pytest.raises(api.GitHubAPIError):
        api._get_repository_page(Mock(get=Mock(return_value=response)), "org", 1, 10)


def test_cli_api_error(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    monkeypatch.setattr(cli, "get_organization_repositories", Mock(side_effect=api.GitHubAPIError("API unavailable")))
    result = CliRunner().invoke(cli.app, ["list", "org"])
    assert result.exit_code == 1
    assert "API unavailable" in result.output
    assert "fake-token" not in result.output
