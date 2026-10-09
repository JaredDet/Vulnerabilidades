---
description: Security audit of this repository
on:
  push:
    branches: [main]
    paths-ignore:
      - "reporter/reports/**"
  workflow_dispatch:
permissions:
  contents: read
engine:
  id: codex
  model: openai/gpt-5.6-luna
  env:
    OPENAI_BASE_URL: https://openrouter.ai/api/v1
    GW_AW_MODEL_AGENT_CODEX: openai/gpt-5.6-luna
    GW_AW_MODEL_DETECTION_CODEX: openai/gpt-5.6-luna
network:
  allowed:
    - defaults
    - openrouter.ai
tools:
  bash: false
  cli-proxy: false
jobs:
  agent:
    timeout-minutes: 90
steps:
  - name: Build analysis image
    run: docker build --tag reporter-tools miner
  - name: Collect evidence
    run: |
      mkdir -p /tmp/gh-aw/agent
      docker run --rm \
        -v "${{ github.workspace }}:/repo" \
        -v /tmp/gh-aw/agent:/evidence \
        -e GITHUB_REPOSITORY \
        -w /repo \
        reporter-tools \
        python reporter/collect.py --repo /repo --output /evidence/summary.json
  - name: Upload evidence
    uses: actions/upload-artifact@v4
    with:
      name: reporter-evidence
      path: /tmp/gh-aw/agent/summary.json
      retention-days: 7
  - name: Add evidence to prompt
    run: |
      set -euo pipefail
      PROMPT=/tmp/gh-aw/aw-prompts/prompt.txt
      EVIDENCE=/tmp/gh-aw/agent/summary.json
      if [ ! -f "$PROMPT" ]; then
        echo "No se encontro el prompt" >&2
        exit 1
      fi
      if [ ! -f "$EVIDENCE" ]; then
        echo "No se encontro summary.json" >&2
        exit 1
      fi
      {
        printf '\n\n## Evidencia\n\n'
        printf '~~~~json\n'
        cat "$EVIDENCE"
        printf '\n~~~~\n'
      } >> "$PROMPT"
safe-outputs:
  noop: false
  missing-tool: false
  missing-data: false
  jobs:
    publish-report:
      description: Recibe el analisis JSON, lo valida, renderiza el reporte y lo sube en una rama nueva.
      runs-on: ubuntu-latest
      permissions:
        contents: write
      output: Reporte renderizado y subido a una rama nueva.
      inputs:
        analysis:
          description: Objeto JSON del analisis, con executive_summary y analyses.
          required: true
          type: string
      steps:
        - name: Checkout
          uses: actions/checkout@v4
        - name: Download evidence
          uses: actions/download-artifact@v4
          with:
            name: reporter-evidence
            path: /tmp/reporter-evidence
        - name: Validate, render, and push report
          run: |
            set -euo pipefail
            if [ ! -f "$GH_AW_AGENT_OUTPUT" ]; then
              echo "No se encontro la salida del agente" >&2
              exit 1
            fi
            COUNT=$(jq '[.items[] | select(.type == "publish_report")] | length' "$GH_AW_AGENT_OUTPUT")
            if [ "$COUNT" -ne 1 ]; then
              echo "Se esperaba una sola llamada a publish-report" >&2
              exit 1
            fi
            jq -r '.items[] | select(.type == "publish_report") | .analysis' "$GH_AW_AGENT_OUTPUT" > /tmp/analysis-raw.txt
            EVIDENCE=/tmp/reporter-evidence/summary.json
            if [ ! -f "$EVIDENCE" ]; then
              echo "No se encontro summary.json" >&2
              exit 1
            fi
            python3 -m pip install --requirement reporter/requirements.txt
            python3 reporter/validate_analysis.py \
              --evidence "$EVIDENCE" \
              --analysis /tmp/analysis-raw.txt \
              --output /tmp/analysis.json
            mkdir -p reporter/reports
            python3 reporter/render.py \
              --evidence "$EVIDENCE" \
              --analysis /tmp/analysis.json \
              --output reporter/reports/security-report.md
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git checkout -b "reporter/security-report-${GITHUB_RUN_ID}"
            git add reporter/reports/security-report.md
            if git diff --cached --quiet; then
              echo "El reporte no cambio"
              exit 0
            fi
            git commit -m "docs(reporter): add security report for ${GITHUB_SHA}"
            git push origin "reporter/security-report-${GITHUB_RUN_ID}"
---

# Auditoría de seguridad del repositorio

La evidencia está al final de este prompt, en la sección Evidencia. No busques archivos ni leas el repositorio. El shell está desactivado: no ejecutes comandos. No ejecutes CodeQL, Syft ni Grype. No inventes identificadores, CVE, archivos, severidades ni ubicaciones que no estén en `groups`.

Invoca el safe output `publish-report` una sola vez. El parámetro `analysis` es el objeto JSON. No escribas Markdown.

## Qué analizar

`executive_summary` menciona el conjunto completo de `groups`, incluidos los que tienen `analyze` en false.

`analyses` incluye solo grupos con `analyze` en true. Cada entrada cita los `id` de un solo grupo, y `identifier` es el de ese grupo. No mezcles ids de grupos distintos. No omitas ningún id de un grupo con `analyze` en true y no cites ids de un grupo con `analyze` en false.

`relevance` y `mitigation` se apoyan en `component`, `summary`, `excerpt` y la ubicación. `fix` es opcional: omítelo o déjalo en null cuando un parche o un comando no aportan. Si lo incluyes, `kind` es `snippet` o `command` y `text` es el cambio propuesto. No reescribas el snippet de la evidencia.

## Forma del análisis

~~~~json
{
  "schema_version": "1.0",
  "executive_summary": "Texto que menciona todos los grupos, también los de severidad baja.",
  "analyses": [
    {
      "ids": ["F005"],
      "identifier": "identificador del grupo",
      "relevance": "Por qué importa en ese componente.",
      "mitigation": "Cambio concreto.",
      "fix": null
    }
  ]
}
~~~~

Si no hay grupos con `analyze` en true, `analyses` es una lista vacía y el resumen igual cubre los grupos restantes. Publica el análisis también cuando `groups` está vacío.
