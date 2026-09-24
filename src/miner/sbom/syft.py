import json
import subprocess
from pathlib import Path

DEFAULT_SYFT_EXECUTABLE = "syft"
DEFAULT_SCAN_TIMEOUT = 600


class SyftError(RuntimeError):
    """No se pudo ejecutar Syft o interpretar su respuesta."""


def get_version(
    executable: str = DEFAULT_SYFT_EXECUTABLE,
) -> str:
    """Devuelve la versión de Syft instalada."""

    try:
        result = subprocess.run(
            [
                executable,
                "version",
                "--output",
                "json",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )

    except subprocess.TimeoutExpired:
        raise SyftError("Se agotó el tiempo al consultar la versión de Syft") from None

    except FileNotFoundError:
        raise SyftError("No se encontró Syft o una ruta necesaria") from None

    except subprocess.CalledProcessError as error:
        raise SyftError(
            f"Syft no pudo obtener su versión (código {error.returncode})"
        ) from None

    except OSError:
        raise SyftError("No se pudo ejecutar Syft") from None

    try:
        data = json.loads(result.stdout)
        version = data["version"]

        if not isinstance(version, str) or not version.strip():
            raise ValueError

    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise SyftError("Syft devolvió una versión con formato inválido") from None

    return version.strip()


def generate_sbom(
    source_path: Path,
    output_path: Path,
    *,
    executable: str = DEFAULT_SYFT_EXECUTABLE,
    timeout: float = DEFAULT_SCAN_TIMEOUT,
) -> Path:
    """Genera un SBOM CycloneDX JSON para un directorio."""

    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")

    try:
        source = Path(source_path).resolve()
        output = Path(output_path).resolve()

        if not source.is_dir():
            raise SyftError("La carpeta del repositorio no existe")

        if output.exists():
            raise SyftError(f"El archivo SBOM ya existe: {output}")

        if output.is_relative_to(source):
            raise SyftError("El SBOM debe quedar fuera de la carpeta del repositorio")

        output.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                executable,
                "scan",
                str(source),
                f"--output=cyclonedx-json={output}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    except FileNotFoundError:
        raise SyftError("No se encontró Syft o una ruta necesaria") from None

    except subprocess.TimeoutExpired:
        raise SyftError("Se agotó el tiempo al generar el SBOM") from None

    except subprocess.CalledProcessError as error:
        raise SyftError(
            f"Syft no pudo generar el SBOM (código {error.returncode})"
        ) from None

    except OSError:
        raise SyftError("No se pudo ejecutar Syft o acceder a sus archivos") from None

    if not output.is_file():
        raise SyftError("Syft terminó sin generar el archivo SBOM")

    return output
