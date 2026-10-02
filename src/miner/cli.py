"""Interfaz de línea de comandos del miner."""

import os
from functools import wraps
from pathlib import Path
from typing import Annotated, Callable, ParamSpec, TypeVar

import typer
from dotenv import load_dotenv

from core.exception_handler import ExitCode, handle_exception
from core.exceptions import AppException
from miner.clone.github_api import PAGE_SIZE
from miner.dependencies.constants import (
    DEFAULT_GRYPE_EXECUTABLE,
)
from miner.dependencies.constants import (
    DEFAULT_SCAN_TIMEOUT as DEFAULT_GRYPE_SCAN_TIMEOUT,
)
from miner.dependencies.pipeline import (
    scan_organization_vulnerabilities,
)

from .clone.constants import DEFAULT_CLONE_TIMEOUT
from .clone.loader import load_latest_clones
from .clone.pipeline import clone_organization
from .codeql.constants import (
    DEFAULT_ANALYSIS_TIMEOUT,
    DEFAULT_CODEQL_EXECUTABLE,
)
from .codeql.pipeline import analyze_organization
from .dataset import generate_dataset
from .sbom.constants import (
    DEFAULT_SCAN_TIMEOUT as DEFAULT_SBOM_SCAN_TIMEOUT,
)
from .sbom.constants import (
    DEFAULT_SYFT_EXECUTABLE,
)
from .sbom.pipeline import generate_organization_sbom

load_dotenv()

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
)

P = ParamSpec("P")
R = TypeVar("R")


