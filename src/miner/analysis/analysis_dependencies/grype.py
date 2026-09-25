"""Interacción con Grype CLI."""

import subprocess
from pathlib import Path

DEFAULT_GRYPE_EXECUTABLE = "grype"
DEFAULT_SCAN_TIMEOUT = 600


class GrypeError(RuntimeError):
    """No se pudo ejecutar Grype o interpretar su resultado."""


def get_version(
    executable: str = DEFAULT_GRYPE_EXECUTABLE,
) -> str:
    """Obtiene la versión instalada de Grype."""
    try:
        result = subprocess.run(
            [executable, "version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise GrypeError("No se encontró Grype") from None
    except subprocess.TimeoutExpired:
        raise GrypeError("Grype excedió el tiempo al obtener su versión") from None
    except subprocess.CalledProcessError:
        raise GrypeError("No se pudo obtener la versión de Grype") from None
    except OSError:
        raise GrypeError("No se pudo ejecutar Grype") from None

    version = result.stdout.strip()
    if not version:
        raise GrypeError("Grype no devolvió su versión")

    return version


def scan_vulnerabilities(
    sbom_path: Path,
    output_path: Path,
    *,
    executable: str = DEFAULT_GRYPE_EXECUTABLE,
    timeout: float = DEFAULT_SCAN_TIMEOUT,
) -> Path:
    """Analiza un SBOM con Grype y guarda el resultado en JSON."""
    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")

    try:
        sbom = Path(sbom_path).resolve()
        output = Path(output_path).resolve()

        if not sbom.is_file():
            raise GrypeError("El archivo SBOM no existe")

        if output.exists():
            raise GrypeError(f"El archivo de resultados ya existe: {output}")

        output.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                executable,
                f"sbom:{sbom}",
                "--output=json",
                f"--file={output}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    except FileNotFoundError:
        raise GrypeError("No se encontró Grype o una ruta necesaria") from None

    except subprocess.TimeoutExpired:
        raise GrypeError("Se agotó el tiempo al buscar vulnerabilidades") from None

    except subprocess.CalledProcessError as error:
        raise GrypeError(
            f"Grype no pudo completar el análisis (código {error.returncode})"
        ) from None

    except OSError:
        raise GrypeError("No se pudo ejecutar Grype o acceder a sus archivos") from None

    if not output.is_file():
        raise GrypeError("Grype terminó sin generar el archivo de resultados")

    return output
