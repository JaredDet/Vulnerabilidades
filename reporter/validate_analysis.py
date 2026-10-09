"""Sanea y comprueba el JSON de análisis antes de renderizar el reporte."""

import argparse
import json
import re
import sys
from pathlib import Path

FIX_KINDS = {"snippet", "command"}


def _load_object(text: str) -> dict:
    stripped = text.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, re.DOTALL)
    if fenced:
        stripped = fenced.group(1).strip()
    start = stripped.find("{")
    if start < 0:
        raise ValueError("El análisis no contiene un objeto JSON.")
    try:
        value, _ = json.JSONDecoder().raw_decode(stripped[start:])
    except json.JSONDecodeError as error:
        raise ValueError("El análisis no es JSON válido.") from error
    if not isinstance(value, dict):
        raise ValueError("El análisis no es un objeto JSON.")
    return value


def _required_text(item: dict, field: str, label: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} no tiene {field}.")
    return value.strip()


def _normalize_fix(item: dict, label: str) -> None:
    if "fix" not in item or item["fix"] is None:
        item["fix"] = None
        return
    fix = item["fix"]
    if fix == {} or fix == "":
        item["fix"] = None
        return
    if not isinstance(fix, dict):
        raise ValueError(f"{label} tiene un fix que no es un objeto.")
    text = fix.get("text")
    if not isinstance(text, str) or not text.strip():
        item["fix"] = None
        return
    kind = fix.get("kind")
    if kind not in FIX_KINDS:
        raise ValueError(f"{label} tiene un fix.kind distinto de snippet o command.")
    item["fix"] = {"kind": kind, "text": text.strip()}


def sanitize(text: str, evidence: dict) -> dict:
    """Devuelve el análisis listo para renderizar, o lanza ValueError."""
    raw = _load_object(text)
    schema_version = raw.get("schema_version")
    if not isinstance(schema_version, str) or not schema_version.strip():
        raise ValueError("Falta schema_version.")
    executive_summary = raw.get("executive_summary")
    if not isinstance(executive_summary, str) or not executive_summary.strip():
        raise ValueError("Falta executive_summary.")
    analyses = raw.get("analyses")
    if not isinstance(analyses, list):
        raise ValueError("analyses no es una lista.")

    groups_by_id: dict[str, dict] = {}
    required: set[str] = set()
    for group in evidence.get("groups") or []:
        for finding in group.get("findings") or []:
            finding_id = finding.get("id")
            if not isinstance(finding_id, str):
                continue
            groups_by_id[finding_id] = group
            if group.get("analyze") is True:
                required.add(finding_id)

    seen: list[str] = []
    cleaned = []
    for index, item in enumerate(analyses, start=1):
        label = f"analyses[{index}]"
        if not isinstance(item, dict):
            raise ValueError(f"{label} no es un objeto.")
        ids = item.get("ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(value, str) and value for value in ids):
            raise ValueError(f"{label} no tiene ids.")
        identifier = _required_text(item, "identifier", label)
        relevance = _required_text(item, "relevance", label)
        mitigation = _required_text(item, "mitigation", label)
        _normalize_fix(item, label)

        groups = []
        for finding_id in ids:
            group = groups_by_id.get(finding_id)
            if group is None:
                raise ValueError(f"{label} cita {finding_id}, que no está en la evidencia.")
            if group.get("analyze") is not True:
                raise ValueError(f"{label} cita {finding_id}, que no requiere análisis.")
            groups.append(group)
        if len({id(group) for group in groups}) != 1:
            raise ValueError(f"{label} mezcla ids de grupos distintos.")
        if groups[0]["identifier"] != identifier:
            raise ValueError(f"{label} usa un identifier distinto al del grupo.")
        seen.extend(ids)
        cleaned.append({
            "ids": ids,
            "identifier": identifier,
            "relevance": relevance,
            "mitigation": mitigation,
            "fix": item["fix"],
        })

    if len(seen) != len(set(seen)):
        raise ValueError("Un id aparece en más de un análisis.")
    missing = sorted(required - set(seen))
    extra = sorted(set(seen) - required)
    if missing or extra:
        detail = []
        if missing:
            detail.append("faltan " + ", ".join(missing))
        if extra:
            detail.append("sobran " + ", ".join(extra))
        raise ValueError("Los ids analizados no coinciden con la evidencia: " + "; ".join(detail) + ".")

    return {
        "schema_version": schema_version.strip(),
        "executive_summary": executive_summary.strip(),
        "analyses": cleaned,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida el análisis del agente contra summary.json.")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        cleaned = sanitize(args.analysis.read_text(encoding="utf-8"), evidence)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(cleaned, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
