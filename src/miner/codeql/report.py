from pathlib import Path

from core.reporting import write_json_report

from .models import OrganizationResult


def _order_findings(findings: list) -> None:
    findings.sort(
        key=lambda finding: (
            finding.file or "",
            finding.start_line or 0,
            finding.rule_id,
            finding.start_column or 0,
            finding.message,
            finding.severity or "",
        )
    )


def _order_result(result: OrganizationResult) -> None:
    result.repositories.sort(key=lambda repository: repository.name)

    for repository in result.repositories:
        repository.languages.sort(key=lambda language: language.language)

        for language in repository.languages:
            _order_findings(language.findings)


def write_report(result: OrganizationResult, output: Path) -> Path:
    """Escribe el resultado validado de forma atómica."""
    return write_json_report(result, output, order=_order_result)
