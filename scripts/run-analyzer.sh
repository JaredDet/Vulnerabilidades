#!/usr/bin/env bash
# Runs the Analyzer on the latest Miner dataset for an organization.
# Without that dataset, the notebook keeps its committed Django evidence.
set -euo pipefail

org="${1:-django}"
root="$(cd "$(dirname "$0")/.." && pwd)"
work="$root/miner/organizations/$org/work"
stamp_dir="$root/.pipeline"

if [[ ! "$org" =~ ^[A-Za-z0-9._-]+$ ]] || [[ "$org" == "." ]] || [[ "$org" == ".." ]]; then
  echo "Organización inválida: $org" >&2
  exit 1
fi

mkdir -p "$stamp_dir"

latest_clone=""
latest_mtime=-1
shopt -s nullglob
for dataset in "$work"/clone-*/dataset.json; do
  dir="$(dirname "$dataset")"
  name="$(basename "$dir")"
  mtime="$(stat -c %Y "$dataset")"
  if [[ -z "$latest_clone" ]] || (( mtime > latest_mtime )) || { (( mtime == latest_mtime )) && [[ "$name" > "$(basename "$latest_clone")" ]]; }; then
    latest_mtime="$mtime"
    latest_clone="$dir"
  fi
done

if [[ -n "$latest_clone" ]]; then
  latest_report=""
  latest_report_mtime=-1
  for report in "$latest_clone"/sboms/sbom-*/sbom-results.json; do
    name="$(basename "$(dirname "$report")")"
    mtime="$(stat -c %Y "$report")"
    if [[ -z "$latest_report" ]] || (( mtime > latest_report_mtime )) || { (( mtime == latest_report_mtime )) && [[ "$name" > "$(basename "$(dirname "$latest_report")")" ]]; }; then
      latest_report_mtime="$mtime"
      latest_report="$report"
    fi
  done
  if [[ -z "$latest_report" ]]; then
    echo "La clonación $(basename "$latest_clone") no tiene un reporte SBOM." >&2
    exit 1
  fi
  export ANALYZER_ORGANIZATION="$org"
  export ANALYZER_CLONE_RUN="$(basename "$latest_clone")"
  export ANALYZER_SBOM_RUN="$(basename "$(dirname "$latest_report")")"
  export ANALYZER_EVIDENCE_ROOT="$latest_clone"
  echo "Evidencia del Miner: $ANALYZER_EVIDENCE_ROOT ($ANALYZER_SBOM_RUN)"
else
  unset ANALYZER_ORGANIZATION ANALYZER_CLONE_RUN ANALYZER_SBOM_RUN ANALYZER_EVIDENCE_ROOT || true
  echo "No hay dataset del Miner para $org. Se usa la evidencia versionada de Django."
fi

uv run --project "$root/analyzer" python "$root/analyzer/scripts/validate_notebook.py"

python3 - "$root" <<'PY'
import json
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
evidence = os.environ.get("ANALYZER_EVIDENCE_ROOT", "").strip()
if evidence:
    dataset_path = Path(evidence) / "dataset.json"
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    output = (
        root
        / "analyzer"
        / "outputs"
        / dataset["organization"]
        / dataset["clone_run"]
        / "analysis.json"
    )
else:
    output = root / "analyzer/outputs/django/clone-x269596i/analysis.json"

if not output.is_file():
    raise SystemExit(f"No se generó {output}")

(root / ".pipeline" / "latest").write_text(output.relative_to(root).as_posix() + "\n", encoding="utf-8")
print(f"Salida: {output.relative_to(root).as_posix()}")
PY
