"""Modelos de resultados de generación de SBOM."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SBOMStatus = Literal["generated", "failed"]


class SBOMResult(BaseModel):
    """Resultado de la generación del SBOM de un repositorio."""

    model_config = ConfigDict(
        frozen=True,
        strict=True,
        str_strip_whitespace=True,
    )

    full_name: str = Field(min_length=1)
    commit: str = Field(min_length=1)
    generation_date: datetime
    syft_version: str = Field(min_length=1)
    status: SBOMStatus
    component_count: int = Field(ge=0)
    sbom_path: str = Field(min_length=1)
    error: str | None = None


class SBOMReport(BaseModel):
    """Resultados de generación de SBOM de una organización."""

    model_config = ConfigDict(frozen=True, strict=True)

    organization: str = Field(min_length=1)
    repositories: list[SBOMResult] = Field(default_factory=list)
