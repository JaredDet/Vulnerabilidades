"""Convierte los resultados SARIF 2.1.0 de CodeQL a hallazgos del miner."""

import json
from pathlib import Path
from urllib.parse import unquote

from .constants import SARIF_ENCODING, SARIF_VERSION
from .errors import SarifErrors
from .models import Finding


def _load_sarif(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding=SARIF_ENCODING))
    except (OSError, ValueError):
        raise SarifErrors.InvalidJson from None


def _validate_sarif(data: dict) -> list:
    if data.get("version") != SARIF_VERSION or not isinstance(data.get("runs"), list):
        raise SarifErrors.InvalidDocument

    return data["runs"]


def _validate_run(run: dict) -> None:
    if any(
        invocation.get("executionSuccessful") is False
        for invocation in run.get("invocations", [])
    ):
        raise SarifErrors.AnalysisFailed


def _get_rule(result: dict, run: dict) -> dict:
    rules = run.get("tool", {}).get("driver", {}).get("rules", [])

    if "ruleIndex" in result:
        index = result["ruleIndex"]

        if type(index) is not int or not 0 <= index < len(rules):
            raise SarifErrors.InvalidIndex

        return rules[index]

    return next(
        (rule for rule in rules if rule.get("id") == result.get("ruleId")),
        {},
    )


def _get_artifact(result: dict, run: dict) -> dict:
    locations = result.get("locations", [])

    if not locations:
        return {}

    physical = locations[0].get("physicalLocation", {})
    artifact = physical.get("artifactLocation", {})

    if "uri" in artifact:
        return artifact

    if "index" not in artifact:
        return {}

    artifacts = run.get("artifacts", [])
    index = artifact["index"]

    if type(index) is not int or not 0 <= index < len(artifacts):
        raise SarifErrors.InvalidIndex

    return artifacts[index]["location"]


def _get_location(result: dict, run: dict) -> tuple[str | None, int | None, int | None]:
    locations = result.get("locations", [])

    if not locations:
        return None, None, None

    physical = locations[0].get("physicalLocation", {})
    artifact = _get_artifact(result, run)
    uri = artifact.get("uri")
    region = physical.get("region", {})

    return (
        unquote(uri) if uri is not None else None,
        region.get("startLine"),
        region.get("startColumn"),
    )


def _parse_finding(result: dict, run: dict) -> Finding:
    rule = _get_rule(result, run)
    rule_id = result.get("ruleId", rule.get("id"))

    if rule.get("id") and rule_id != rule["id"]:
        raise SarifErrors.RuleMismatch

    file, start_line, start_column = _get_location(result, run)
    message = result["message"]

    return Finding(
        rule_id=rule_id,
        message=message.get("text", message.get("markdown")),
        severity=result.get(
            "level",
            rule.get("defaultConfiguration", {}).get("level"),
        ),
        file=file,
        start_line=start_line,
        start_column=start_column,
    )


def _parse_run(run: dict) -> list[Finding]:
    _validate_run(run)

    results = run.get("results", [])

    if not isinstance(results, list):
        raise SarifErrors.InvalidResults

    return [_parse_finding(result, run) for result in results]


def parse_sarif(sarif_path: Path) -> list[Finding]:
    """Lee un SARIF y devuelve sus hallazgos ordenados."""
    try:
        runs = _validate_sarif(_load_sarif(sarif_path))
        findings = [finding for run in runs for finding in _parse_run(run)]
    except (
        AttributeError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
    ):
        raise SarifErrors.InvalidStructure from None

    return sorted(
        findings,
        key=lambda finding: (
            finding.file or "",
            finding.start_line or 0,
            finding.rule_id,
            finding.start_column or 0,
            finding.message,
            finding.severity or "",
        ),
    )
