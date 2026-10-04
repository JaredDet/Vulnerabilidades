"""Interacción con Grype CLI."""

import subprocess
from pathlib import Path

from .constants import (
    DEFAULT_GRYPE_EXECUTABLE,
    DEFAULT_SCAN_TIMEOUT,
    DEFAULT_VERSION_TIMEOUT,
)
from .errors import GrypeErrors


def get_version(
    executable: str = DEFAULT_GRYPE_EXECUTABLE,
) -> str:
    """Obtiene la versión instalada de Grype."""
    try:
        result = subprocess.run(
            [
                executable,
                "version",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=DEFAULT_VERSION_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise GrypeErrors.VersionTimeout from None
    except subprocess.CalledProcessError:
        raise GrypeErrors.VersionFailed from None
    except OSError:
        raise GrypeErrors.GrypeAccessFailed from None

    version = result.stdout.strip()

    if not version:
        raise GrypeErrors.VersionFailed

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
        raise GrypeErrors.InvalidTimeout

    sbom = Path(sbom_path).resolve()
    output = Path(output_path).resolve()

    if not sbom.is_file():
        raise GrypeErrors.SBOMFileNotFound

    if output.exists():
        raise GrypeErrors.ResultAlreadyExists

    try:
        output.parent.mkdir(parents=True, exist_ok=True)

        subprocess.run(
            [
                executable,
                f"sbom:{sbom}",
                f"--file={output}",
                "--output=json",
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise GrypeErrors.ScanTimeout from None
    except subprocess.CalledProcessError:
        raise GrypeErrors.ScanFailed from None
    except OSError:
        raise GrypeErrors.GrypeAccessFailed from None

    if not output.is_file():
        raise GrypeErrors.ResultsNotGenerated

    return output
