import base64
import os
import re
import subprocess
from pathlib import Path

from .errors import CloneErrors
from .models import Repository

CLONE_RUN_PREFIX = "clone-"
CLONE_REPOSITORIES_DIRECTORY = "repositories"
CLONE_MANIFEST_FILENAME = "clones.json"

DEFAULT_CLONE_TIMEOUT = 300

REPOSITORY_NAME_PART_PATTERN = re.compile(r"[A-Za-z0-9_.-]+")

DEFAULT_CLONE_DIRECTORY = Path("repositories")


def _prepare_destination(full_name: str, destination: Path) -> Path:
    parts = full_name.split("/")

    if len(parts) != 2 or any(
        not REPOSITORY_NAME_PART_PATTERN.fullmatch(part) or part in {".", ".."}
        for part in parts
    ):
        raise CloneErrors.InvalidRepositoryName

    try:
        root = Path(destination).resolve()
        target = root.joinpath(*parts).resolve()

        if not target.is_relative_to(root):
            raise CloneErrors.DestinationOutsideRoot

        if target.exists():
            raise CloneErrors.DestinationAlreadyExists

        target.parent.mkdir(parents=True, exist_ok=True)

    except OSError:
        raise CloneErrors.GitCloneFailed from None

    return target


def _build_environment(token: str | None) -> dict[str, str]:
    environment = {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
    }

    if token:
        credentials = base64.b64encode(f"x-access-token:{token}".encode()).decode()

        environment.update(
            {
                "GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_0": "http.https://github.com/.extraheader",
                "GIT_CONFIG_VALUE_0": (f"Authorization: Basic {credentials}"),
                "GIT_CONFIG_KEY_1": "credential.helper",
                "GIT_CONFIG_VALUE_1": "",
            }
        )

    return environment


def _run_git_clone(
    repository: Repository,
    target: Path,
    timeout: float,
    token: str | None = None,
) -> None:
    try:
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--",
                repository.clone_url,
                str(target),
            ],
            check=True,
            capture_output=True,
            timeout=timeout,
            env=_build_environment(token),
        )

    except subprocess.TimeoutExpired:
        raise CloneErrors.GitCloneTimeout from None

    except subprocess.CalledProcessError:
        raise CloneErrors.GitCloneFailed from None

    except OSError:
        raise CloneErrors.GitCloneFailed from None


def clone_repository(
    repository: Repository,
    destination: Path = DEFAULT_CLONE_DIRECTORY,
    *,
    timeout: float = DEFAULT_CLONE_TIMEOUT,
    token: str | None = None,
) -> Path:
    """Clona un repositorio y devuelve su ruta absoluta.

    Requiere Git instalado y no sobrescribe destinos existentes.
    """
    if timeout <= 0:
        raise CloneErrors.InvalidTimeout

    target = _prepare_destination(repository.full_name, destination)

    _run_git_clone(
        repository,
        target,
        timeout,
        token,
    )

    return target
