"""Crea y recupera ejecuciones de clonación de una organización."""

import re
from collections.abc import Callable
from pathlib import Path

from core.exceptions import AppException
from core.execution import workspace
from core.filesystem import create_temporary_directory, load_data, save_data

from .clone import (
    CLONE_MANIFEST_FILENAME,
    CLONE_REPOSITORIES_DIRECTORY,
    CLONE_RUN_PREFIX,
    DEFAULT_CLONE_TIMEOUT,
    clone_repository,
)
from .errors import CloneErrors
from .github_api import PAGE_SIZE, get_organization_repositories
from .models import CloneExecution, CloneResult, OrganizationCloneResult, Repository


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


def clone_organization(
    organization: str,
    token: str,
    *,
    workspace_path: Path | None = None,
    timeout: float = DEFAULT_CLONE_TIMEOUT,
    page_size: int = PAGE_SIZE,
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
    repositories = sorted(
        get_organization_repositories(organization, token, page_size=page_size),
        key=lambda repository: repository.full_name,
    )
    root = create_temporary_directory(workspace_path, CLONE_RUN_PREFIX)

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

    save_data(
        root / CLONE_MANIFEST_FILENAME,
        result.model_dump_json(indent=2) + "\n",
    )

    return result


def _find_clone_runs(workspace_path: Path) -> list[tuple[int, Path]]:
    """Encuentra ejecuciones de clonación válidas."""
    if not workspace_path.is_dir():
        return []

    candidates = []

    for root in workspace_path.iterdir():
        if not root.is_dir() or not root.name.startswith(CLONE_RUN_PREFIX):
            continue

        manifest = root / CLONE_MANIFEST_FILENAME

        if manifest.is_file():
            candidates.append((manifest.stat().st_mtime_ns, root))

    return candidates


def _find_run_by_id(workspace_path: Path, run_id: str) -> Path:
    """Encuentra una ejecución concreta por su identificador."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise CloneErrors.InvalidRunId

    root = workspace_path / f"{CLONE_RUN_PREFIX}{run_id}"

    if not root.is_dir():
        raise CloneErrors.RunNotFound

    if not (root / CLONE_MANIFEST_FILENAME).is_file():
        raise CloneErrors.InvalidCloneManifest

    return root


def _find_latest_run(workspace_path: Path) -> Path:
    """Encuentra la última ejecución de clonación válida."""
    candidates = _find_clone_runs(workspace_path)

    if not candidates:
        raise CloneErrors.CloneNotFound

    return max(
        candidates,
        key=lambda candidate: (candidate[0], candidate[1].name),
    )[1]


def _load_clone_manifest(
    root: Path,
    organization: str,
) -> OrganizationCloneResult:
    """Carga el manifest de una ejecución de clonación."""
    manifest = root / CLONE_MANIFEST_FILENAME

    try:
        result = OrganizationCloneResult.model_validate_json(load_data(manifest))
    except (OSError, ValueError):
        raise CloneErrors.InvalidCloneManifest from None

    if result.organization != organization:
        raise CloneErrors.WrongOrganization

    return result


def load_latest_clones(
    organization: str,
    *,
    workspace_path: Path | None = None,
    run_id: str | None = None,
) -> OrganizationCloneResult:
    """Carga una ejecución de clonación existente."""
    organization = organization.strip()

    if not organization:
        raise CloneErrors.OrganizationRequired

    workspace_path = workspace(organization, workspace_path)

    root = (
        _find_run_by_id(workspace_path, run_id)
        if run_id is not None
        else _find_latest_run(workspace_path)
    )

    return _load_clone_manifest(root, organization)
