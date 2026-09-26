"""Carga ejecuciones de clonación existentes."""

import re
from pathlib import Path

from core.execution import workspace
from core.filesystem import load_data

from .constants import CLONE_MANIFEST_FILENAME, CLONE_RUN_PREFIX
from .errors import CloneErrors
from .models import OrganizationCloneResult


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
