"""Coordina el análisis de vulnerabilidades de SBOM con Grype."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import mkdtemp

from ...clone.pipeline import load_latest_clones
from ...sbom.models import SBOMReport, SBOMResult
from .grype import get_version, scan_vulnerabilities
from .models import VulnerabilityReport, VulnerabilityResult
from .report import write_report


def _create_vulnerability_directory(
    workspace: Path,
) -> Path:
    """Crea el directorio para una ejecución de vulnerabilidades."""
    vulnerability_root = (workspace / "vulnerabilities").resolve()
    vulnerability_root.mkdir(parents=True, exist_ok=True)

    return Path(
        mkdtemp(
            prefix="vulnerability-",
            dir=vulnerability_root,
        )
    ).resolve()


def _load_sbom_report(
    sbom_directory: Path,
) -> SBOMReport:
    """Carga el reporte de la ejecución de SBOM."""
    report_path = sbom_directory / "sbom-results.json"

    try:
        return SBOMReport.model_validate_json(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RuntimeError("No se pudo leer el reporte de SBOM") from None


def _find_sbom_directory(
    workspace: Path,
    run_id: str | None,
) -> Path:
    """Encuentra la ejecución de SBOM a utilizar."""
    sbom_root = (workspace / "sboms").resolve()

    if not sbom_root.is_dir():
        raise RuntimeError("No existe el directorio de SBOMs")

    if run_id is not None:
        sbom_directory = sbom_root / f"sbom-{run_id}"

        if not sbom_directory.is_dir():
            raise RuntimeError(f"No se encontró la ejecución de SBOM: sbom-{run_id}")

        return sbom_directory

    sbom_directories = sorted(
        (
            directory
            for directory in sbom_root.iterdir()
            if directory.is_dir() and directory.name.startswith("sbom-")
        ),
        key=lambda directory: directory.stat().st_mtime,
        reverse=True,
    )

    if not sbom_directories:
        raise RuntimeError("No se encontró ninguna ejecución de SBOM")

    return sbom_directories[0]


def _process_sbom(
    sbom: SBOMResult,
    output_directory: Path,
    grype_version: str,
    executable: str,
    timeout: float,
) -> VulnerabilityResult:
    full_name = sbom.full_name
    output = output_directory / f"{full_name.replace('/', '-')}.json"
    analysis_date = datetime.now(UTC)

    try:
        if sbom.status != "generated":
            raise RuntimeError(sbom.error or "El SBOM no pudo generarse")

        source = Path(sbom.sbom_path)

        if not source.is_file():
            raise RuntimeError("No se encontró el archivo SBOM")

        scan_vulnerabilities(
            source,
            output,
            executable=executable,
            timeout=timeout,
        )

        return VulnerabilityResult(
            full_name=full_name,
            commit=sbom.commit,
            analysis_date=analysis_date,
            grype_version=grype_version,
            status="analyzed",
            vulnerability_count=0,
            report_path=str(output),
        )

    except RuntimeError as error:
        return VulnerabilityResult(
            full_name=full_name,
            commit=sbom.commit,
            analysis_date=analysis_date,
            grype_version=grype_version,
            status="failed",
            vulnerability_count=0,
            report_path=str(output),
            error=str(error),
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
    output_directory: Path,
    grype_version: str,
    executable: str,
    timeout: float,
    progress: Callable[[str], None],
) -> VulnerabilityReport:
    """Analiza los SBOM de los repositorios."""
    report = VulnerabilityReport(
        organization=organization,
        repositories=[],
    )

    for index, sbom in enumerate(repositories, 1):
        progress(f"[{index}/{len(repositories)}] {sbom.full_name}")

        result = _process_sbom(
            sbom,
            output_directory,
            grype_version,
            executable,
            timeout,
        )

        report.repositories.append(result)

        progress(f"  {result.status}" + (f": {result.error}" if result.error else ""))

    return report


def scan_organization_vulnerabilities(
    organization: str,
    output: Path,
    *,
    workspace: Path | None = None,
    run_id: str | None = None,
    executable: str = "grype",
    timeout: float = 600,
    progress: Callable[[str], None] = print,
) -> VulnerabilityReport:
    """Analiza las vulnerabilidades del último SBOM de una organización."""
    organization = organization.strip()

    if not organization:
        raise ValueError("La organización no puede estar vacía")

    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")

    clones = load_latest_clones(
        organization,
        workspace=workspace,
    )

    progress(f"Clones: {clones.workspace}")

    sbom_directory = _find_sbom_directory(
        clones.workspace,
        run_id,
    )

    progress(f"SBOM: {sbom_directory}")

    sbom_report = _load_sbom_report(
        sbom_directory,
    )

    repositories = sorted(
        sbom_report.repositories,
        key=lambda item: item.full_name,
    )

    vulnerability_directory = _create_vulnerability_directory(
        clones.workspace,
    )

    report_path = vulnerability_directory / "vulnerability-results.json"

    grype_version = _get_grype_version(
        repositories,
        executable,
    )

    report = _process_repositories(
        organization,
        repositories,
        vulnerability_directory,
        grype_version,
        executable,
        timeout,
        progress,
    )

    write_report(report, report_path)
    write_report(report, output)

    return report
