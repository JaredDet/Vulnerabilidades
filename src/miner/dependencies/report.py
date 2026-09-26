"""Escritura atómica del reporte de vulnerabilidades."""

from pathlib import Path

from core.reporting import write_json_report

from .models import VulnerabilityReport


def _order_report(result: VulnerabilityReport) -> None:
    result.repositories.sort(key=lambda repository: repository.full_name)


def write_report(
    result: VulnerabilityReport,
    output: Path,
) -> Path:
    """Escribe el reporte validado de forma atómica."""
    return write_json_report(result, output, order=_order_report)
