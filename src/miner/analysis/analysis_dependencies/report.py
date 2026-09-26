"""Escritura atómica del reporte de vulnerabilidades."""

from pathlib import Path

from core.filesystem import save_data_atomic

from .models import VulnerabilityReport


def write_report(
    result: VulnerabilityReport,
    output: Path,
) -> Path:
    """Escribe el reporte validado de forma atómica."""
    ordered = VulnerabilityReport.model_validate_json(result.model_dump_json())

    ordered.repositories.sort(key=lambda repository: repository.full_name)

    output = output.resolve()

    save_data_atomic(
        output,
        ordered.model_dump_json(indent=2) + "\n",
    )

    return output
