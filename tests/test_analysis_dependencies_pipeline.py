import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.exceptions import AppException
from miner.analysis.analysis_dependencies import pipeline
from miner.analysis.analysis_dependencies.constants import (
    VULNERABILITY_REPORT_FILENAME,
)
from miner.analysis.analysis_dependencies.errors import GrypeErrors
from miner.analysis.analysis_dependencies.models import VulnerabilityReport
from miner.clone.models import OrganizationCloneResult
from miner.sbom.constants import SBOM_DIRECTORY, SBOM_REPORT_FILENAME, SBOM_RUN_PREFIX
from miner.sbom.models import SBOMReport, SBOMResult


def _write_sbom_report(
    workspace: Path,
    run_name: str,
    repositories: list[SBOMResult],
    *,
    timestamp: int = 100,
) -> Path:
    run = workspace / SBOM_DIRECTORY / run_name
    run.mkdir(parents=True)
    report = SBOMReport(organization="org", repositories=repositories)
    (run / SBOM_REPORT_FILENAME).write_text(report.model_dump_json(), encoding="utf-8")
    os.utime(run, (timestamp, timestamp))
    return run


def _sbom_result(workspace: Path, name: str, *, status: str = "generated") -> SBOMResult:
    source = workspace / "sbom-files" / f"{name}.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("{}", encoding="utf-8")
    return SBOMResult(
        full_name=f"org/{name}",
        commit="abc123",
        generation_date=datetime(2026, 1, 1, tzinfo=UTC),
        syft_version="1.0.0",
        status=status,
        component_count=1 if status == "generated" else 0,
        sbom_path=str(source),
        error=None if status == "generated" else "generation failed",
    )


@pytest.fixture
def setup_scan(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    clones = OrganizationCloneResult(
        organization="org",
        workspace=workspace,
        repositories=[],
    )
    load = Mock(return_value=clones)
    version = Mock(return_value="0.80.0")
    scan = Mock()

    def create_result(_sbom, output, **_kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("{}", encoding="utf-8")
        return output

    scan.side_effect = create_result
    monkeypatch.setattr(pipeline, "load_latest_clones", load)
    monkeypatch.setattr(pipeline, "get_version", version)
    monkeypatch.setattr(pipeline, "scan_vulnerabilities", scan)
    return workspace, load, version, scan


def test_scan_organization_orders_results_and_writes_reports(tmp_path, setup_scan):
    workspace, load, version, scan = setup_scan
    _write_sbom_report(
        workspace,
        f"{SBOM_RUN_PREFIX}run",
        [_sbom_result(workspace, "z"), _sbom_result(workspace, "a")],
    )
    output = tmp_path / "summary.json"

    report = pipeline.scan_organization_vulnerabilities(
        "org",
        output,
        workspace=tmp_path,
        executable="custom-grype",
        timeout=37,
        progress=lambda _message: None,
    )

    assert [item.full_name for item in report.repositories] == ["org/a", "org/z"]
    assert all(item.status == "analyzed" for item in report.repositories)
    assert all(item.grype_version == "0.80.0" for item in report.repositories)
    assert VulnerabilityReport.model_validate_json(output.read_text()) == report
    assert (Path(report.repositories[0].report_path).parent / VULNERABILITY_REPORT_FILENAME).is_file()
    load.assert_called_once_with("org", workspace_path=tmp_path)
    version.assert_called_once_with("custom-grype")
    assert scan.call_count == 2
    assert scan.call_args.kwargs == {"executable": "custom-grype", "timeout": 37}


def test_scan_organization_selects_explicit_sbom_run(tmp_path, setup_scan):
    workspace, load, _version, _scan = setup_scan
    older = _write_sbom_report(
        workspace,
        f"{SBOM_RUN_PREFIX}older",
        [_sbom_result(workspace, "old")],
        timestamp=100,
    )
    _write_sbom_report(
        workspace,
        f"{SBOM_RUN_PREFIX}newer",
        [_sbom_result(workspace, "new")],
        timestamp=200,
    )

    report = pipeline.scan_organization_vulnerabilities(
        "org",
        tmp_path / "summary.json",
        run_id="older",
        progress=lambda _message: None,
    )

    assert older.name.endswith("older")
    assert [item.full_name for item in report.repositories] == ["org/old"]
    assert load.call_args.kwargs == {"workspace_path": None}


def test_scan_organization_continues_after_repository_failure(tmp_path, setup_scan):
    workspace, _load, _version, scan = setup_scan
    _write_sbom_report(
        workspace,
        f"{SBOM_RUN_PREFIX}run",
        [_sbom_result(workspace, "a"), _sbom_result(workspace, "b")],
    )
    scan.side_effect = [GrypeErrors.ScanFailed, lambda _sbom, output, **_kwargs: output]

    report = pipeline.scan_organization_vulnerabilities(
        "org", tmp_path / "summary.json", progress=lambda _message: None
    )

    assert [item.status for item in report.repositories] == ["failed", "analyzed"]
    assert report.repositories[0].error == GrypeErrors.ScanFailed.message


def test_scan_organization_skips_version_when_no_generated_sboms(tmp_path, setup_scan):
    workspace, _load, version, scan = setup_scan
    _write_sbom_report(
        workspace,
        f"{SBOM_RUN_PREFIX}run",
        [_sbom_result(workspace, "a", status="failed")],
    )

    report = pipeline.scan_organization_vulnerabilities(
        "org", tmp_path / "summary.json", progress=lambda _message: None
    )

    assert report.repositories[0].status == "failed"
    assert report.repositories[0].grype_version == "unknown"
    version.assert_not_called()
    scan.assert_not_called()


@pytest.mark.parametrize(
    ("organization", "timeout", "expected"),
    [
        (" ", 60, GrypeErrors.OrganizationRequired),
        ("org", 0, GrypeErrors.InvalidTimeout),
    ],
)
def test_scan_organization_validates_before_loading(
    tmp_path, setup_scan, organization, timeout, expected
):
    _workspace, load, _version, _scan = setup_scan

    with pytest.raises(AppException) as raised:
        pipeline.scan_organization_vulnerabilities(
            organization,
            tmp_path / "summary.json",
            timeout=timeout,
        )

    assert raised.value is expected
    load.assert_not_called()


def test_find_sbom_run_reports_missing_directory_and_run(tmp_path):
    with pytest.raises(AppException) as missing_directory:
        pipeline._find_sbom_directory(tmp_path, None)
    assert missing_directory.value is GrypeErrors.SbomDirectoryNotFound

    sbom_root = tmp_path / SBOM_DIRECTORY
    sbom_root.mkdir()
    with pytest.raises(AppException) as missing_run:
        pipeline._find_sbom_directory(tmp_path, "missing")
    assert missing_run.value is GrypeErrors.SbomRunNotFound
