"""Comprueba que el reporte cite solo evidencia presente en el JSON."""

import argparse
import json
import re
import sys
from pathlib import Path

REPORT_LIMIT = 65000
NARRATED = {"critical", "high", "medium", "error", "warning"}
REQUIRED_SECTIONS = (
    "# Reporte de seguridad",
    "## Cobertura",
    "## Hallazgos",
    "## Sin evidencia suficiente",
)
HEADING = re.compile(
    r"^###\s+((?:F\d{3,})(?:\s*,\s*F\d{3,})*)\s+[—-]\s+(\S+)\s+\(([^)]+)\)\s*$",
    re.MULTILINE,
)
FENCE = re.compile(r"```(\d+):(\d+):([^\n]+)\n(.*?)```", re.DOTALL)
FINDING_ID = re.compile(r"\bF\d{3,}\b")
CVE_ID = re.compile(r"\bCVE-\d{4}-\d+\b")
GHSA_ID = re.compile(r"\bGHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}\b", re.IGNORECASE)
CODEQL_ID = re.compile(r"\b(?:py|js|javascript)/[a-z0-9-]+\b")


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").rstrip("\n")


def normalize_report(report: str) -> str:
    """Quita encabezados prematuros de Otros hallazgos insertados entre secciones narradas."""
    text = report.replace("\r\n", "\n")
    parts = re.split(r"(?=^## Otros hallazgos\s*$)", text, flags=re.MULTILINE)
    if len(parts) <= 2:
        return text
    cleaned = parts[0]
    for section in parts[1:-1]:
        cleaned += re.sub(
            r"^## Otros hallazgos\s*\n+(?:\|[^\n]*\n)*",
            "",
            section,
            count=1,
        )
    return cleaned + parts[-1]


def validate(evidence: dict, report: str) -> list[str]:
    """Devuelve los incumplimientos. Una lista vacía significa que el reporte es válido."""
    errors = []
    findings = evidence.get("findings") or []
    by_id = {finding["id"]: finding for finding in findings}
    identifiers = {finding["identifier"] for finding in findings}

    if len(report) > REPORT_LIMIT:
        errors.append(f"El reporte supera {REPORT_LIMIT} caracteres.")

    commit = evidence.get("commit")
    if not commit or commit not in report:
        errors.append("El reporte no incluye el commit de la evidencia.")

    repository = evidence.get("repository")
    if not repository or repository not in report:
        errors.append("El reporte no incluye el repositorio de la evidencia.")

    for section in REQUIRED_SECTIONS:
        if section not in report:
            errors.append(f"Falta la sección {section}.")

    for tool in evidence.get("tools") or []:
        if tool.get("name") and tool["name"] not in report:
            errors.append(f"La cobertura no menciona la herramienta {tool['name']}.")
        status = tool.get("status")
        if status and status not in report:
            errors.append(f"La cobertura no menciona el estado {status}.")

    for finding_id in FINDING_ID.findall(report):
        if finding_id not in by_id:
            errors.append(f"{finding_id} no está en la evidencia.")

    for finding in findings:
        if finding["id"] not in report:
            errors.append(f"El reporte omite {finding['id']}.")

    for pattern in (CVE_ID, GHSA_ID, CODEQL_ID):
        for identifier in pattern.findall(report):
            if identifier not in identifiers:
                errors.append(f"El identificador {identifier} no está en la evidencia.")

    heading_ids = set()
    for match in HEADING.finditer(report):
        ids = FINDING_ID.findall(match.group(1))
        identifier = match.group(2)
        severity = match.group(3)
        heading_ids.update(ids)
        for finding_id in ids:
            finding = by_id.get(finding_id)
            if finding is None:
                continue
            if finding["identifier"] != identifier:
                errors.append(f"{finding_id} no corresponde a {identifier}.")
            if finding["severity"].lower() != severity.lower():
                errors.append(f"{finding_id} no tiene severidad {severity}.")

    for finding in findings:
        if finding["severity"].lower() in NARRATED and finding["id"] not in heading_ids:
            errors.append(f"{finding['id']} debe narrarse en un encabezado de tercer nivel.")

    sections = re.split(r"(?=^###\s)", report, flags=re.MULTILINE)
    for section in sections:
        heading = HEADING.search(section)
        if heading is None:
            continue
        if "**Mitigación:**" not in section:
            errors.append(f"La sección {heading.group(1)} no tiene mitigación.")
        ids = FINDING_ID.findall(heading.group(1))
        sources = {by_id[finding_id]["source"] for finding_id in ids if finding_id in by_id}
        if sources == {"grype"} and "```" in section:
            errors.append(f"La sección {heading.group(1)} es de Grype y no lleva bloque de código.")

    for match in FENCE.finditer(report):
        start_line = int(match.group(1))
        file = match.group(3).strip()
        body = _normalize(match.group(4))
        matches = [
            finding for finding in findings
            if finding.get("snippet")
            and finding["location"]["file"] == file
            and finding["snippet"]["start_line"] == start_line
            and _normalize(finding["snippet"]["text"]) == body
        ]
        if not matches:
            errors.append(f"El snippet de {file}:{start_line} no coincide con la evidencia.")

    for finding in findings:
        snippet = finding.get("snippet")
        if not snippet or finding["severity"].lower() not in NARRATED:
            continue
        if _normalize(snippet["text"]) not in _normalize(report):
            errors.append(f"El snippet de {finding['id']} no aparece verbatim.")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida el reporte de seguridad contra la evidencia.")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    report = normalize_report(args.report.read_text(encoding="utf-8"))
    args.report.write_text(report, encoding="utf-8")
    errors = validate(evidence, report)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
