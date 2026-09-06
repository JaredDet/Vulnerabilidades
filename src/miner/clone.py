import base64
import os
import re
import subprocess
from pathlib import Path

from .models import Repository

REPOSITORY_NAME_PART_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")
DEFAULT_CLONE_DIRECTORY = Path("repositories")
DEFAULT_CLONE_TIMEOUT = 300


class CloneError(RuntimeError):
    """No se pudo clonar un repositorio."""


def _prepare_destination(full_name: str, destination: Path) -> Path:
    parts = full_name.split("/")
    if len(parts) != 2 or any(
        not REPOSITORY_NAME_PART_PATTERN.fullmatch(part) or part in {".", ".."}
        for part in parts
    ):
        raise CloneError(
            "El nombre debe tener el formato organización/repositorio")
    try:
        root = Path(destination).resolve()
        target = root.joinpath(*parts).resolve()
        if not target.is_relative_to(root):
            raise CloneError("La ruta del repositorio queda fuera del destino")
        if target.exists():
            raise CloneError(f"El destino ya existe: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise CloneError(
            "No se pudo acceder al destino de clonación") from None
    return target


def _run_git_clone(repository: Repository, target: Path, timeout: float, token: str | None = None) -> None:
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0",
                   "GCM_INTERACTIVE": "Never"}
    if token:
        # Configuración del proceso: el secreto no se guarda en .git/config ni argv.
        credentials = base64.b64encode(
            f"x-access-token:{token}".encode()).decode()
        environment.update({
            "GIT_CONFIG_COUNT": "2",
            "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
            "GIT_CONFIG_VALUE_0": f"Authorization: Basic {credentials}",
            "GIT_CONFIG_KEY_1": "credential.helper", "GIT_CONFIG_VALUE_1": "",
        })
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--",
                repository.clone_url, str(target)],
            check=True,
            capture_output=True,
            timeout=timeout,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        raise CloneError(f"La clonación superó {timeout} segundos") from None
    except subprocess.CalledProcessError as error:
        raise CloneError(
            f"Git no pudo clonar {repository.full_name} (código {error.returncode})"
        ) from None
    except OSError:
        raise CloneError(
            "No se pudo ejecutar Git"
        ) from None


def clone_repository(
    repository: Repository,
    destination: Path = DEFAULT_CLONE_DIRECTORY,
    *,
    timeout: float = DEFAULT_CLONE_TIMEOUT,
    token: str | None = None,
) -> Path:
    """Clona en destination/organización/repositorio y devuelve su ruta absoluta.

    Requiere Git instalado. Lanza CloneError sin sobrescribir carpetas existentes.
    El llamador debe registrar el error y continuar con el siguiente repositorio.
    """
    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")
    target = _prepare_destination(repository.full_name, destination)
    _run_git_clone(repository, target, timeout, token)
    return target
