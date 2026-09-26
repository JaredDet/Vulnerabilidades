import subprocess
from unittest.mock import Mock

import pytest

from core.exceptions import AppException
from miner.dependencies import grype
from miner.dependencies.errors import GrypeErrors


def test_get_version_uses_selected_executable(monkeypatch):
    run = Mock(return_value=Mock(stdout="  0.80.0  \n"))
    monkeypatch.setattr(grype.subprocess, "run", run)

    assert grype.get_version("custom-grype") == "0.80.0"
    assert run.call_args.args[0] == ["custom-grype", "version"]
    assert run.call_args.kwargs["check"] is True
    assert run.call_args.kwargs["capture_output"] is True
    assert run.call_args.kwargs["text"] is True
    assert run.call_args.kwargs["timeout"] > 0


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (FileNotFoundError(), GrypeErrors.GrypeNotAvailable),
        (subprocess.TimeoutExpired("grype", 1), GrypeErrors.VersionTimeout),
        (subprocess.CalledProcessError(1, "grype"), GrypeErrors.VersionFailed),
        (PermissionError(), GrypeErrors.GrypeAccessFailed),
    ],
)
def test_get_version_maps_process_errors(monkeypatch, failure, expected):
    monkeypatch.setattr(grype.subprocess, "run", Mock(side_effect=failure))

    with pytest.raises(AppException) as raised:
        grype.get_version()

    assert raised.value is expected


@pytest.mark.parametrize("stdout", ["", "  "])
def test_get_version_rejects_empty_response(monkeypatch, stdout):
    monkeypatch.setattr(grype.subprocess, "run", Mock(return_value=Mock(stdout=stdout)))

    with pytest.raises(AppException) as raised:
        grype.get_version()

    assert raised.value is GrypeErrors.InvalidVersionResponse


def test_scan_vulnerabilities_builds_command_and_returns_output(tmp_path, monkeypatch):
    sbom = tmp_path / "source sbom.json"
    sbom.write_text("{}", encoding="utf-8")
    output = tmp_path / "results" / "vulnerabilities.json"

    def run(*_args, **_kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("{}", encoding="utf-8")

    process = Mock(side_effect=run)
    monkeypatch.setattr(grype.subprocess, "run", process)

    result = grype.scan_vulnerabilities(
        sbom,
        output,
        executable="custom-grype",
        timeout=42,
    )

    assert result == output.resolve()
    assert process.call_args.args[0] == [
        "custom-grype",
        f"sbom:{sbom.resolve()}",
        f"--file={output.resolve()}",
        "--output=json",
    ]
    assert process.call_args.kwargs["timeout"] == 42


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (FileNotFoundError(), GrypeErrors.GrypeNotAvailable),
        (subprocess.TimeoutExpired("grype", 1), GrypeErrors.ScanTimeout),
        (subprocess.CalledProcessError(1, "grype"), GrypeErrors.ScanFailed),
        (PermissionError(), GrypeErrors.GrypeAccessFailed),
    ],
)
def test_scan_vulnerabilities_maps_process_errors(
    tmp_path, monkeypatch, failure, expected
):
    sbom = tmp_path / "sbom.json"
    sbom.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(grype.subprocess, "run", Mock(side_effect=failure))

    with pytest.raises(AppException) as raised:
        grype.scan_vulnerabilities(sbom, tmp_path / "out.json")

    assert raised.value is expected


def test_scan_vulnerabilities_validates_inputs_before_running(tmp_path, monkeypatch):
    process = Mock()
    monkeypatch.setattr(grype.subprocess, "run", process)

    with pytest.raises(AppException) as invalid_timeout:
        grype.scan_vulnerabilities(tmp_path / "missing.json", tmp_path / "out.json", timeout=0)
    assert invalid_timeout.value is GrypeErrors.InvalidTimeout

    with pytest.raises(AppException) as missing:
        grype.scan_vulnerabilities(tmp_path / "missing.json", tmp_path / "out.json")
    assert missing.value is GrypeErrors.SBOMFileNotFound

    sbom = tmp_path / "sbom.json"
    sbom.write_text("{}", encoding="utf-8")
    output = tmp_path / "existing.json"
    output.write_text("{}", encoding="utf-8")
    with pytest.raises(AppException) as exists:
        grype.scan_vulnerabilities(sbom, output)
    assert exists.value is GrypeErrors.ResultAlreadyExists
    process.assert_not_called()


def test_scan_vulnerabilities_requires_grype_to_create_output(tmp_path, monkeypatch):
    sbom = tmp_path / "sbom.json"
    sbom.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(grype.subprocess, "run", Mock())

    with pytest.raises(AppException) as raised:
        grype.scan_vulnerabilities(sbom, tmp_path / "out.json")

    assert raised.value is GrypeErrors.ResultsNotGenerated
