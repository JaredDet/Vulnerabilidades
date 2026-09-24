"""Interfaz de línea de comandos del miner."""

import os
from pathlib import Path
from typing import Annotated

import typer
from dotenv import load_dotenv

from .analysis.codeql import CodeQLError
from .analysis.pipeline import analyze_organization
from .clone.github_api import GitHubAPIError, get_organization_repositories
from .clone.pipeline import clone_organization, load_latest_clones
from .sbom.pipeline import generate_organization_sbom

load_dotenv()

app = typer.Typer(
    add_completion=False,
    pretty_exceptions_enable=False,
)


@app.callback()
def main() -> None:
    """Clona y analiza repositorios de una organización."""


def _token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        typer.echo("Debes definir GITHUB_TOKEN", err=True)
        raise typer.Exit(2)
    return token


@app.command()
def analyze(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    output: Annotated[Path, typer.Option("--output")] = Path("results.json"),
    codeql: Annotated[str, typer.Option("--codeql")] = "codeql",
    run_id: Annotated[
        str | None,
        typer.Option(
            "--run-id",
            help="ID after scan- or clone- (e.g. xkfbl6pl). Uses the latest clone run if omitted.",
        ),
    ] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=1)] = 600,
) -> None:
    """Analiza la clonación más reciente de una organización, sin volver a clonar."""
    token = _token()
    try:
        clones = load_latest_clones(
            organization,
            run_id=run_id,
        )
        typer.echo(f"Clones: {clones.workspace}", err=True)
        report = analyze_organization(
            clones,
            output,
            token=token,
            executable=codeql,
            timeout=timeout,
            progress=lambda text: typer.echo(text, err=True),
        )
    except (GitHubAPIError, CodeQLError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None
    except OSError:
        typer.echo(
            "No se pudo acceder al directorio de trabajo o guardar el JSON", err=True
        )
        raise typer.Exit(1) from None
    typer.echo(
        f"JSON: {output}; repositorios: {report.summary.repositories}; "
        f"hallazgos: {report.summary.findings}",
        err=True,
    )


@app.command()
def clone(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    workspace: Annotated[Path | None, typer.Option("--workspace")] = None,
    timeout: Annotated[float, typer.Option("--timeout", min=1)] = 300,
) -> None:
    """Clona los repositorios y muestra sus rutas, sin ejecutar análisis."""
    token = _token()
    try:
        result = clone_organization(
            organization,
            token,
            workspace=workspace,
            timeout=timeout,
            progress=lambda text: typer.echo(text, err=True),
        )
    except (GitHubAPIError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None
    except OSError:
        typer.echo("No se pudo acceder al directorio de trabajo", err=True)
        raise typer.Exit(1) from None
    typer.echo(result.model_dump_json(indent=2))


@app.command(name="list")
def list_repositories(organization: str) -> None:
    """Lista repositorios sin clonarlos ni ejecutar CodeQL."""
    token = _token()
    try:
        for repository in get_organization_repositories(organization, token):
            typer.echo(f"{repository.full_name}\t{repository.clone_url}")
    except (GitHubAPIError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None


@app.command()
def sbom(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    run_id: Annotated[
        str | None,
        typer.Option("--run-id", help="ID after scan- or clone- (e.g. xkfbl6pl). Uses the latest clone run if omitted."),
    ] = None,
    output: Annotated[
        Path,
        typer.Option("--output"),
    ] = Path("sbom-results.json"),
    syft: Annotated[
        str,
        typer.Option("--syft"),
    ] = "syft",
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1),
    ] = 600,
) -> None:
    """Genera los SBOM de la clonación más reciente."""

    try:
        report = generate_organization_sbom(
            organization,
            output,
            run_id=run_id,
            executable=syft,
            timeout=timeout,
            progress=lambda text: typer.echo(text, err=True),
        )
    except (ValueError, RuntimeError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None
    except OSError:
        typer.echo(
            "No se pudo acceder al directorio de trabajo o guardar el JSON",
            err=True,
        )
        raise typer.Exit(1) from None

    typer.echo(
        f"JSON: {output}; repositorios: {len(report.repositories)}",
        err=True,
    )


if __name__ == "__main__":
    app()
