import json
import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from core.exceptions import AppException
from miner import cli
from miner.clone.models import CloneResult, OrganizationCloneResult, Repository
from miner.sbom.errors import SBOMErrors
from miner.sbom import pipeline
from miner.sbom.models import SBOMReport


def save_clones(root, names=("b", "a"), timestamp=100):
    root.mkdir(parents=True)
    items = []
    for name in names:
        source = root / "repositories" / "org" / name
        (source / ".git").mkdir(parents=True)
        items.append(CloneResult(
            repository=Repository(full_name=f"org/{name}", clone_url=f"https://github.com/org/{name}.git"),
            source=source,
        ))
    clones = OrganizationCloneResult(organization="org", workspace=root, repositories=items)
    manifest = root / "clones.json"
    manifest.write_text(clones.model_dump_json(), encoding="utf-8")
    os.utime(manifest, (timestamp, timestamp))
    return clones


@pytest.fixture
def dependencies(monkeypatch):
    version = Mock(return_value="1.0.0")
    commit = Mock(return_value="abc123")

    def generate(source, output, **kwargs):
        assert not output.exists()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"bomFormat": "CycloneDX", "components": [{"name": "example"}]}))
        return output

    generator = Mock(side_effect=generate)
    monkeypatch.setattr(pipeline, "get_version", version)
    monkeypatch.setattr(pipeline, "_get_commit", commit)
    monkeypatch.setattr(pipeline, "generate_sbom", generator)
    return version, commit, generator


def test_latest_clone_and_repeat_preserve_previous_artifacts(tmp_path, dependencies):
    save_clones(tmp_path / "clone-z", timestamp=100)
    newest = save_clones(tmp_path / "clone-a", timestamp=200)
    first = pipeline.generate_organization_sbom("org", tmp_path / "out.json", workspace=tmp_path)
    second = pipeline.generate_organization_sbom("org", tmp_path / "out.json", workspace=tmp_path)
    assert [item.full_name for item in first.repositories] == ["org/a", "org/b"]
    assert all(item.status == "generated" and item.component_count == 1 for item in first.repositories)
    assert first.repositories[0].sbom_path != second.repositories[0].sbom_path
    assert all(Path(item.sbom_path).is_file() for item in first.repositories + second.repositories)
    assert all(Path(item.sbom_path).is_relative_to(newest.workspace) for item in second.repositories)
    assert SBOMReport.model_validate_json((tmp_path / "out.json").read_text()) == second


def test_legacy_scan_and_explicit_id(tmp_path, dependencies):
    save_clones(tmp_path / "clone-old", names=("legacy",))
    save_clones(tmp_path / "clone-new")
    report = pipeline.generate_organization_sbom("org", tmp_path / "out.json", workspace=tmp_path, run_id="old")
    assert [item.full_name for item in report.repositories] == ["org/legacy"]


@pytest.mark.parametrize("contents", ["[]", "null", "{}", "invalid", '{"bomFormat":"CycloneDX","components":{}}', '{"bomFormat":"CycloneDX","components":[null]}'])
def test_invalid_sbom_does_not_stop_other_repositories(tmp_path, dependencies, contents):
    save_clones(tmp_path / "clone-one")
    generator = dependencies[2]
    valid = generator.side_effect

    def generate(source, output, **kwargs):
        if source.name == "a":
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(contents)
            return output
        return valid(source, output, **kwargs)

    generator.side_effect = generate
    report = pipeline.generate_organization_sbom("org", tmp_path / "out.json", workspace=tmp_path)
    assert [item.status for item in report.repositories] == ["failed", "generated"]
    assert report.repositories[0].commit == "unknown"


def test_empty_report_is_written_without_syft(tmp_path, dependencies):
    save_clones(tmp_path / "clone-empty", names=())
    output = tmp_path / "out.json"
    output.write_text("old report")
    report = pipeline.generate_organization_sbom("org", output, workspace=tmp_path)
    assert json.loads(output.read_text())["repositories"] == []
    assert report.repositories == []
    dependencies[0].assert_not_called()
    dependencies[2].assert_not_called()


def test_failed_clone_remains_in_report(tmp_path, dependencies):
    clones = save_clones(tmp_path / "clone-one")
    clones.repositories[0].source = None
    clones.repositories[0].error = "clone failed"
    (clones.workspace / "clones.json").write_text(clones.model_dump_json())
    report = pipeline.generate_organization_sbom("org", tmp_path / "out.json", workspace=tmp_path)
    assert [item.status for item in report.repositories] == ["generated", "failed"]
    assert report.repositories[1].error == SBOMErrors.CloneFailed.message
    assert dependencies[2].call_count == 1


def test_syft_unavailable_preserves_report(tmp_path, dependencies):
    save_clones(tmp_path / "clone-one")
    output = tmp_path / "out.json"
    output.write_text("existing report")
    dependencies[0].side_effect = SBOMErrors.SyftNotAvailable
    with pytest.raises(AppException) as raised:
        pipeline.generate_organization_sbom("org", output, workspace=tmp_path)
    assert raised.value is SBOMErrors.SyftNotAvailable
    assert output.read_text() == "existing report"


def test_cli_sbom_uses_clones_without_token_or_cloning(tmp_path, monkeypatch, dependencies):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    save_clones(tmp_path / "organizations" / "org" / "work" / "clone-one")
    clone = Mock(side_effect=AssertionError("must not clone"))
    monkeypatch.setattr(cli, "clone_organization", clone)
    result = CliRunner().invoke(cli.app, [
        "generate-sbom", "-o", "org", "--run-id", "one", "--syft", "custom-syft", "--timeout", "42",
    ])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "sbom-results.json").is_file()
    dependencies[0].assert_called_once_with("custom-syft")
    assert dependencies[2].call_args.kwargs == {"executable": "custom-syft", "timeout": 42}
    clone.assert_not_called()


def test_cli_missing_clones_returns_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(cli.app, ["generate-sbom", "-o", "org"])
    assert result.exit_code == 4
    assert not (tmp_path / "sbom-results.json").exists()
