"""Modelos de resultados del miner."""

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    computed_field,
    model_serializer,
)


class Repository(BaseModel):
    model_config = ConfigDict(
        frozen=True, strict=True, str_strip_whitespace=True, str_min_length=1
    )

    full_name: str
    clone_url: str


class Finding(BaseModel):
    """Hallazgo con su ubicación principal, cuando está disponible."""

    model_config = ConfigDict(frozen=True, strict=True)

    rule_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: Literal["none", "note", "warning", "error"] | None = None
    file: str | None = None
    start_line: int | None = Field(default=None, ge=1)
    start_column: int | None = Field(default=None, ge=1)


AnalysisStatus = Literal[
    "analyzed", "clone_failed", "unsupported", "language_detection_failed",
    "database_failed", "analysis_failed", "sarif_failed", "partial", "failed",
]


class LanguageResult(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    language: str
    status: AnalysisStatus
    error: str | None = None
    findings: list[Finding] = Field(default_factory=list)


class RepositoryResult(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    name: str
    url: str
    status: AnalysisStatus
    error: str | None = None
    detected_languages: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    analyses: list[LanguageResult] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)

    @computed_field
    @property
    def findings_count(self) -> int:
        return len(self.findings)


class Summary(BaseModel):
    repositories: int
    analyzed: int
    failed: int
    unsupported: int
    partial: int
    findings: int


class OrganizationResult(BaseModel):
    organization: str
    repositories: list[RepositoryResult]

    @model_serializer(mode="wrap")
    def serialize_report(self, handler: SerializerFunctionWrapHandler) -> dict:
        data = handler(self)
        return {key: data[key] for key in ("organization", "summary", "repositories") if key in data}

    @computed_field
    @property
    def summary(self) -> Summary:
        statuses = [repo.status for repo in self.repositories]
        return Summary(
            repositories=len(statuses), analyzed=statuses.count("analyzed"),
            unsupported=statuses.count("unsupported"), partial=statuses.count("partial"),
            failed=sum(status not in {
                       "analyzed", "unsupported", "partial"} for status in statuses),
            findings=sum(repo.findings_count for repo in self.repositories),
        )
