from pathlib import Path

from core.filesystem import save_data_atomic

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


def _order_result(result: OrganizationResult) -> OrganizationResult:
    ordered = OrganizationResult.model_validate_json(result.model_dump_json())

    ordered.repositories.sort(key=lambda repository: repository.name)

    for repository in ordered.repositories:
        repository.languages.sort(key=lambda language: language.language)

        for language in repository.languages:
            _order_findings(language.findings)

    return ordered


def write_report(result: OrganizationResult, output: Path) -> Path:
    """Escribe el resultado validado de forma atómica."""
    ordered = _order_result(result)
    output = output.resolve()

    save_data_atomic(
        output,
        ordered.model_dump_json(indent=2) + "\n",
    )

    return output
