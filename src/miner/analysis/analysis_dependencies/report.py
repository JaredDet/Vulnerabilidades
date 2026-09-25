"""Escritura atómica del reporte de vulnerabilidades."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .models import VulnerabilityReport


def write_report(
    result: VulnerabilityReport,
    output: Path,
) -> Path:
    """Escribe el reporte validado de forma atómica."""

    ordered = VulnerabilityReport.model_validate_json(result.model_dump_json())
    ordered.repositories.sort(key=lambda repository: repository.full_name)

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(ordered.model_dump_json(indent=2) + "\n")

        os.replace(temporary, output)

    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return output
