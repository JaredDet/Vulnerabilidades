#!/usr/bin/env bash
# Copies the selected Analyzer export to the Visualizer's public data path.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
latest="$root/.pipeline/latest"
default="analyzer/outputs/django/clone-x269596i/analysis.json"

if [[ -f "$latest" ]]; then
  target="$(tr -d '\r' < "$latest")"
else
  target="$default"
fi

if [[ "$target" = /* ]]; then
  absolute="$target"
else
  absolute="$root/$target"
fi

if [[ ! -f "$absolute" ]]; then
  echo "No se encontró $target" >&2
  exit 1
fi

link="$root/visualizer/public/analysis.json"
cp "$absolute" "$link"
echo "Visualizer: copied $target to visualizer/public/analysis.json"
