"""Interfaz de línea de comandos del miner."""

import os
from pathlib import Path
from typing import Annotated

import typer

from codeql import CodeQLError
from github_api import GitHubAPIError, get_organization_repositories
from miner import scan_organization

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


@app.callback()
def main() -> None:
    """Analiza repositorios de una organización con CodeQL."""


def _token() -> str:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        typer.echo("Debes definir GITHUB_TOKEN", err=True)
        raise typer.Exit(2)
    return token


@app.command()
def scan(
    organization: Annotated[str, typer.Option("--organization", "-o")],
    output: Annotated[Path, typer.Option("--output")] = Path("results.json"),
    codeql: Annotated[str, typer.Option("--codeql")] = "codeql",
    workspace: Annotated[Path, typer.Option("--workspace")] = Path("work"),
    timeout: Annotated[float, typer.Option("--timeout", min=1)] = 600,
) -> None:
    """Clona, analiza y consolida todos los repositorios accesibles."""
    token = _token()
    try:
        report = scan_organization(organization, token, output, workspace=workspace,
                                   executable=codeql, timeout=timeout,
                                   progress=lambda text: typer.echo(text, err=True))
    except (GitHubAPIError, CodeQLError, ValueError) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from None
    except OSError:
        typer.echo("No se pudo acceder al directorio de trabajo o guardar el JSON", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"JSON: {output}; repositorios: {report.summary.repositories}; "
               f"hallazgos: {report.summary.findings}", err=True)


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


if __name__ == "__main__":
    app()
