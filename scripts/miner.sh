#!/usr/bin/env bash
# Runs a Miner command from the repository root.
# An empty GITHUB_TOKEN, injected when the host has none, is removed so
# miner/.env can supply the credential.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  unset GITHUB_TOKEN
fi

exec uv run --directory miner miner "$@"
