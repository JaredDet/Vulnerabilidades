"""Prepara clones de una organización sin ejecutar análisis ni generar SBOM."""

from collections.abc import Callable
from pathlib import Path
import re
from tempfile import mkdtemp

from .clone import DEFAULT_CLONE_TIMEOUT, CloneError, clone_repository
from .github_api import get_organization_repositories
from .models import CloneResult, OrganizationCloneResult, Repository


def _workspace(organization: str, workspace: Path | None) -> Path:
    if not organization or organization in {".", ".."} or any(
        char in organization for char in "/\\:"
    ):
        raise ValueError("Nombre de organización inválido para el directorio de trabajo")
    return workspace if workspace is not None else Path("organizations") / organization / "work"


def load_latest_clones(
    organization: str,
    *,
    workspace: Path | None = None,
    run_id: str | None = None,
) -> OrganizationCloneResult:
    """Carga la última clonación terminada, incluidas las carpetas scan antiguas."""
    organization = organization.strip()
    workspace = _workspace(organization, workspace)
    candidates: list[tuple[int, Path]] = []
    if run_id is not None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
            raise ValueError("--run-id debe ser solo el identificador de la ejecución")
        matches = [workspace / f"{prefix}{run_id}" for prefix in ("scan-", "clone-")]
        matches = [path for path in matches if path.is_dir()]
        if len(matches) != 1:
            raise ValueError(f"No se encontró una ejecución única con el identificador {run_id}")
        directory = matches[0]
        if not (directory / "clones.json").is_file() and not (directory / "repositories" / organization).is_dir():
            raise ValueError("La ejecución indicada no contiene clones de esta organización")
        candidates.append((0, directory))
    elif workspace.is_dir():
        for root in workspace.iterdir():
            if not root.is_dir():
                continue
            manifest = root / "clones.json"
            legacy = root / "repositories" / organization
            if root.name.startswith("clone-") and manifest.is_file():
                candidates.append((manifest.stat().st_mtime_ns, root))
            elif root.name.startswith("scan-") and legacy.is_dir():
                candidates.append((legacy.stat().st_mtime_ns, root))

    if not candidates:
        raise ValueError(
            f"No hay clones disponibles para {organization}. "
            "Ejecuta primero miner clone --organization " + organization
        )

    # El análisis crea otras carpetas, pero no modifica la fecha del manifiesto.
    root = max(candidates, key=lambda candidate: (candidate[0], candidate[1].name))[1].resolve()
    manifest = root / "clones.json"
    if manifest.is_file():
        result = OrganizationCloneResult.model_validate_json(manifest.read_text(encoding="utf-8"))
        if result.organization != organization:
            raise ValueError("La clonación seleccionada pertenece a otra organización")
        return result

    repositories = []
    for source in sorted((root / "repositories" / organization).iterdir()):
        if source.is_dir() and (source / ".git").exists():
            full_name = f"{organization}/{source.name}"
            repositories.append(CloneResult(
                repository=Repository(
                    full_name=full_name, clone_url=f"https://github.com/{full_name}.git",
                ),
                source=source,
            ))
    if not repositories:
        raise ValueError("La ejecución seleccionada no contiene repositorios Git clonados")
    return OrganizationCloneResult(
        organization=organization, workspace=root, repositories=repositories,
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

    workspace = _workspace(organization, workspace)

    repositories = sorted(
        get_organization_repositories(organization, token),
        key=lambda repository: repository.full_name,
    )
    workspace.mkdir(parents=True, exist_ok=True)
    root = Path(mkdtemp(prefix="clone-", dir=workspace)).resolve()
    result = OrganizationCloneResult(
        organization=organization, workspace=root, repositories=[],
    )

    for index, repository in enumerate(repositories, 1):
        progress(f"[{index}/{len(repositories)}] Clonando {repository.full_name}")
        try:
            source = clone_repository(
                repository, root / "repositories", token=token, timeout=timeout,
            )
            item = CloneResult(repository=repository, source=source)
        except CloneError as error:
            item = CloneResult(repository=repository, error=str(error))
        except Exception as error:  # noqa: BLE001
            item = CloneResult(
                repository=repository,
                error=f"Error inesperado: {type(error).__name__}",
            )
        result.repositories.append(item)
        progress(f"  {item.status}" + (f": {item.error}" if item.error else ""))

    (root / "clones.json").write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return result
