"""Modelos de resultados del análisis con CodeQL."""

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    computed_field,
    model_serializer,
)


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
    "analyzed",
    "clone_failed",
    "unsupported",
    "language_detection_failed",
    "database_failed",
    "analysis_failed",
    "sarif_failed",
    "partial",
    "failed",
]


class LanguageResult(BaseModel):
    """Resultado del análisis de un lenguaje."""

    model_config = ConfigDict(validate_assignment=True)

    language: str
    status: AnalysisStatus
    error: str | None = None
    findings: list[Finding] = Field(default_factory=list)

    @computed_field
    @property
    def findings_count(self) -> int:
        return len(self.findings)


class RepositoryResult(BaseModel):
    """Resultado del análisis CodeQL de un repositorio."""

    model_config = ConfigDict(validate_assignment=True)

    name: str
    url: str
    status: AnalysisStatus
    error: str | None = None
    languages: list[LanguageResult] = Field(default_factory=list)

    @computed_field
    @property
    def findings(self) -> list[Finding]:
        return [finding for language in self.languages for finding in language.findings]

    @computed_field
    @property
    def findings_count(self) -> int:
        return sum(language.findings_count for language in self.languages)


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
    def serialize_report(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict:
        data = handler(self)
        return {
            key: data[key]
            for key in ("organization", "summary", "repositories")
            if key in data
        }

    @computed_field
    @property
    def summary(self) -> Summary:
        statuses = [repo.status for repo in self.repositories]

        return Summary(
            repositories=len(statuses),
            analyzed=statuses.count("analyzed"),
            unsupported=statuses.count("unsupported"),
            partial=statuses.count("partial"),
            failed=sum(
                status
                not in {
                    "analyzed",
                    "unsupported",
                    "partial",
                }
                for status in statuses
            ),
            findings=sum(repo.findings_count for repo in self.repositories),
        )
