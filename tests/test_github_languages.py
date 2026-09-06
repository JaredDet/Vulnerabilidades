from unittest.mock import Mock

import pytest

import github_api as api


@pytest.mark.parametrize("data,expected", [({}, []), ({"Python": 20, "HTML": 5}, ["HTML", "Python"])])
def test_languages(monkeypatch, data, expected):
    get = Mock(return_value=data)
    monkeypatch.setattr(api, "_get_json", get)
    assert api.get_repository_languages("org/repo", "test-token") == expected
    assert get.call_args.args[1] == "/repos/org/repo/languages"


@pytest.mark.parametrize("data", [[], {"Python": -1}, {"Python": "1"}, {"Python": True}])
def test_invalid_languages(monkeypatch, data):
    monkeypatch.setattr(api, "_get_json", Mock(return_value=data))
    with pytest.raises(api.GitHubAPIError):
        api.get_repository_languages("org/repo", "test-token")
