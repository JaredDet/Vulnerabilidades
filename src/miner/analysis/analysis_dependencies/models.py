"""Modelos de resultados del análisis de vulnerabilidades."""

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.dataclasses import dataclass

VulnerabilityStatus = Literal["analyzed", "failed"]


@dataclass(frozen=True)
class GrypeExecution:
    output_directory: Path
    grype_version: str
    executable: str
    timeout: float


class VulnerabilityResult(BaseModel):
    """Resultado del análisis de vulnerabilidades de un repositorio."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    full_name: str = Field(min_length=1)
    commit: str = Field(min_length=1)
    analysis_date: datetime
    grype_version: str = Field(min_length=1)
    status: VulnerabilityStatus
    vulnerability_count: int = Field(ge=0)
    report_path: str = Field(min_length=1)
    error: str | None = None


class VulnerabilityReport(BaseModel):
    """Resultados del análisis de vulnerabilidades de una organización."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
    )

    organization: str = Field(min_length=1)
    repositories: list[VulnerabilityResult] = Field(default_factory=list)
