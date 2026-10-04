"""Coordina la generación de SBOM de repositorios con Syft."""

import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from core.exceptions import AppException
from core.filesystem import create_temporary_directory
from core.reporting import write_json_report

from ..clone.pipeline import load_latest_clones
from ..clone.models import CloneResult
from .constants import (
    DEFAULT_GIT_TIMEOUT,
    DEFAULT_SCAN_TIMEOUT,
    DEFAULT_SYFT_EXECUTABLE,
    SBOM_DIRECTORY,
    SBOM_REPORT_FILENAME,
    SBOM_RUN_PREFIX,
)
from .errors import SBOMErrors
from .models import SBOMExecution, SBOMReport, SBOMResult
from .syft import generate_sbom, get_version


def _get_commit(source: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(source), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=DEFAULT_GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise SBOMErrors.CommitTimeout from None
    except subprocess.CalledProcessError:
        raise SBOMErrors.CommitFailed from None
    except OSError:
        raise SBOMErrors.CommitFailed from None

    commit = result.stdout.strip()

    if not commit:
        raise SBOMErrors.CommitFailed

    return commit


def _count_components(sbom_path: Path) -> int:
    try:
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SBOMErrors.InvalidSBOM from None

    if not isinstance(data, dict) or data.get("bomFormat") != "CycloneDX":
        raise SBOMErrors.InvalidSBOM

    components = data.get("components", [])

    if not isinstance(components, list) or any(
        not isinstance(item, dict) for item in components
    ):
        raise SBOMErrors.InvalidSBOM

    return len(components)


def _order_report(result: SBOMReport) -> None:
    result.repositories.sort(key=lambda repository: repository.full_name)


def write_report(result: SBOMReport, output: Path) -> Path:
    """Escribe el reporte validado de forma atómica."""
    return write_json_report(result, output, order=_order_report)


def _process_repository(clone: CloneResult, execution: SBOMExecution) -> SBOMResult:
    filename = f"{clone.repository.full_name.replace('/', '-')}.json"
    output = execution.output_directory / filename
    generation_date = datetime.now(UTC)

    try:
        if clone.source is None:
            raise SBOMErrors.CloneFailed
        commit = _get_commit(clone.source)
        generate_sbom(
            clone.source,
            output,
            executable=execution.executable,
            timeout=execution.timeout,
        )
        component_count = _count_components(output)
    except AppException as error:
        return SBOMResult(
            full_name=clone.repository.full_name,
            commit="unknown",
            generation_date=generation_date,
            syft_version=execution.syft_version,
            status="failed",
            component_count=0,
            sbom_path=str(output),
            error=error.message,
        )

    return SBOMResult(
        full_name=clone.repository.full_name,
        commit=commit,
        generation_date=generation_date,
        syft_version=execution.syft_version,
        status="generated",
        component_count=component_count,
        sbom_path=str(output),
    )


def _process_repositories(
    organization: str,
    repositories: list[CloneResult],
    execution: SBOMExecution,
    progress: Callable[[str], None],
) -> SBOMReport:
    """Genera los SBOM de los repositorios."""
    report = SBOMReport(
        organization=organization,
        repositories=[],
    )

    for index, clone in enumerate(repositories, 1):
        progress(f"[{index}/{len(repositories)}] {clone.repository.full_name}")

        result = _process_repository(clone, execution)
        report.repositories.append(result)

        progress(f"  {result.status}" + (f": {result.error}" if result.error else ""))

    return report


def generate_organization_sbom(
    organization: str,
    output: Path | None = None,
    *,
    workspace: Path | None = None,
    run_id: str | None = None,
    executable: str = DEFAULT_SYFT_EXECUTABLE,
    timeout: float = DEFAULT_SCAN_TIMEOUT,
    progress: Callable[[str], None] = print,
) -> SBOMReport:
    """Genera los SBOM de los repositorios de una organización."""
    if not organization.strip():
        raise SBOMErrors.OrganizationRequired

    if timeout <= 0:
        raise SBOMErrors.InvalidTimeout

    clones = load_latest_clones(
        organization,
        workspace_path=workspace,
        run_id=run_id,
    )

    progress(f"Clones: {clones.workspace}")

    repositories = sorted(
        clones.repositories,
        key=lambda item: item.repository.full_name,
    )

    output_directory = create_temporary_directory(
        clones.workspace / SBOM_DIRECTORY,
        SBOM_RUN_PREFIX,
    )
    has_clones = any(repository.source is not None for repository in repositories)
    execution = SBOMExecution(
        output_directory=output_directory,
        syft_version=get_version(executable) if has_clones else "unknown",
        executable=executable,
        timeout=timeout,
    )

    report = _process_repositories(
        organization,
        repositories,
        execution,
        progress,
    )

    write_report(report, execution.output_directory / SBOM_REPORT_FILENAME)
    if output is not None:
        write_report(report, output)

    return report
