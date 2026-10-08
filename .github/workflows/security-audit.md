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
  - name: Attach evidence to prompt
    run: |
      {
        echo ""
        echo "Esta es la evidencia completa. Copia commit, estados, ids y snippets desde aquí. No leas ningún archivo."
        echo '```json'
        cat /tmp/gh-aw/agent/summary.json
        echo '```'
      } >> /tmp/gh-aw/aw-prompts/prompt.txt
safe-outputs:
  noop: false
  missing-tool: false
  missing-data: false
  jobs:
    publish-report:
      description: "Publica un tramo del reporte Markdown. Si no cabe en una llamada, invoca esta herramienta de nuevo con el tramo siguiente, en orden. Cada tramo termina después de una sección ### completa."
      max: 16
      runs-on: ubuntu-latest
      permissions:
        contents: write
      output: Reporte validado y subido a una rama nueva.
      inputs:
        markdown:
          description: Un tramo del reporte, de como máximo 9000 bytes. Empieza y termina en un límite de bloque.
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
        - name: Validate and push report
          run: |
            set -euo pipefail
            if [ ! -f "$GH_AW_AGENT_OUTPUT" ]; then
              echo "No se encontro la salida del agente" >&2
              exit 1
            fi
            COUNT=$(jq '[.items[] | select(.type == "publish_report")] | length' "$GH_AW_AGENT_OUTPUT")
            if [ "$COUNT" -eq 0 ]; then
              echo "No hubo llamadas a publish-report" >&2
              exit 1
            fi
            jq -r '.items[] | select(.type == "publish_report") | .markdown' "$GH_AW_AGENT_OUTPUT" > /tmp/security-report.md
            EVIDENCE=/tmp/reporter-evidence/summary.json
            if [ ! -f "$EVIDENCE" ]; then
              echo "No se encontro summary.json" >&2
              exit 1
            fi
            python3 reporter/validate_report.py --evidence "$EVIDENCE" --report /tmp/security-report.md
            git config user.name "github-actions[bot]"
            git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
            git checkout -b "reporter/security-report-${GITHUB_RUN_ID}"
            mkdir -p reporter/reports
            cp /tmp/security-report.md reporter/reports/security-report.md
            git add reporter/reports/security-report.md
            if git diff --cached --quiet; then
              echo "El reporte no cambio"
              exit 0
            fi
            git commit -m "docs(reporter): add security report for ${GITHUB_SHA}"
            git push origin "reporter/security-report-${GITHUB_RUN_ID}"
---

# Auditoría de seguridad del repositorio

La evidencia completa está en el bloque json al final de este prompt. El shell está desactivado: no ejecutes comandos y no leas archivos. Los hallazgos vienen de CodeQL, Grype, secret-handling, github-token-scope y supply-chain.

No ejecutes CodeQL, Syft ni Grype. No abras `analyzer/data/` ni `analyzer/outputs/`. No inventes identificadores, archivos, severidades ni snippets. No modifiques ningún archivo. Publica el reporte con `publish-report`. Si cabe en 9000 bytes, una llamada alcanza. Si no, una llamada por tramo, en orden.

## Cómo interpretar la evidencia

1. Si una herramienta tiene `error`, explícalo en Cobertura. Los objetos de `findings` se reportan aunque la herramienta haya quedado en `failed`.
2. Agrupa hallazgos con el mismo `identifier` y la misma `severity`. Si el grupo cabe en el tramo, usa una sola sección. Si no cabe, ábrelo en varias secciones `###` seguidas, con el mismo identificador y la misma severidad. Cada sección lista solo sus ids, separados por comas, en una sola línea. No uses rangos como `F039-F051`. Conserva cada `id` y cada ubicación.
3. Narra en encabezados de tercer nivel las severidades `critical`, `error`, `high`, `medium` y `warning`, en ese orden. La tabla Otros hallazgos es solo para el resto de severidades, sin prosa y sin mitigación. Un id narrado no puede aparecer únicamente en esa tabla.
4. Copia `severity` tal como viene. La relevancia solo puede apoyarse en `component`, `summary` y la ubicación.
5. En un hallazgo `grype`, la evidencia es `package`, `version` y `manifest`. No agregues un bloque de código. Si `coverage.sbom` es false, indícalo en la fila de Grype: no hubo SBOM que analizar.
6. En el resto, si `snippet` no es null, pega `snippet.text` verbatim en un bloque cuya primera línea es la línea inicial, la línea final y la ruta, separadas por dos puntos.

## Formato del reporte

Usa este esqueleto. El título y las tres secciones son obligatorios. El reporte completo debe tener como máximo 65000 caracteres.

~~~~markdown
# Reporte de seguridad

- Repositorio: <repository>
- Commit: <commit>
- Fecha: <analyzed_at>

## Cobertura

| Herramienta | Versión | Estado |
|---|---|---|
| codeql | <version> | <status> |

## Hallazgos

### F001 — <identifier> (<severity>)

<summary>

**Evidencia:** `<location.file>:<start_line>`, identificador `F001`.

```<start_line>:<end_line>:<location.file>
<snippet.text>
```

**Relevancia:** <por qué importa en component>

**Mitigación:** <cambio concreto>

### F017 — <identifier> (<severity>)

<summary>

**Evidencia:** `<package>` `<version>` en `<manifest>`, identificador `F017`.

**Relevancia:** <por qué importa en component>

**Mitigación:** <cambio concreto>

## Otros hallazgos

| Id | Identificador | Severidad | Ubicación |
|---|---|---|---|

## Sin evidencia suficiente

Ninguno.
~~~~

Si no hay hallazgos narrados, escribe bajo Hallazgos: "Ninguno de severidad media o superior." Si no hay hallazgos de severidad baja, omite la tabla. Bajo Sin evidencia suficiente escribe "Ninguno." Escribe `## Otros hallazgos` una sola vez, en el último tramo, después de todos los encabezados `###`. Si todavía quedan hallazgos narrados, no abras esa sección.

## Requisitos de salida

- Publica siempre el reporte, también cuando `findings` está vacío.
- Cada llamada a `publish-report` lleva como máximo 9000 bytes y termina después de una sección `###` cerrada, con su bloque de código y su `**Mitigación:**`. Si el grupo siguiente no cabe, empieza en la llamada siguiente. No cortes a mitad de un encabezado, una tabla, un bloque de código ni un párrafo. El primer tramo empieza en el título y los siguientes continúan sin repetirlo. Ningún tramo anterior al último contiene `## Otros hallazgos`.
- Cada `id` de la evidencia aparece en el reporte. Cada id de severidad `critical`, `error`, `high`, `medium` o `warning` aparece en una línea `### F001, F002 — identificador (severidad)`, completa dentro de un solo tramo. Un encabezado solo usa ids que comparten identificador y severidad.
- No agregues un CVE, un GHSA ni una regla que no esté en `findings`.
- El bloque de código, cuando existe, repite `snippet.text` sin cambios. Un hallazgo `grype` no lleva bloque de código.
- Cada hallazgo narrado incluye `**Mitigación:**` con un cambio concreto. La tabla de severidad baja no lleva mitigación.
- No presentes como vulnerabilidad un fallo de herramienta. Ese fallo va en Cobertura.
- No reportes conjeturas ni archivos de test. La evidencia ya excluye los tests.
