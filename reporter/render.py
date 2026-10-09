"""Renderiza el reporte de seguridad a partir de la evidencia y el análisis."""

import argparse
import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def _location(finding: dict) -> str:
    location = finding.get("location") or {}
    file = location.get("file") or ""
    start_line = location.get("start_line")
    if start_line:
        return f"{file}:{start_line}"
    return file


def _prepare(evidence: dict, analysis: dict) -> tuple[list[dict], list[dict]]:
    by_id = {}
    for item in analysis["analyses"]:
        for finding_id in item["ids"]:
            by_id[finding_id] = item

    analyzed = []
    deferred = []
    for group in evidence["groups"]:
        ids = [finding["id"] for finding in group["findings"]]
        locations = ", ".join(_location(finding) for finding in group["findings"])
        view = {
            **group,
            "ids": ", ".join(ids),
            "locations": locations,
        }
        if group["analyze"]:
            view["analysis"] = by_id[ids[0]]
            analyzed.append(view)
        else:
            deferred.append(view)
    return analyzed, deferred


def render(evidence: dict, analysis: dict) -> str:
    analyzed, deferred = _prepare(evidence, analysis)
    environment = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    template = environment.get_template("security-report.md.j2")
    return template.render(
        evidence=evidence,
        analysis=analysis,
        analyzed=analyzed,
        deferred=deferred,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Renderiza el reporte de seguridad.")
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    report = render(evidence, analysis)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")


if __name__ == "__main__":
    main()
