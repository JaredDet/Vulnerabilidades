"""Prepara clones de una organización sin ejecutar análisis ni generar SBOM."""

import re
from collections.abc import Callable
from pathlib import Path
from tempfile import mkdtemp

from .clone import DEFAULT_CLONE_TIMEOUT, CloneError, clone_repository
from .github_api import get_organization_repositories
from .models import (
    CloneResult,
    OrganizationCloneResult,
    Repository,
)


def _workspace(
    organization: str,
    workspace: Path | None,
) -> Path:
    if (
        not organization
        or organization in {".", ".."}
        or any(char in organization for char in "/\\:")
    ):
        raise ValueError(
            "Nombre de organización inválido para el directorio de trabajo"
        )

    return (
        workspace
        if workspace is not None
        else Path("organizations") / organization / "work"
    )


def _find_clone_runs(
    organization: str,
    workspace: Path,
) -> list[tuple[int, Path]]:
    """Encuentra ejecuciones de clonación válidas."""
    if not workspace.is_dir():
        return []

    candidates = []

    for root in workspace.iterdir():
        if not root.is_dir():
            continue

        manifest = root / "clones.json"
        legacy = root / "repositories" / organization

        if root.name.startswith("clone-") and manifest.is_file():
            candidates.append((manifest.stat().st_mtime_ns, root))
        elif root.name.startswith("scan-") and legacy.is_dir():
            candidates.append((legacy.stat().st_mtime_ns, root))

    return candidates


def _find_run_by_id(
    organization: str,
    workspace: Path,
    run_id: str,
) -> Path:
    """Encuentra una ejecución concreta por su identificador."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
        raise ValueError("--run-id debe ser solo el identificador de la ejecución")

    matches = [workspace / f"{prefix}{run_id}" for prefix in ("scan-", "clone-")]

    matches = [path for path in matches if path.is_dir()]

    if len(matches) != 1:
        raise ValueError(
            f"No se encontró una ejecución única con el identificador {run_id}"
        )

    root = matches[0]

    if not (
        (root / "clones.json").is_file()
        or (root / "repositories" / organization).is_dir()
    ):
        raise ValueError(
            "La ejecución indicada no contiene clones de esta organización"
        )

    return root


def _find_latest_run(
    organization: str,
    workspace: Path,
) -> Path:
    """Encuentra la última ejecución de clonación válida."""
    candidates = _find_clone_runs(
        organization,
        workspace,
    )

    if not candidates:
        raise ValueError(
            f"No hay clones disponibles para {organization}. "
            f"Ejecuta primero miner clone --organization {organization}"
        )

    return max(
        candidates,
        key=lambda candidate: (
            candidate[0],
            candidate[1].name,
        ),
    )[1]


def _load_clone_manifest(
    root: Path,
    organization: str,
) -> OrganizationCloneResult | None:
    """Carga el manifest de una ejecución si existe."""
    manifest = root / "clones.json"

    if not manifest.is_file():
        return None

    result = OrganizationCloneResult.model_validate_json(
        manifest.read_text(encoding="utf-8")
    )

    if result.organization != organization:
        raise ValueError("La clonación seleccionada pertenece a otra organización")

    return result


def _load_legacy_clones(
    root: Path,
    organization: str,
) -> OrganizationCloneResult:
    """Carga clones desde la estructura anterior."""
    repository_root = root / "repositories" / organization

    repositories = []

    for source in sorted(repository_root.iterdir()):
        if not source.is_dir() or not (source / ".git").exists():
            continue

        full_name = f"{organization}/{source.name}"

        repositories.append(
            CloneResult(
                repository=Repository(
                    full_name=full_name,
                    clone_url=(f"https://github.com/{full_name}.git"),
                ),
                source=source,
            )
        )

    if not repositories:
        raise ValueError(
            "La ejecución seleccionada no contiene repositorios Git clonados"
        )

    return OrganizationCloneResult(
        organization=organization,
        workspace=root,
        repositories=repositories,
    )


def load_latest_clones(
    organization: str,
    *,
    workspace: Path | None = None,
    run_id: str | None = None,
) -> OrganizationCloneResult:
    """Carga una ejecución de clonación sin ejecutar análisis."""
    organization = organization.strip()
    workspace = _workspace(
        organization,
        workspace,
    )

    root = (
        _find_run_by_id(
            organization,
            workspace,
            run_id,
        )
        if run_id is not None
        else _find_latest_run(
            organization,
            workspace,
        )
    ).resolve()

    result = _load_clone_manifest(
        root,
        organization,
    )

    if result is not None:
        return result

    return _load_legacy_clones(
        root,
        organization,
    )


def clone_organization(
    organization: str,
    token: str,
    *,
    workspace: Path | None = None,
    timeout: float = DEFAULT_CLONE_TIMEOUT,
    progress: Callable[[str], None] = print,
) -> OrganizationCloneResult:
    """Lista y clona los repositorios; conserva fallos sin detener el resto."""
    organization = organization.strip()

    if not organization or not token.strip() or timeout <= 0:
        raise ValueError("Se requiere organización, GITHUB_TOKEN y timeout positivo")

    workspace = _workspace(
        organization,
        workspace,
    )

    repositories = sorted(
        get_organization_repositories(
            organization,
            token,
        ),
        key=lambda repository: repository.full_name,
    )

    workspace.mkdir(
        parents=True,
        exist_ok=True,
    )

    root = Path(
        mkdtemp(
            prefix="clone-",
            dir=workspace,
        )
    ).resolve()

    result = OrganizationCloneResult(
        organization=organization,
        workspace=root,
        repositories=[],
    )

    for index, repository in enumerate(repositories, 1):
        progress(f"[{index}/{len(repositories)}] Clonando {repository.full_name}")

        try:
            source = clone_repository(
                repository,
                root / "repositories",
                token=token,
                timeout=timeout,
            )

            item = CloneResult(
                repository=repository,
                source=source,
            )

        except CloneError as error:
            item = CloneResult(
                repository=repository,
                error=str(error),
            )

        except Exception as error:  # noqa: BLE001
            item = CloneResult(
                repository=repository,
                error=(f"Error inesperado: {type(error).__name__}"),
            )

        result.repositories.append(item)

        progress(f"  {item.status}" + (f": {item.error}" if item.error else ""))

    (root / "clones.json").write_text(
        result.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )

    return result
