"""Integra evidencia de una misma ejecución de clones sin ejecutar herramientas."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from core.exceptions import AppException, ErrorType
from core.filesystem import save_data_atomic

from .clone.models import OrganizationCloneResult
from .codeql.models import OrganizationResult
from .codeql.sarif import parse_sarif
from .scores import VulnerabilityScore
from .dependencies.models import VulnerabilityReport
from .dependencies.parser import parse_grype


class DatasetFinding(BaseModel):
    repository: str
    tool: Literal["codeql", "grype"]
    vulnerability_id: str
    scores: list[VulnerabilityScore] = Field(default_factory=list)
    description: str | None = None
    severity: str | None = None
    severity_kind: Literal["sarif_level", "vulnerability_severity"]
    locations: list[str] = Field(default_factory=list)
    start_line: int | None = None
    start_column: int | None = None
    language: str | None = None
    package: str | None = None
    version: str | None = None
    package_type: str | None = None
    commit: str | None = None
    source_report: str


class DatasetRepository(BaseModel):
    repository: str
    clone_status: str
    codeql_status: str = "not_run"
    grype_status: str = "not_run"
    clone_error: str | None = None
    codeql_error: str | None = None
    grype_error: str | None = None


class Dataset(BaseModel):
    schema_version: str = "1.1"
    organization: str
    clone_run: str
    source_reports: dict[str, str] = Field(default_factory=dict)
    repositories: list[DatasetRepository]
    findings: list[DatasetFinding]

    @computed_field
    @property
    def findings_count(self) -> int:
        return len(self.findings)


def _latest_report(root: Path, pattern: str) -> Path | None:
    reports = list(root.glob(pattern))
    return max(reports, key=lambda p: (p.stat().st_mtime_ns, str(p))) if reports else None


def generate_dataset(clones: OrganizationCloneResult) -> Path:
    """Selecciona el último reporte terminado de cada herramienta en estos clones."""
    root = clones.workspace.resolve()
    codeql_path = _latest_report(root, "analysis_results/codeql-*/codeql-results.json")
    grype_path = _latest_report(root, "vulnerabilities/vulnerability-*/vulnerability-results.json")
    repositories = {
        item.repository.full_name: DatasetRepository(
            repository=item.repository.full_name, clone_status=item.status, clone_error=item.error,
        ) for item in clones.repositories
    }
    findings = []
    sources = {}
    try:
        if codeql_path:
            report = OrganizationResult.model_validate_json(codeql_path.read_text(encoding="utf-8"))
            if report.organization != clones.organization:
                raise ValueError("Organización distinta")
            sources["codeql"] = str(codeql_path.relative_to(root))
            for repo in report.repositories:
                entry = repositories[repo.name]
                entry.codeql_status, entry.codeql_error = repo.status, repo.error
                for language in repo.languages:
                    sarif = codeql_path.parent / repo.name.replace("/", "-") / language.language / "results.sarif"
                    language_findings = (
                        parse_sarif(sarif) if language.status == "analyzed" and sarif.is_file()
                        else language.findings
                    )
                    for finding in language_findings:
                        findings.append(DatasetFinding(
                            repository=repo.name, tool="codeql", vulnerability_id=finding.rule_id,
                            description=finding.message, severity=finding.severity,
                            scores=finding.scores,
                            severity_kind="sarif_level", language=language.language,
                            locations=[finding.file] if finding.file else [],
                            start_line=finding.start_line, start_column=finding.start_column,
                            source_report=sources["codeql"],
                        ))
        if grype_path:
            report = VulnerabilityReport.model_validate_json(grype_path.read_text(encoding="utf-8"))
            if report.organization != clones.organization:
                raise ValueError("Organización distinta")
            sources["grype"] = str(grype_path.relative_to(root))
            for repo in report.repositories:
                entry = repositories[repo.full_name]
                entry.grype_status, entry.grype_error = repo.status, repo.error
                if repo.status != "analyzed":
                    continue
                raw = Path(repo.report_path).resolve()
                raw.relative_to(root)
                for finding in parse_grype(raw):
                    findings.append(DatasetFinding(
                        repository=repo.full_name, tool="grype",
                        vulnerability_id=finding.vulnerability_id, description=finding.description,
                        scores=finding.scores,
                        severity=finding.severity, severity_kind="vulnerability_severity",
                        locations=finding.locations, package=finding.package, version=finding.version,
                        package_type=finding.package_type, commit=repo.commit,
                        source_report=str(raw.relative_to(root)),
                    ))
    except (ValueError, KeyError) as error:
        raise AppException("invalid_dataset_source", "Los reportes no corresponden a estos clones o son inválidos", ErrorType.VALIDATION) from error
    dataset = Dataset(
        organization=clones.organization, clone_run=root.name, source_reports=sources,
        repositories=sorted(repositories.values(), key=lambda r: r.repository),
        findings=sorted(findings, key=lambda f: (f.repository, f.tool, f.vulnerability_id, f.package or "")),
    )
    output = root / "dataset.json"
    save_data_atomic(output, dataset.model_dump_json(indent=2) + "\n")
    return output
