"""Funciones compartidas para persistir reportes Pydantic como JSON."""

from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from core.filesystem import save_data_atomic

Report = TypeVar("Report", bound=BaseModel)


def write_json_report(
    report: Report,
    output: Path,
    *,
    order: Callable[[Report], None],
) -> Path:
    """Valida una copia ordenada del reporte y la escribe atómicamente."""
    ordered = type(report).model_validate_json(report.model_dump_json())
    order(ordered)

    output = output.resolve()
    save_data_atomic(output, ordered.model_dump_json(indent=2) + "\n")

    return output
