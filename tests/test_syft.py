import subprocess
from unittest.mock import Mock

import pytest

from miner.sbom import syft


def test_generate_sbom_command(tmp_path, monkeypatch):
    source = tmp_path / "source with spaces"
    source.mkdir()
    output = tmp_path / "results" / "sbom.json"
    run = Mock(side_effect=lambda *args, **kwargs: output.write_text('{"bomFormat":"CycloneDX"}'))
    monkeypatch.setattr(syft.subprocess, "run", run)
    assert syft.generate_sbom(source, output, executable="custom-syft", timeout=42) == output.resolve()
    assert run.call_args.args[0] == ["custom-syft", "scan", str(source.resolve()), f"--output=cyclonedx-json={output.resolve()}"]
    assert run.call_args.kwargs["timeout"] == 42
    with pytest.raises(syft.SyftError, match="ya existe"):
        syft.generate_sbom(source, output)


@pytest.mark.parametrize("failure", [None, FileNotFoundError(), subprocess.TimeoutExpired("syft", 1), subprocess.CalledProcessError(2, "syft")])
def test_generation_failure(tmp_path, monkeypatch, failure):
    source = tmp_path / "source"
    source.mkdir()
    monkeypatch.setattr(syft.subprocess, "run", Mock(side_effect=failure))
    with pytest.raises(syft.SyftError):
        syft.generate_sbom(source, tmp_path / "sbom.json")


def test_paths_and_timeout_are_checked(tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr(syft.subprocess, "run", run)
    with pytest.raises(syft.SyftError):
        syft.generate_sbom(tmp_path / "missing", tmp_path / "out.json")
    with pytest.raises(syft.SyftError):
        syft.generate_sbom(tmp_path, tmp_path / "out.json")
    with pytest.raises(ValueError):
        syft.generate_sbom(tmp_path, tmp_path / "out.json", timeout=0)
    run.assert_not_called()


def test_version(monkeypatch):
    run = Mock(return_value=Mock(stdout='{"version":" 1.0.0 "}'))
    monkeypatch.setattr(syft.subprocess, "run", run)
    assert syft.get_version("custom-syft") == "1.0.0"
    assert run.call_args.args[0] == ["custom-syft", "version", "--output", "json"]
    assert run.call_args.kwargs["timeout"] == 30


@pytest.mark.parametrize("contents", ["invalid", "[]", "null", "{}", '{"version":null}', '{"version":" "}'])
def test_invalid_version(monkeypatch, contents):
    monkeypatch.setattr(syft.subprocess, "run", Mock(return_value=Mock(stdout=contents)))
    with pytest.raises(syft.SyftError):
        syft.get_version()


def test_version_timeout(monkeypatch):
    monkeypatch.setattr(syft.subprocess, "run", Mock(side_effect=subprocess.TimeoutExpired("syft", 30)))
    with pytest.raises(syft.SyftError):
        syft.get_version()
