"""Convierte las coincidencias del JSON de Grype en hallazgos estructurados."""

import json
from pathlib import Path

from .errors import GrypeErrors
from .models import VulnerabilityFinding


def parse_grype(path: Path) -> list[VulnerabilityFinding]:
    """Lee matches sin deduplicar vulnerabilidades de paquetes distintos."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        matches = data["matches"]
        if not isinstance(matches, list):
            raise ValueError("matches debe ser una lista")

        findings = []
        for match in matches:
            vulnerability = match["vulnerability"]
            artifact = match["artifact"]
            locations = artifact.get("locations", [])
            if not isinstance(locations, list):
                raise ValueError("locations debe ser una lista")
            findings.append(VulnerabilityFinding(
                vulnerability_id=vulnerability["id"],
                description=vulnerability.get("description"),
                severity=vulnerability.get("severity"),
                package=artifact["name"],
                version=artifact["version"],
                package_type=artifact.get("type"),
                locations=[location["path"] for location in locations],
            ))
        return findings
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise GrypeErrors.InvalidResults from None
