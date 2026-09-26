import subprocess
from unittest.mock import Mock

import pytest

from core.exceptions import AppException
from miner.clone.clone import clone_repository
from miner.clone.errors import CloneErrors
from miner.clone.models import Repository


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
    repo = Repository(full_name="org/a", clone_url=source.as_uri())
    target = clone_repository(repo, tmp_path / "clones")
    assert (target / "example.py").read_text() == "print('hello')\n"
    with pytest.raises(AppException) as raised:
        clone_repository(repo, tmp_path / "clones")
    assert raised.value is CloneErrors.DestinationAlreadyExists


def test_clone_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr("miner.clone.clone.subprocess.run", Mock(
        side_effect=subprocess.TimeoutExpired("git", 1)))
    repo = Repository(
        full_name="org/a", clone_url="https://github.com/org/a.git")
    with pytest.raises(AppException) as raised:
        clone_repository(repo, tmp_path)
    assert raised.value is CloneErrors.GitCloneTimeout


def test_git_auth_not_in_arguments(tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr("miner.clone.clone.subprocess.run", run)
    clone_repository(Repository(full_name="org/repo", clone_url="https://github.com/org/repo.git"),
                     tmp_path, token="fake-private-token")
    assert "fake-private-token" not in repr(run.call_args.args)
    assert run.call_args.kwargs["env"]["GIT_CONFIG_KEY_0"] == "http.https://github.com/.extraheader"
