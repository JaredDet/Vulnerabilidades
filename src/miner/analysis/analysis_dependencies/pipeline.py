"""Coordina el análisis de vulnerabilidades de SBOM con Grype."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from core.exceptions import AppException
from core.filesystem import create_temporary_directory

from ...clone.loader import load_latest_clones
from ...sbom.constants import (
    SBOM_DIRECTORY,
    SBOM_REPORT_FILENAME,
    SBOM_RUN_PREFIX,
)
from ...sbom.models import SBOMReport, SBOMResult
from .constants import (
    DEFAULT_GRYPE_EXECUTABLE,
    DEFAULT_SCAN_TIMEOUT,
    VULNERABILITY_DIRECTORY,
    VULNERABILITY_REPORT_FILENAME,
    VULNERABILITY_RUN_PREFIX,
)
from .errors import GrypeErrors
from .grype import get_version, scan_vulnerabilities
from .models import GrypeExecution, VulnerabilityReport, VulnerabilityResult
from .report import write_report


def _create_vulnerability_directory(workspace: Path) -> Path:
    """Crea el directorio para una ejecución de vulnerabilidades."""
    return create_temporary_directory(
        workspace / VULNERABILITY_DIRECTORY,
        VULNERABILITY_RUN_PREFIX,
    )


def _find_sbom_runs(sbom_root: Path) -> list[Path]:
    """Encuentra las ejecuciones de SBOM disponibles."""
    if not sbom_root.is_dir():
        raise GrypeErrors.SbomDirectoryNotFound

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
        raise GrypeErrors.SbomRunNotFound

    return directory


def _find_sbom_directory(workspace: Path, run_id: str | None) -> Path:
    """Encuentra la ejecución de SBOM a utilizar."""
    sbom_root = workspace / SBOM_DIRECTORY

    if run_id is not None:
        return _find_sbom_run_by_id(sbom_root, run_id)

    runs = _find_sbom_runs(sbom_root)

    if not runs:
        raise GrypeErrors.SbomRunNotFound

    return runs[0]


def _load_sbom_report(sbom_directory: Path) -> SBOMReport:
    """Carga el reporte de la ejecución de SBOM."""
    report_path = sbom_directory / SBOM_REPORT_FILENAME

    try:
        return SBOMReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise GrypeErrors.InvalidSbomReport from None


def _get_repository_output(
    sbom: SBOMResult,
    output_directory: Path,
) -> Path:
    filename = f"{sbom.full_name.replace('/', '-')}.json"
    return output_directory / filename


def _get_sbom_source(sbom: SBOMResult) -> Path:
    """Obtiene y valida la ruta del SBOM."""
    if sbom.status != "generated":
        raise GrypeErrors.SbomGenerationFailed

    source = Path(sbom.sbom_path)

    if not source.is_file():
        raise GrypeErrors.SbomFileNotFound

    return source


def _create_analyzed_result(
    sbom: SBOMResult,
    execution: GrypeExecution,
    output: Path,
    analysis_date: datetime,
) -> VulnerabilityResult:
    return VulnerabilityResult(
        full_name=sbom.full_name,
        commit=sbom.commit,
        analysis_date=analysis_date,
        grype_version=execution.grype_version,
        status="analyzed",
        vulnerability_count=0,
        report_path=str(output),
    )


def _create_failed_result(
    sbom: SBOMResult,
    execution: GrypeExecution,
    output: Path,
    analysis_date: datetime,
    error: AppException,
) -> VulnerabilityResult:
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


def _process_sbom(
    sbom: SBOMResult,
    execution: GrypeExecution,
) -> VulnerabilityResult:
    output = _get_repository_output(sbom, execution.output_directory)
    analysis_date = datetime.now(UTC)

    try:
        source = _get_sbom_source(sbom)

        scan_vulnerabilities(
            source,
            output,
            executable=execution.executable,
            timeout=execution.timeout,
        )

    except AppException as error:
        return _create_failed_result(
            sbom,
            execution,
            output,
            analysis_date,
            error,
        )

    return _create_analyzed_result(
        sbom,
        execution,
        output,
        analysis_date,
    )


def _get_grype_version(
    repositories: list[SBOMResult],
    executable: str,
) -> str:
    """Obtiene la versión de Grype si existen SBOM generados."""
    if not any(item.status == "generated" for item in repositories):
        return "unknown"

    return get_version(executable)


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


def _create_execution(
    workspace: Path,
    repositories: list[SBOMResult],
    executable: str,
    timeout: float,
) -> GrypeExecution:
    return GrypeExecution(
        output_directory=_create_vulnerability_directory(workspace),
        grype_version=_get_grype_version(repositories, executable),
        executable=executable,
        timeout=timeout,
    )


def _write_reports(
    report: VulnerabilityReport,
    execution: GrypeExecution,
    output: Path,
) -> None:
    write_report(
        report,
        execution.output_directory / VULNERABILITY_REPORT_FILENAME,
    )
    write_report(report, output)


def scan_organization_vulnerabilities(
    organization: str,
    output: Path,
    *,
    workspace: Path | None = None,
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

    clones = load_latest_clones(
        organization,
        workspace_path=workspace,
    )

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

    execution = _create_execution(
        clones.workspace,
        repositories,
        executable,
        timeout,
    )

    report = _process_repositories(
        organization,
        repositories,
        execution,
        progress,
    )

    _write_reports(report, execution, output)

    return report
