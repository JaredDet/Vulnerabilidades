import os
from unittest.mock import Mock

import pytest

from miner.clone import pipeline
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
    (old.workspace / "analysis-new").mkdir()
    (tmp_path / "clone-incomplete").mkdir()
    assert pipeline.load_latest_clones("org", workspace=tmp_path) == latest


def test_explicit_folder_selects_older_clones(tmp_path):
    old = save_clones(tmp_path / "clone-old", timestamp=100)
    save_clones(tmp_path / "clone-new", timestamp=200)
    assert pipeline.load_latest_clones("org", workspace=tmp_path, run_id="old") == old


def test_default_workspace_is_scoped_to_organization(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    expected = save_clones(tmp_path / "organizations" / "org" / "work" / "clone-a")
    save_clones(tmp_path / "organizations" / "other" / "work" / "clone-b", "other", timestamp=500)
    assert pipeline.load_latest_clones("org") == expected


@pytest.mark.parametrize("explicit", [False, True])
def test_legacy_scan_folders(tmp_path, explicit):
    root = tmp_path / "scan-legacy"
    source = root / "repositories" / "org" / "repo"
    (source / ".git").mkdir(parents=True)
    (root / "repositories" / "org" / "incomplete").mkdir()
    clones = pipeline.load_latest_clones("org", workspace=tmp_path, run_id="legacy" if explicit else None)
    assert clones.workspace == root
    assert clones.cloned == 1
    assert clones.repositories[0].source == source
    assert clones.repositories[0].repository.full_name == "org/repo"


def test_manifest_organization_must_match(tmp_path):
    save_clones(tmp_path / "clone-other", "other")
    with pytest.raises(ValueError, match="otra organización"):
        pipeline.load_latest_clones("org", workspace=tmp_path)


def test_invalid_latest_manifest_is_not_silently_skipped(tmp_path):
    save_clones(tmp_path / "clone-old", timestamp=100)
    latest = save_clones(tmp_path / "clone-new", timestamp=200)
    (latest.workspace / "clones.json").write_text("invalid", encoding="utf-8")
    with pytest.raises(ValueError):
        pipeline.load_latest_clones("org", workspace=tmp_path)


def test_clone_persists_result_for_later_analysis(tmp_path, monkeypatch):
    repository = Repository(full_name="org/repo", clone_url="https://github.com/org/repo.git")
    monkeypatch.setattr(pipeline, "get_organization_repositories", Mock(return_value=[repository]))
    monkeypatch.setattr(pipeline, "clone_repository", Mock(return_value=tmp_path / "source"))
    result = pipeline.clone_organization(
        "org", "test-token", workspace=tmp_path, progress=lambda _: None,
    )
    restored = pipeline.load_latest_clones("org", workspace=tmp_path)
    assert restored == result
    assert "test-token" not in (result.workspace / "clones.json").read_text(encoding="utf-8")


@pytest.mark.parametrize("run_id", ["../existing", "scan/existing", "C:\\work", ""])
def test_run_id_cannot_be_a_path(tmp_path, run_id):
    save_clones(tmp_path / "clone-existing")
    with pytest.raises(ValueError, match="--run-id"):
        pipeline.load_latest_clones("org", workspace=tmp_path, run_id=run_id)


def test_unknown_id_does_not_fall_back_to_latest(tmp_path):
    save_clones(tmp_path / "clone-existing")
    with pytest.raises(ValueError, match="missing"):
        pipeline.load_latest_clones("org", workspace=tmp_path, run_id="missing")
