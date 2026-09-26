import json
import subprocess
from pathlib import Path

from .constants import (
    DEFAULT_SCAN_TIMEOUT,
    DEFAULT_SYFT_EXECUTABLE,
    DEFAULT_VERSION_TIMEOUT,
    SYFT_SBOM_OUTPUT,
    SYFT_SCAN_COMMAND,
    SYFT_VERSION_COMMAND,
    SYFT_VERSION_OUTPUT,
)
from .errors import SBOMErrors


def get_version(executable: str = DEFAULT_SYFT_EXECUTABLE) -> str:
    """Devuelve la versión de Syft instalada."""
    try:
        result = subprocess.run(
            [
                executable,
                SYFT_VERSION_COMMAND,
                "--output",
                SYFT_VERSION_OUTPUT,
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=DEFAULT_VERSION_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise SBOMErrors.VersionTimeout from None
    except FileNotFoundError:
        raise SBOMErrors.SyftNotAvailable from None
    except subprocess.CalledProcessError:
        raise SBOMErrors.VersionFailed from None
    except OSError:
        raise SBOMErrors.SyftAccessFailed from None

    try:
        data = json.loads(result.stdout)
        version = data["version"]

        if not isinstance(version, str) or not version.strip():
            raise ValueError

    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        raise SBOMErrors.InvalidVersionResponse from None

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
        raise SBOMErrors.InvalidTimeout

    source = Path(source_path).resolve()
    output = Path(output_path).resolve()

    if not source.is_dir():
        raise SBOMErrors.SourceNotFound

    if output.exists():
        raise SBOMErrors.SbomAlreadyExists

    if output.is_relative_to(source):
        raise SBOMErrors.SbomInsideSource

    try:
        output.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                executable,
                SYFT_SCAN_COMMAND,
                str(source),
                f"--output={SYFT_SBOM_OUTPUT}={output}",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise SBOMErrors.SyftNotAvailable from None
    except subprocess.TimeoutExpired:
        raise SBOMErrors.GenerationTimeout from None
    except subprocess.CalledProcessError:
        raise SBOMErrors.GenerationFailed from None
    except OSError:
        raise SBOMErrors.SyftAccessFailed from None

    if not output.is_file():
        raise SBOMErrors.SbomNotGenerated

    return output
