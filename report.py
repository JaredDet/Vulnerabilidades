"""Escritura atómica de resultados validados, con orden estable."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from models import OrganizationResult


def write_report(result: OrganizationResult, output: Path) -> Path:
    # Revalidar también los modelos que pudieron modificarse durante el escaneo.
    ordered = OrganizationResult.model_validate_json(result.model_dump_json())
    ordered.repositories.sort(key=lambda repo: repo.name)
    for repo in ordered.repositories:
        repo.languages.sort()
        repo.detected_languages.sort()
        repo.analyses.sort(key=lambda analysis: analysis.language)
        for findings in [repo.findings, *(analysis.findings for analysis in repo.analyses)]:
            findings.sort(key=lambda f: (f.file or "", f.start_line or 0, f.rule_id,
                                        f.start_column or 0, f.message, f.severity or ""))
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(ordered.model_dump_json(indent=2) + "\n")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output
