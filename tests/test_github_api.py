from unittest.mock import Mock

import pytest
import requests

from core.exceptions import AppException
from miner.clone import github_api as api
from miner.clone.errors import CloneErrors


def test_pagination(monkeypatch):
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(api, "PAGE_SIZE", 1)
    pages = [
        [{"full_name": "org/a", "clone_url": "https://github.com/org/a.git"}], []]
    session.get.side_effect = [
        Mock(json=Mock(return_value=page)) for page in pages]
    monkeypatch.setattr(api.requests, "Session", lambda: session)
    result = api.get_organization_repositories("org", "fake-token")
    assert result[0].full_name == "org/a"
    assert [call.kwargs["params"]["page"]
            for call in session.get.call_args_list] == [1, 2]
    session.headers.update.assert_called_once_with(
        api._build_headers("fake-token"))


def test_failed_page_propagates(monkeypatch):
    monkeypatch.setattr(api, "PAGE_SIZE", 1)
    repo = api.Repository(
        full_name="org/a", clone_url="https://github.com/org/a.git")
    page = Mock(side_effect=[[repo], CloneErrors.GitHubTimeout])
    monkeypatch.setattr(api, "_get_repository_page", page)
    with pytest.raises(AppException) as raised:
        api.get_organization_repositories("org", "fake")
    assert raised.value is CloneErrors.GitHubTimeout


@pytest.mark.parametrize("status,headers,expected", [
    (401, {}, CloneErrors.GitHubUnauthorized),
    (403, {}, CloneErrors.GitHubForbidden),
    (404, {}, CloneErrors.GitHubNotFound),
    (429, {}, CloneErrors.GitHubRateLimit),
    (403, {"X-RateLimit-Remaining": "0"}, CloneErrors.GitHubRateLimit),
    (403, {"Retry-After": "60"}, CloneErrors.GitHubRateLimit),
    (503, {}, CloneErrors.GitHubRequestFailed),
])
def test_http_errors(status, headers, expected):
    response = requests.Response()
    response.status_code = status
    response.headers.update(headers)
    session = Mock(get=Mock(return_value=response))
    with pytest.raises(AppException) as error:
        api._get_repository_page(session, "org", 1, 10)
    assert error.value is expected


@pytest.mark.parametrize(
    "failure,expected",
    [
        (requests.Timeout("secret"), CloneErrors.GitHubTimeout),
        (requests.ConnectionError("secret"), CloneErrors.GitHubRequestFailed),
    ],
)
def test_network_errors_hide_details(failure, expected):
    with pytest.raises(AppException) as error:
        api._get_repository_page(
            Mock(get=Mock(side_effect=failure)), "org", 1, 10)
    assert error.value is expected
    assert "secret" not in str(error.value)


@pytest.mark.parametrize("body", [b"not json", b"{}", b'[{}]'])
def test_invalid_response(body):
    response = requests.Response()
    response.status_code = 200
    response._content = body
    with pytest.raises(AppException) as error:
        api._get_repository_page(
            Mock(get=Mock(return_value=response)), "org", 1, 10)
    assert error.value is CloneErrors.InvalidGitHubResponse
