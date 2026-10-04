"""Puntajes publicados por las herramientas; no se infieren de etiquetas."""

from pydantic import BaseModel, Field


class VulnerabilityScore(BaseModel):
    value: float = Field(ge=0, le=10, allow_inf_nan=False)
    system: str
    source: str
    version: str | None = None
    vector: str | None = None
    vulnerability_id: str | None = None
