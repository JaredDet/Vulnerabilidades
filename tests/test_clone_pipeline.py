import os
from unittest.mock import Mock

import pytest

from core.exceptions import AppException
from miner.clone import loader, pipeline
from miner.clone.errors import CloneErrors
from miner.clone.models import CloneResult, OrganizationCloneResult, Repository


def save_clones(root, organization="org", *, timestamp=100):
    source = root / "repositories" / organization / "repo"
    (source / ".git").mkdir(parents=True)
    clones = OrganizationCloneResult(
        organization=organization,
        workspace=root,
        repositories=[CloneResult(
            repository=Repository(
                full_name=f"{organization}/repo",
                clone_url=f"https://github.com/{organization}/repo.git",
            ),
            source=source,
        )],
    )
    manifest = root / "clones.json"
    manifest.write_text(clones.model_dump_json(), encoding="utf-8")
    os.utime(manifest, (timestamp, timestamp))
    return clones


def test_latest_clones_uses_completion_date_not_analysis_date(tmp_path):
    old = save_clones(tmp_path / "clone-z", timestamp=100)
    latest = save_clones(tmp_path / "clone-a", timestamp=200)
    (old.workspace / "codeql-new").mkdir()
    (tmp_path / "clone-incomplete").mkdir()
    assert loader.load_latest_clones("org", workspace_path=tmp_path) == latest


def test_explicit_folder_selects_older_clones(tmp_path):
    old = save_clones(tmp_path / "clone-old", timestamp=100)
    save_clones(tmp_path / "clone-new", timestamp=200)
    assert loader.load_latest_clones("org", workspace_path=tmp_path, run_id="old") == old


def test_default_workspace_is_scoped_to_organization(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    expected = save_clones(tmp_path / "organizations" / "org" / "work" / "clone-a")
    save_clones(tmp_path / "organizations" / "other" / "work" / "clone-b", "other", timestamp=500)
    assert loader.load_latest_clones("org") == expected


@pytest.mark.parametrize("run_id", [None, "legacy"])
def test_legacy_scan_folders_are_not_clone_runs(tmp_path, run_id):
    source = tmp_path / "scan-legacy" / "repositories" / "org" / "repo"
    (source / ".git").mkdir(parents=True)

    with pytest.raises(AppException) as raised:
        loader.load_latest_clones("org", workspace_path=tmp_path, run_id=run_id)

    expected = CloneErrors.CloneNotFound if run_id is None else CloneErrors.RunNotFound
    assert raised.value is expected


def test_manifest_organization_must_match(tmp_path):
    save_clones(tmp_path / "clone-other", "other")
    with pytest.raises(AppException) as raised:
        loader.load_latest_clones("org", workspace_path=tmp_path)
    assert raised.value is CloneErrors.WrongOrganization


def test_invalid_latest_manifest_is_not_silently_skipped(tmp_path):
    save_clones(tmp_path / "clone-old", timestamp=100)
    latest = save_clones(tmp_path / "clone-new", timestamp=200)
    (latest.workspace / "clones.json").write_text("invalid", encoding="utf-8")
    with pytest.raises(AppException) as raised:
        loader.load_latest_clones("org", workspace_path=tmp_path)
    assert raised.value is CloneErrors.InvalidCloneManifest


def test_clone_persists_result_for_later_analysis(tmp_path, monkeypatch):
    repository = Repository(full_name="org/repo", clone_url="https://github.com/org/repo.git")
    monkeypatch.setattr(pipeline, "get_organization_repositories", Mock(return_value=[repository]))
    monkeypatch.setattr(pipeline, "clone_repository", Mock(return_value=tmp_path / "source"))
    result = pipeline.clone_organization(
        "org", "test-token", workspace_path=tmp_path, progress=lambda _: None,
    )
    restored = loader.load_latest_clones("org", workspace_path=tmp_path)
    assert restored == result
    assert "test-token" not in (result.workspace / "clones.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("run_id", ["../existing", "scan/existing", "C:\\work", ""])
def test_run_id_cannot_be_a_path(tmp_path, run_id):
    save_clones(tmp_path / "clone-existing")
    with pytest.raises(AppException) as raised:
        loader.load_latest_clones("org", workspace_path=tmp_path, run_id=run_id)
    assert raised.value is CloneErrors.InvalidRunId


def test_unknown_id_does_not_fall_back_to_latest(tmp_path):
    save_clones(tmp_path / "clone-existing")
    with pytest.raises(AppException) as raised:
        loader.load_latest_clones("org", workspace_path=tmp_path, run_id="missing")
    assert raised.value is CloneErrors.RunNotFound
