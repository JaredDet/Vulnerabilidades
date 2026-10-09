#!/usr/bin/env bash
# Points visualizer/public/analysis.json at the Analyzer export.
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
relative="$(realpath --relative-to="$(dirname "$link")" "$absolute")"
ln -sfn "$relative" "$link"
echo "Visualizer: visualizer/public/analysis.json -> $relative"
