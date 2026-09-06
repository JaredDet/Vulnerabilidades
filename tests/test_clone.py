import subprocess
from unittest.mock import Mock

import pytest

from miner import github_api as api
from miner.clone import CloneError, clone_repository
from miner.models import Repository


def test_clone_local(tmp_path):
    source = tmp_path / "source"
    subprocess.run(["git", "init", str(source)],
                   check=True, capture_output=True)
    (source / "example.py").write_text("print('hello')\n")
    subprocess.run(["git", "-C", str(source), "add", "."],
                   check=True, capture_output=True)
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
    monkeypatch.setattr("miner.clone.subprocess.run", Mock(
        side_effect=subprocess.TimeoutExpired("git", 1)))
    repo = api.Repository(
        full_name="org/a", clone_url="https://github.com/org/a.git")
    with pytest.raises(CloneError):
        clone_repository(repo, tmp_path)


def test_git_auth_not_in_arguments(tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr("miner.clone.subprocess.run", run)
    clone_repository(Repository(full_name="org/repo", clone_url="https://github.com/org/repo.git"),
                     tmp_path, token="fake-private-token")
    assert "fake-private-token" not in repr(run.call_args.args)
    assert run.call_args.kwargs["env"]["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
