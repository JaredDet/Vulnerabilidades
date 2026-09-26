from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, computed_field
from pydantic.dataclasses import dataclass


@dataclass(frozen=True)
class CloneExecution:
    root: Path
    token: str
    timeout: float
    progress: Callable[[str], None]

    def __init__(
        self,
        root: Path,
        token: str,
        timeout: float,
        progress: Callable[[str], None],
    ) -> None:
        self.root = root
        self.token = token
        self.timeout = timeout
        self.progress = progress


class Repository(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
        str_min_length=1,
    )

    full_name: str
    clone_url: str


class CloneResult(BaseModel):
    """Ruta del clon preparado o motivo del fallo, sin datos de análisis."""

    repository: Repository
    source: Path | None = None
    error: str | None = None

    @computed_field
    @property
    def status(self) -> str:
        return "cloned" if self.source is not None else "clone_failed"


class OrganizationCloneResult(BaseModel):
    """Clones reutilizables por cualquier procesador de repositorios."""

    organization: str
    workspace: Path
    repositories: list[CloneResult]

    @computed_field
    @property
    def cloned(self) -> int:
        return sum(item.source is not None for item in self.repositories)

    @computed_field
    @property
    def failed(self) -> int:
        return len(self.repositories) - self.cloned
