"""Escritura atómica de resultados validados, con orden estable."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from .models import OrganizationResult


def write_report(
    result: OrganizationResult,
    output: Path,
) -> Path:
    """Escribe el resultado validado de forma atómica."""

    ordered = OrganizationResult.model_validate_json(result.model_dump_json())

    ordered.repositories.sort(key=lambda repo: repo.name)

    for repository in ordered.repositories:
        repository.languages.sort(key=lambda language: language.language)

        for language in repository.languages:
            language.findings.sort(
                key=lambda finding: (
                    finding.file or "",
                    finding.start_line or 0,
                    finding.rule_id,
                    finding.start_column or 0,
                    finding.message,
                    finding.severity or "",
                )
            )

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    temporary = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(ordered.model_dump_json(indent=2) + "\n")

        os.replace(temporary, output)

    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)

    return output
