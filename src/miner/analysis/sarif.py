"""Convierte los resultados SARIF 2.1.0 de CodeQL a hallazgos del miner."""

import json
from pathlib import Path
from urllib.parse import unquote

from .models import Finding


class SarifError(RuntimeError):
    """No se pudo leer o interpretar el SARIF."""


def _indexed(items: list, index: int) -> dict:
    if type(index) is not int or not 0 <= index < len(items):
        raise SarifError("El SARIF contiene un índice inválido")
    return items[index]


def _parse_finding(result: dict, run: dict) -> Finding:
    rules = run.get("tool", {}).get("driver", {}).get("rules", [])
    rule = (
        _indexed(rules, result["ruleIndex"])
        if "ruleIndex" in result
        else next((rule for rule in rules if rule.get("id") == result.get("ruleId")), {})
    )
    rule_id = result.get("ruleId", rule.get("id"))
    if rule.get("id") and rule_id != rule["id"]:
        raise SarifError("La regla del hallazgo no coincide con su índice")
    message = result["message"]
    locations = result.get("locations", [])
    physical = locations[0].get("physicalLocation", {}) if locations else {}
    artifact = physical.get("artifactLocation", {})
    if "uri" not in artifact and "index" in artifact:
        artifact = _indexed(run.get("artifacts", []), artifact["index"])["location"]
    uri = artifact.get("uri")
    region = physical.get("region", {})
    return Finding(
        rule_id=rule_id,
        message=message.get("text", message.get("markdown")),
        severity=result.get("level", rule.get("defaultConfiguration", {}).get("level")),
        file=unquote(uri) if uri is not None else None,
        start_line=region.get("startLine"),
        start_column=region.get("startColumn"),
    )


def parse_sarif(sarif_path: Path) -> list[Finding]:
    """Lee todos los runs y devuelve hallazgos ordenados por archivo, línea y regla.

    Conserva resultados sin ubicación usando None. Extrae la primera ubicación
    de cada resultado; los flujos y ubicaciones relacionadas no se incluyen.
    Lanza SarifError ante datos inválidos, sin devolver resultados parciales.
    """
    try:
        data = json.loads(Path(sarif_path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        raise SarifError("No se pudo leer el SARIF como JSON UTF-8") from None
    try:
        if data.get("version") != "2.1.0" or not isinstance(data.get("runs"), list):
            raise SarifError("Se esperaba un SARIF 2.1.0 con una lista de runs")
        findings = []
        for run in data["runs"]:
            if any(invocation.get("executionSuccessful") is False
                   for invocation in run.get("invocations", [])):
                raise SarifError("El SARIF indica que la ejecución del análisis falló")
            results = run.get("results", [])
            if not isinstance(results, list):
                raise SarifError("El SARIF contiene resultados inválidos")
            findings.extend(_parse_finding(result, run) for result in results)
    except (AttributeError, KeyError, TypeError, ValueError, IndexError):
        raise SarifError("El SARIF contiene un hallazgo o estructura inválida") from None
    return sorted(findings, key=lambda finding: (
        finding.file or "", finding.start_line or 0, finding.rule_id,
        finding.start_column or 0, finding.message, finding.severity or "",
    ))
