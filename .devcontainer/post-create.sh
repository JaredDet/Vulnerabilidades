#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

uv sync --locked --directory miner
uv sync --locked --directory analyzer
uv run --directory analyzer python -m ipykernel install --user --name analyzer --display-name "analyzer"
npm ci --prefix visualizer
uv venv reporter/.venv
uv pip install --python reporter/.venv/bin/python --requirement reporter/requirements.txt
