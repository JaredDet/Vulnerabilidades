"""Coordina la generación de SBOM de repositorios con Syft."""

import json
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from core.exceptions import AppException
from core.filesystem import create_temporary_directory

from ..clone.loader import load_latest_clones
from ..clone.models import CloneResult
from .constants import (
    DEFAULT_GIT_TIMEOUT,
    DEFAULT_SCAN_TIMEOUT,
    DEFAULT_SYFT_EXECUTABLE,
    GIT_COMMIT_COMMAND,
    GIT_EXECUTABLE,
    GIT_HEAD_REFERENCE,
    SBOM_DIRECTORY,
    SBOM_REPORT_FILENAME,
    SBOM_RUN_PREFIX,
)
from .errors import SBOMErrors
from .models import SBOMExecution, SBOMReport, SBOMResult
from .report import write_report
from .syft import generate_sbom, get_version


def _get_commit(source: Path) -> str:
    try:
        result = subprocess.run(
            [
                GIT_EXECUTABLE,
                "-C",
                str(source),
                GIT_COMMIT_COMMAND,
                GIT_HEAD_REFERENCE,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=DEFAULT_GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise SBOMErrors.CommitTimeout from None
    except FileNotFoundError:
        raise SBOMErrors.GitNotAvailable from None
    except subprocess.CalledProcessError:
        raise SBOMErrors.CommitFailed from None
    except OSError:
        raise SBOMErrors.GitAccessFailed from None

    commit = result.stdout.strip()

    if not commit:
        raise SBOMErrors.CommitNotFound

    return commit


def _count_components(sbom_path: Path) -> int:
    try:
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise SBOMErrors.InvalidSbom from None

    if not isinstance(data, dict) or data.get("bomFormat") != "CycloneDX":
        raise SBOMErrors.InvalidSbom

    components = data.get("components", [])

    if not isinstance(components, list) or any(
        not isinstance(item, dict) for item in components
    ):
        raise SBOMErrors.InvalidComponents

    return len(components)


def _create_sbom_directory(workspace: Path) -> Path:
    """Crea el directorio para una ejecución de SBOM."""
    return create_temporary_directory(
        workspace / SBOM_DIRECTORY,
        SBOM_RUN_PREFIX,
    )


def _has_cloned_repositories(repositories: list[CloneResult]) -> bool:
    return any(repository.source is not None for repository in repositories)


def _get_syft_version(
    repositories: list[CloneResult],
    executable: str,
) -> str:
    if not _has_cloned_repositories(repositories):
        return "unknown"

    return get_version(executable)


def _create_execution(
    workspace: Path,
    repositories: list[CloneResult],
    executable: str,
    timeout: float,
) -> SBOMExecution:
    return SBOMExecution(
        output_directory=_create_sbom_directory(workspace),
        syft_version=_get_syft_version(repositories, executable),
        executable=executable,
        timeout=timeout,
    )


def _get_repository_output(clone: CloneResult, output_directory: Path) -> Path:
    filename = f"{clone.repository.full_name.replace('/', '-')}.json"
    return output_directory / filename


def _generate_repository_sbom(
    clone: CloneResult,
    execution: SBOMExecution,
    output: Path,
) -> tuple[str, int]:
    if clone.source is None:
        raise SBOMErrors.CloneFailed

    commit = _get_commit(clone.source)

    generate_sbom(
        clone.source,
        output,
        executable=execution.executable,
        timeout=execution.timeout,
    )

    return commit, _count_components(output)


def _create_generated_result(
    clone: CloneResult,
    execution: SBOMExecution,
    output: Path,
    commit: str,
    generation_date: datetime,
    component_count: int,
) -> SBOMResult:
    return SBOMResult(
        full_name=clone.repository.full_name,
        commit=commit,
        generation_date=generation_date,
        syft_version=execution.syft_version,
        status="generated",
        component_count=component_count,
        sbom_path=str(output),
    )


def _create_failed_result(
    clone: CloneResult,
    execution: SBOMExecution,
    output: Path,
    generation_date: datetime,
    error: AppException,
) -> SBOMResult:
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


def _process_repository(
    clone: CloneResult,
    execution: SBOMExecution,
) -> SBOMResult:
    output = _get_repository_output(clone, execution.output_directory)
    generation_date = datetime.now(UTC)

    try:
        commit, component_count = _generate_repository_sbom(
            clone,
            execution,
            output,
        )
    except AppException as error:
        return _create_failed_result(
            clone,
            execution,
            output,
            generation_date,
            error,
        )

    return _create_generated_result(
        clone,
        execution,
        output,
        commit,
        generation_date,
        component_count,
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


def _write_reports(
    report: SBOMReport,
    execution: SBOMExecution,
    output: Path,
) -> None:
    write_report(
        report,
        execution.output_directory / SBOM_REPORT_FILENAME,
    )
    write_report(report, output)


def generate_organization_sbom(
    organization: str,
    output: Path,
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
