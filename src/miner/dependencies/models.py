"""Modelos de resultados del análisis de vulnerabilidades."""

from datetime import datetime
from pathlib import Path
from typing import Literal
from miner.scores import VulnerabilityScore

from pydantic import BaseModel, ConfigDict, Field
from pydantic.dataclasses import dataclass

VulnerabilityStatus = Literal["analyzed", "failed"]


@dataclass(frozen=True)
class GrypeExecution:
    output_directory: Path
    grype_version: str
    executable: str
    timeout: float


class VulnerabilityFinding(BaseModel):
    """Coincidencia de Grype; el repositorio y commit pertenecen al resultado padre."""

    model_config = ConfigDict(frozen=True, strict=True)

    vulnerability_id: str = Field(min_length=1)
    scores: list[VulnerabilityScore] = Field(default_factory=list)
    description: str | None = None
    severity: str | None = None
    package: str = Field(min_length=1)
    version: str
    package_type: str | None = None
    locations: list[str] = Field(default_factory=list)


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
    findings: list[VulnerabilityFinding] = Field(default_factory=list)
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
