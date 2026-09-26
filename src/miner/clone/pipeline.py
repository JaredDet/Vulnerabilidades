"""Prepara clones de una organización sin ejecutar análisis ni generar SBOM."""

from collections.abc import Callable
from pathlib import Path

from core.exceptions import AppException
from core.execution import workspace
from core.filesystem import create_temporary_directory, save_data

from .clone import DEFAULT_CLONE_TIMEOUT, clone_repository
from .constants import (
    CLONE_MANIFEST_FILENAME,
    CLONE_REPOSITORIES_DIRECTORY,
    CLONE_RUN_PREFIX,
)
from .errors import CloneErrors
from .github_api import get_organization_repositories
from .models import CloneExecution, CloneResult, OrganizationCloneResult, Repository


def _get_repositories(organization: str, token: str) -> list[Repository]:
    """Obtiene los repositorios de una organización ordenados por nombre."""
    return sorted(
        get_organization_repositories(organization, token),
        key=lambda repository: repository.full_name,
    )


def _create_clone_run(workspace_path: Path) -> Path:
    """Crea la carpeta para una nueva ejecución de clonación."""
    return create_temporary_directory(workspace_path, CLONE_RUN_PREFIX)


def _clone_repository(
    repository: Repository,
    execution: CloneExecution,
) -> CloneResult:
    """Clona un repositorio y conserva su fallo como resultado."""
    try:
        source = clone_repository(
            repository,
            execution.root / CLONE_REPOSITORIES_DIRECTORY,
            token=execution.token,
            timeout=execution.timeout,
        )
        return CloneResult(repository=repository, source=source)
    except Exception as error:  # noqa: BLE001
        return CloneResult(
            repository=repository,
            error=str(error)
            if isinstance(error, AppException)
            else (f"Error inesperado: {type(error).__name__}"),
        )


def _clone_repositories(
    repositories: list[Repository],
    execution: CloneExecution,
) -> list[CloneResult]:
    """Clona los repositorios y conserva los fallos individuales."""
    results = []

    for index, repository in enumerate(repositories, 1):
        execution.progress(
            f"[{index}/{len(repositories)}] Clonando {repository.full_name}"
        )

        result = _clone_repository(repository, execution)
        results.append(result)

        execution.progress(
            f"  {result.status}" + (f": {result.error}" if result.error else "")
        )

    return results


def _save_clone_result(root: Path, result: OrganizationCloneResult) -> None:
    """Guarda el resultado de una ejecución de clonación."""
    save_data(
        root / CLONE_MANIFEST_FILENAME,
        result.model_dump_json(indent=2) + "\n",
    )


def clone_organization(
    organization: str,
    token: str,
    *,
    workspace_path: Path | None = None,
    timeout: float = DEFAULT_CLONE_TIMEOUT,
    progress: Callable[[str], None] = print,
) -> OrganizationCloneResult:
    """Lista y clona los repositorios de una organización."""
    organization = organization.strip()

    if not organization:
        raise CloneErrors.OrganizationRequired

    if not token.strip():
        raise CloneErrors.TokenRequired

    if timeout <= 0:
        raise CloneErrors.InvalidTimeout

    workspace_path = workspace(organization, workspace_path)
    repositories = _get_repositories(organization, token)
    root = _create_clone_run(workspace_path)

    execution = CloneExecution(
        root=root,
        token=token,
        timeout=timeout,
        progress=progress,
    )

    result = OrganizationCloneResult(
        organization=organization,
        workspace=root,
        repositories=_clone_repositories(repositories, execution),
    )

    _save_clone_result(root, result)

    return result
