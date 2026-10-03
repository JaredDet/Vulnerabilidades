"""Coordina el análisis de vulnerabilidades de SBOM con Grype."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from core.exceptions import AppException
from core.filesystem import create_temporary_directory
from core.reporting import write_json_report

from ..clone.pipeline import load_latest_clones
from ..sbom.constants import (
    SBOM_DIRECTORY,
    SBOM_REPORT_FILENAME,
    SBOM_RUN_PREFIX,
)
from ..sbom.models import SBOMReport, SBOMResult
from .constants import (
    DEFAULT_GRYPE_EXECUTABLE,
    DEFAULT_SCAN_TIMEOUT,
    VULNERABILITY_DIRECTORY,
    VULNERABILITY_REPORT_FILENAME,
    VULNERABILITY_RUN_PREFIX,
)
from .errors import GrypeErrors
from .grype import get_version, scan_vulnerabilities
from .models import (
    GrypeExecution,
    VulnerabilityReport,
    VulnerabilityResult,
)
from .parser import parse_grype


def _find_sbom_runs(sbom_root: Path) -> list[Path]:
    """Encuentra las ejecuciones de SBOM disponibles."""
    if not sbom_root.is_dir():
        raise GrypeErrors.SBOMDirectoryNotFound

    return sorted(
        (
            directory
            for directory in sbom_root.iterdir()
            if directory.is_dir() and directory.name.startswith(SBOM_RUN_PREFIX)
        ),
        key=lambda directory: directory.stat().st_mtime_ns,
        reverse=True,
    )


def _find_sbom_run_by_id(sbom_root: Path, run_id: str) -> Path:
    """Encuentra una ejecución de SBOM por su identificador."""
    directory = sbom_root / (
        run_id if run_id.startswith(SBOM_RUN_PREFIX) else f"{SBOM_RUN_PREFIX}{run_id}"
    )

    if not directory.is_dir():
        raise GrypeErrors.SBOMRunNotFound

    return directory


def _find_sbom_directory(workspace: Path, run_id: str | None) -> Path:
    """Encuentra la ejecución de SBOM a utilizar."""
    sbom_root = workspace / SBOM_DIRECTORY

    if run_id is not None:
        return _find_sbom_run_by_id(sbom_root, run_id)

    runs = _find_sbom_runs(sbom_root)

    if not runs:
        raise GrypeErrors.SBOMRunNotFound

    return runs[0]


def _load_sbom_report(sbom_directory: Path) -> SBOMReport:
    """Carga el reporte de la ejecución de SBOM."""
    report_path = sbom_directory / SBOM_REPORT_FILENAME

    try:
        return SBOMReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise GrypeErrors.InvalidSBOMReport from None


def _order_report(result: VulnerabilityReport) -> None:
    result.repositories.sort(key=lambda repository: repository.full_name)


def write_report(result: VulnerabilityReport, output: Path) -> Path:
    """Escribe el reporte validado de forma atómica."""
    return write_json_report(result, output, order=_order_report)


def _process_sbom(
    sbom: SBOMResult,
    execution: GrypeExecution,
) -> VulnerabilityResult:
    """Analiza un SBOM y conserva los fallos del repositorio en el reporte."""
    output = execution.output_directory / f"{sbom.full_name.replace('/', '-')}.json"
    analysis_date = datetime.now(UTC)

    try:
        if sbom.status != "generated":
            raise GrypeErrors.SBOMGenerationFailed

        source = Path(sbom.sbom_path)
        scan_vulnerabilities(
            source,
            output,
            executable=execution.executable,
            timeout=execution.timeout,
        )
        findings = parse_grype(output)
    except AppException as error:
        return VulnerabilityResult(
            full_name=sbom.full_name,
            commit=sbom.commit,
            analysis_date=analysis_date,
            grype_version=execution.grype_version,
            status="failed",
            vulnerability_count=0,
            report_path=str(output),
            error=error.message,
        )

    return VulnerabilityResult(
        full_name=sbom.full_name,
        commit=sbom.commit,
        analysis_date=analysis_date,
        grype_version=execution.grype_version,
        status="analyzed",
        vulnerability_count=len(findings),
        findings=findings,
        report_path=str(output),
    )


def _process_repositories(
    organization: str,
    repositories: list[SBOMResult],
    execution: GrypeExecution,
    progress: Callable[[str], None],
) -> VulnerabilityReport:
    """Analiza los SBOM de los repositorios."""
    report = VulnerabilityReport(
        organization=organization,
        repositories=[],
    )

    for index, sbom in enumerate(repositories, 1):
        progress(f"[{index}/{len(repositories)}] {sbom.full_name}")

        result = _process_sbom(sbom, execution)
        report.repositories.append(result)

        progress(f"  {result.status}" + (f": {result.error}" if result.error else ""))

    return report


def scan_organization_vulnerabilities(
    organization: str,
    output: Path,
    *,
    workspace: Path | None = None,
    clone_run_id: str | None = None,
    run_id: str | None = None,
    executable: str = DEFAULT_GRYPE_EXECUTABLE,
    timeout: float = DEFAULT_SCAN_TIMEOUT,
    progress: Callable[[str], None] = print,
) -> VulnerabilityReport:
    """Analiza las vulnerabilidades del último SBOM de una organización."""
    organization = organization.strip()

    if not organization:
        raise GrypeErrors.OrganizationRequired

    if timeout <= 0:
        raise GrypeErrors.InvalidTimeout

    clone_options = {"workspace_path": workspace}
    if clone_run_id is not None:
        clone_options["run_id"] = clone_run_id
    clones = load_latest_clones(organization, **clone_options)

    progress(f"Clones: {clones.workspace}")

    sbom_directory = _find_sbom_directory(
        clones.workspace,
        run_id,
    )

    progress(f"SBOM: {sbom_directory}")

    sbom_report = _load_sbom_report(sbom_directory)

    repositories = sorted(
        sbom_report.repositories,
        key=lambda item: item.full_name,
    )

    output_directory = create_temporary_directory(
        clones.workspace / VULNERABILITY_DIRECTORY,
        VULNERABILITY_RUN_PREFIX,
    )
    grype_version = (
        get_version(executable)
        if any(item.status == "generated" for item in repositories)
        else "unknown"
    )
    execution = GrypeExecution(
        output_directory=output_directory,
        grype_version=grype_version,
        executable=executable,
        timeout=timeout,
    )

    report = _process_repositories(
        organization,
        repositories,
        execution,
        progress,
    )

    write_report(report, output_directory / VULNERABILITY_REPORT_FILENAME)
    write_report(report, output)

    return report
