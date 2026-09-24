"""Coordina la generación de SBOM de repositorios con Syft."""

import json
import subprocess
from collections.abc import Callable
from datetime import datetime, UTC
from pathlib import Path
from tempfile import mkdtemp

from ..clone.models import CloneResult
from ..clone.pipeline import load_latest_clones

from .models import SBOMReport, SBOMResult
from .report import write_report
from .syft import generate_sbom, get_version


def _get_commit(source: Path) -> str:
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "rev-parse",
                "HEAD",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("Git excedio el tiempo para obtener el commit") from None
    except FileNotFoundError:
        raise RuntimeError("No se encontró Git") from None
    except subprocess.CalledProcessError:
        raise RuntimeError("No se pudo obtener el commit del repositorio") from None
    except OSError:
        raise RuntimeError("No se pudo ejecutar Git") from None

    commit = result.stdout.strip()

    if not commit:
        raise RuntimeError("Git no devolvió ningún commit")

    return commit


def _count_components(sbom_path: Path) -> int:
    try:
        data = json.loads(sbom_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise RuntimeError("No se pudo leer el SBOM generado") from None

    if not isinstance(data, dict) or data.get("bomFormat") != "CycloneDX":
        raise RuntimeError("El SBOM no es un documento CycloneDX")

    components = data.get("components", [])

    if not isinstance(components, list) or any(not isinstance(item, dict) for item in components):
        raise RuntimeError("El SBOM contiene una lista de componentes inválida")  # noqa: TRY004

    return len(components)


def _process_repository(
    clone: CloneResult,
    output_directory: Path,
    syft_version: str,
    executable: str,
    timeout: float,
) -> SBOMResult:
    full_name = clone.repository.full_name
    output = output_directory / f"{full_name}.json"
    commit = "unknown"
    generation_date = datetime.now(UTC)

    try:
        if clone.source is None:
            raise RuntimeError(clone.error or "El repositorio no pudo clonarse")
        source = clone.source
        commit = _get_commit(source)

        generate_sbom(
            source,
            output,
            executable=executable,
            timeout=timeout,
        )

        component_count = _count_components(output)

        return SBOMResult(
            full_name=full_name,
            commit=commit,
            generation_date=generation_date,
            syft_version=syft_version,
            status="generated",
            component_count=component_count,
            sbom_path=str(output),
        )

    except RuntimeError as error:
        return SBOMResult(
            full_name=full_name,
            commit=commit,
            generation_date=generation_date,
            syft_version=syft_version,
            status="failed",
            component_count=0,
            sbom_path=str(output),
            error=str(error),
        )


def generate_organization_sbom(
    organization: str,
    output: Path,
    *,
    workspace: Path | None = None,
    run_id: str | None = None,
    executable: str = "syft",
    timeout: float = 600,
    progress: Callable[[str], None] = print,
) -> SBOMReport:
    """Genera los SBOM de los repositorios del último scan."""

    organization = organization.strip()

    if not organization:
        raise ValueError("La organización no puede estar vacía")

    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")

    clones = load_latest_clones(organization, workspace=workspace, run_id=run_id)
    progress(f"Clones: {clones.workspace}")
    repositories = sorted(clones.repositories, key=lambda item: item.repository.full_name)
    syft_version = get_version(executable) if any(item.source is not None for item in repositories) else "unknown"
    sbom_directory = Path(mkdtemp(prefix="sbom-", dir=clones.workspace)).resolve()

    report = SBOMReport(
        organization=organization,
        repositories=[],
    )

    for index, clone in enumerate(repositories, 1):
        progress(f"[{index}/{len(repositories)}] {clone.repository.full_name}")

        result = _process_repository(
            clone,
            sbom_directory,
            syft_version,
            executable,
            timeout,
        )

        report.repositories.append(result)

        progress(f"  {result.status}" + (f": {result.error}" if result.error else ""))

        write_report(report, output)

    if not repositories:
        write_report(report, output)

    return report