def command(
    name: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Registra un comando con el tratamiento común de errores de aplicación."""

    def register(callback: Callable[P, R]) -> Callable[P, R]:
        @wraps(callback)
        def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return callback(*args, **kwargs)
            except (AppException, OSError) as error:
                exit_code = handle_exception(
                    error,
                    write=lambda message: typer.echo(message, err=True),
                )
                raise typer.Exit(exit_code.value) from None

        return app.command(name=name)(wrapped)

    return register


@app.callback()
def main() -> None:
    """Clona, analiza y examina dependencias de repositorios."""


def _token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    if not token:
        typer.echo("Debes definir GITHUB_TOKEN", err=True)
        raise typer.Exit(2)

    return token


@command(name="analyze-code")
def analyze(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    output: Annotated[Path, typer.Option("--output")] = Path("results.json"),
    codeql: Annotated[str, typer.Option("--codeql")] = DEFAULT_CODEQL_EXECUTABLE,
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="Clone-run ID (e.g. xkfbl6pl). Uses the latest clone run if omitted.",
        ),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1),
    ] = DEFAULT_ANALYSIS_TIMEOUT,
) -> None:
    """Analiza la clonación más reciente de una organización, sin volver a clonar."""
    token = _token()

    clones = load_latest_clones(organization, run_id=run_id)
    typer.echo(f"Clones: {clones.workspace}", err=True)

    report = analyze_organization(
        clones,
        output,
        token=token,
        executable=codeql,
        timeout=timeout,
        progress=lambda text: typer.echo(text, err=True),
    )

    typer.echo(
        f"JSON: {output}; repositorios: {report.summary.repositories}; "
        f"hallazgos: {report.summary.findings}",
        err=True,
    )


@command(name="clone-repositories")
def clone(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1),
    ] = DEFAULT_CLONE_TIMEOUT,
    page_size: Annotated[
        int,
        typer.Option(
            "--page-size",
            "-p",
            min=1,
            max=PAGE_SIZE,  # GitHub no permite pedir más de 100 por página
            help="Tamaño de página para las consultas de repositorios a la API de GitHub.",
        ),
    ] = PAGE_SIZE,
) -> None:
    """Clona los repositorios y muestra sus rutas, sin ejecutar análisis."""
    token = _token()

    result = clone_organization(
        organization,
        token,
        workspace_path=workspace,
        timeout=timeout,
        page_size=page_size,
        progress=lambda text: typer.echo(text, err=True),
    )

    typer.echo(result.model_dump_json(indent=2))


@command(name="generate-sbom")
def sbom(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="Clone-run ID (e.g. xkfbl6pl). Uses the latest clone run if omitted.",
        ),
    ] = None,
    output: Annotated[Path, typer.Option("--output")] = Path("sbom-results.json"),
    syft: Annotated[str, typer.Option("--syft")] = DEFAULT_SYFT_EXECUTABLE,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1),
    ] = DEFAULT_SBOM_SCAN_TIMEOUT,
) -> None:
    """Genera los SBOM de la clonación más reciente."""
    report = generate_organization_sbom(
        organization,
        output,
        run_id=run_id,
        executable=syft,
        timeout=timeout,
        progress=lambda text: typer.echo(text, err=True),
    )

    typer.echo(
        f"JSON: {output}; repositorios: {len(report.repositories)}",
        err=True,
    )


@command(name="scan-dependency-vulnerabilities")
def vulnerabilities(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="ID after sbom- (e.g. 7o9x8nb_). Uses the latest SBOM run if omitted.",
        ),
    ] = None,
    output: Annotated[Path, typer.Option("--output")] = Path(
        "vulnerability-results.json"
    ),
    grype: Annotated[str, typer.Option("--grype")] = DEFAULT_GRYPE_EXECUTABLE,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1),
    ] = DEFAULT_GRYPE_SCAN_TIMEOUT,
) -> None:
    """Busca vulnerabilidades en las dependencias de los repositorios."""
    report = scan_organization_vulnerabilities(
        organization,
        output,
        run_id=run_id,
        executable=grype,
        timeout=timeout,
        progress=lambda text: typer.echo(text, err=True),
    )

    typer.echo(
        f"JSON: {output}; repositorios: {len(report.repositories)}",
        err=True,
    )


@command(name="generate-dataset")
def dataset(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    run_id: Annotated[str | None, typer.Option("--run-id")] = None,
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
) -> None:
    """Integra CodeQL y Grype en dataset.json junto a clones.json."""
    clones = load_latest_clones(organization, run_id=run_id, workspace_path=workspace)
    typer.echo(f"Dataset: {generate_dataset(clones)}")


@command(name="run")
def run(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    codeql: Annotated[str, typer.Option("--codeql")] = DEFAULT_CODEQL_EXECUTABLE,
    syft: Annotated[str, typer.Option("--syft")] = DEFAULT_SYFT_EXECUTABLE,
    grype: Annotated[str, typer.Option("--grype")] = DEFAULT_GRYPE_EXECUTABLE,
    timeout: Annotated[float, typer.Option("--timeout", min=1)] = 600,
) -> None:
    """Clona, analiza código, genera SBOM, analiza dependencias e integra el dataset."""
    token = _token()
    progress = lambda message: typer.echo(message, err=True)
    clones = clone_organization(
        organization, token, workspace_path=workspace, timeout=timeout, progress=progress,
    )
    root = clones.workspace.resolve()
    clone_id = root.name.removeprefix("clone-")
    analyze_organization(
        clones, root / "codeql-results.json", token=token,
        executable=codeql, timeout=timeout, progress=progress,
    )
    sbom_report = generate_organization_sbom(
        clones.organization, root / "sbom-results.json", workspace=root.parent,
        run_id=clone_id, executable=syft, timeout=timeout, progress=progress,
    )
    sbom_id = (
        Path(sbom_report.repositories[0].sbom_path).parent.name.removeprefix("sbom-")
        if sbom_report.repositories else None
    )
    scan_organization_vulnerabilities(
        clones.organization, root / "vulnerability-results.json", workspace=root.parent,
        clone_run_id=clone_id, run_id=sbom_id, executable=grype,
        timeout=timeout, progress=progress,
    )
    typer.echo(f"Dataset: {generate_dataset(clones)}")


if __name__ == "__main__":
    app()
