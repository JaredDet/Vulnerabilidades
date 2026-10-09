# Reporte de seguridad

- Repositorio: JaredDet/Vulnerabilidades
- Commit: c901148343f963d309233341eac148a8563cd04f
- Fecha: 2026-10-09T13:59:24Z

## Cobertura

| Herramienta | Versión | Estado |
|---|---|---|
| codeql | 2.27.0 | analyzed |
| syft | 1.52.0 | analyzed |
| grype | Application:         grype | analyzed |
| secret-scanner | 1 | analyzed |
| github-token-auditor | 1 | analyzed |
| workflow-analyzer | 1 | analyzed |

## Resumen ejecutivo

La auditoría identifica siete áreas: workflow-permissions-write por el permiso contents: write en workflows; token-passed-to-process por la exposición del token a procesos hijos en miner y repository; GHSA-8988-9cw3-xx77 por la configuración TLS de proxies HTTPS en urllib3; GHSA-gh4c-6fx4-qh6g por un posible bucle infinito al procesar streaming Chunked Deflate en urllib3; GHSA-vxq7-64xx-v4gw por el almacenamiento en memoria sin límite de la línea de tamaño de chunk en urllib3; secret-env-read por la lectura de un secreto desde el entorno en miner; remote-archive-extracted por descargar y extraer archivos remotos con tar en repository y miner; y action-not-pinned-by-sha por acciones fijadas mediante tags en workflows.

## Hallazgos

### F001 — workflow-permissions-write (medium)

El workflow concede un permiso de escritura: contents: write

**Evidencia:** `.github/workflows/security-audit.md:75`, identificador `F001`.
```73:77:.github/workflows/security-audit.md
      runs-on: ubuntu-latest
      permissions:
        contents: write
      output: Reporte renderizado y subido a una rama nueva.
      inputs:
```
**Relevancia:** El workflow en .github/workflows/security-audit.md concede contents: write, por lo que el token de GitHub disponible durante la ejecución puede modificar contenido del repositorio. Esto amplía el impacto potencial de una ejecución comprometida o de un paso vulnerable.

**Mitigación:** Usar el principio de mínimo privilegio: eliminar contents: write si no es imprescindible y limitar el permiso al alcance estrictamente necesario para la publicación.
### F002, F003 — token-passed-to-process (medium)

El token se pasa al entorno de un proceso hijo.

**Evidencia:** `miner/src/miner/codeql/codeql.py:49`, identificador `F002`.
```47:51:miner/src/miner/codeql/codeql.py
        environment = {
            **os.environ,
            GITHUB_TOKEN_ENVIRONMENT_VARIABLE: token,
        }

```
**Evidencia:** `scripts/miner.sh:10`, identificador `F003`.
```8:12:scripts/miner.sh
cd "$root"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  unset GITHUB_TOKEN
fi
```
**Relevancia:** En miner/src/miner/codeql/codeql.py el token se incorpora al entorno de un proceso hijo, y scripts/miner.sh gestiona GITHUB_TOKEN en el entorno. Cualquier proceso hijo o herramienta ejecutada en esos contextos puede acceder al token, aumentando el riesgo de exposición accidental o de uso indebido.

**Mitigación:** Evitar propagar el token mediante el entorno global de procesos hijos; pasarlo solo al paso que lo necesita, reducir su alcance y duración, y limpiar explícitamente el entorno antes de ejecutar herramientas no confiables.
### F004 — GHSA-8988-9cw3-xx77 (High)

urllib3: HTTPS proxy TLS configuration may be ignored or overridden

**Evidencia:** `miner/uv.lock`, identificador `F004`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner usa urllib3 2.7.0, declarado en miner/uv.lock. La configuración TLS de un proxy HTTPS puede ignorarse o sobrescribirse, lo que puede debilitar las garantías esperadas de validación TLS en conexiones que atraviesen proxies.

**Mitigación:** Actualizar urllib3 a una versión corregida compatible con el proyecto y verificar que la configuración de certificados y validación TLS del proxy se aplique explícitamente.
### F005 — GHSA-gh4c-6fx4-qh6g (Medium)

urllib3: Chunked Deflate streaming can enter an infinite loop

**Evidencia:** `miner/uv.lock`, identificador `F005`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner usa urllib3 2.7.0. Una respuesta con Chunked Deflate puede provocar un bucle infinito durante el streaming, afectando la disponibilidad del proceso que consume la respuesta.

**Mitigación:** Actualizar urllib3 a una versión corregida y aplicar límites de tiempo, tamaño y duración a las respuestas streaming.
### F006 — GHSA-vxq7-64xx-v4gw (High)

urllib3: HTTPResponse.stream()/read_chunked() buffers an unbounded chunk-size line into memory

**Evidencia:** `miner/uv.lock`, identificador `F006`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner usa urllib3 2.7.0. HTTPResponse.stream()/read_chunked() puede acumular sin límite la línea que contiene el tamaño del chunk, permitiendo un consumo excesivo de memoria y una posible denegación de servicio.

**Mitigación:** Actualizar urllib3 a una versión corregida y establecer límites de tamaño para respuestas y líneas de chunk antes de procesarlas.
### F008, F021 — remote-archive-extracted (medium)

Un RUN descarga un archivo remoto y lo extrae con tar.

**Evidencia:** `.devcontainer/Dockerfile:19`, identificador `F008`.
```19:26:.devcontainer/Dockerfile
RUN mkdir -p /opt/codeql \
    && curl -fsSL \
        "https://github.com/github/codeql-action/releases/download/codeql-bundle-v${CODEQL_VERSION}/codeql-bundle-linux64.tar.gz" \
        | tar -xz -C /opt/codeql --strip-components=1 \
    && curl -fsSL \
        "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz" \
        | tar -xz -C /usr/local/bin syft \
    && curl -fsSL \
```
**Evidencia:** `miner/Dockerfile:19`, identificador `F021`.
```19:26:miner/Dockerfile
RUN mkdir -p /opt/codeql \
    && curl -fsSL \
        "https://github.com/github/codeql-action/releases/download/codeql-bundle-v${CODEQL_VERSION}/codeql-bundle-linux64.tar.gz" \
        | tar -xz -C /opt/codeql --strip-components=1 \
    && curl -fsSL \
        "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz" \
        | tar -xz -C /usr/local/bin syft \
    && curl -fsSL \
```
**Relevancia:** Los Dockerfiles .devcontainer/Dockerfile y miner/Dockerfile descargan archivos remotos y los extraen directamente con tar. Si el recurso remoto o su transporte se altera, el proceso de construcción puede incorporar contenido no confiable o inesperado.

**Mitigación:** Verificar la integridad de cada archivo descargado mediante hashes o firmas fijados y revisar que la extracción quede confinada al destino esperado.
### F009, F010, F011, F012, F013, F014, F015, F016, F017, F018, F019, F020 — action-not-pinned-by-sha (medium)

La action está fijada por tag, no por SHA.

**Evidencia:** `.github/workflows/ci.yml:19`, identificador `F009`.
Paquete `actions/checkout` versión `v4`.
```17:21:.github/workflows/ci.yml
        working-directory: miner
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
```
**Evidencia:** `.github/workflows/ci.yml:20`, identificador `F010`.
Paquete `astral-sh/setup-uv` versión `v6`.
```18:22:.github/workflows/ci.yml
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
```
**Evidencia:** `.github/workflows/ci.yml:23`, identificador `F011`.
Paquete `actions/setup-python` versión `v5`.
```21:25:.github/workflows/ci.yml
        with:
          enable-cache: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
```
**Evidencia:** `.github/workflows/ci.yml:33`, identificador `F012`.
Paquete `actions/checkout` versión `v4`.
```31:35:.github/workflows/ci.yml
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
```
**Evidencia:** `.github/workflows/ci.yml:34`, identificador `F013`.
Paquete `astral-sh/setup-uv` versión `v6`.
```32:36:.github/workflows/ci.yml
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
```
**Evidencia:** `.github/workflows/ci.yml:37`, identificador `F014`.
Paquete `actions/setup-python` versión `v5`.
```35:39:.github/workflows/ci.yml
        with:
          enable-cache: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
```
**Evidencia:** `.github/workflows/ci.yml:43`, identificador `F015`.
Paquete `actions/upload-artifact` versión `v4`.
```41:45:.github/workflows/ci.yml
      - run: uv run --project analyzer python analyzer/scripts/validate_notebook.py
      - run: uv run --project analyzer python -m unittest discover -s analyzer/tests
      - uses: actions/upload-artifact@v4
        with:
          name: analyzer-results
```
**Evidencia:** `.github/workflows/ci.yml:53`, identificador `F016`.
Paquete `actions/checkout` versión `v4`.
```51:55:.github/workflows/ci.yml
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Create artifact directories
```
**Evidencia:** `.github/workflows/ci.yml:98`, identificador `F017`.
Paquete `actions/upload-artifact` versión `v4`.
```96:100:.github/workflows/ci.yml
      - name: Upload scanner reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
```
**Evidencia:** `.github/workflows/security-audit.md:42`, identificador `F018`.
Paquete `actions/upload-artifact` versión `v4`.
```40:44:.github/workflows/security-audit.md
        python reporter/collect.py --repo /repo --output /evidence/summary.json
  - name: Upload evidence
    uses: actions/upload-artifact@v4
    with:
      name: reporter-evidence
```
**Evidencia:** `.github/workflows/security-audit.md:84`, identificador `F019`.
Paquete `actions/checkout` versión `v4`.
```82:86:.github/workflows/security-audit.md
      steps:
        - name: Checkout
          uses: actions/checkout@v4
        - name: Download evidence
          uses: actions/download-artifact@v4
```
**Evidencia:** `.github/workflows/security-audit.md:86`, identificador `F020`.
Paquete `actions/download-artifact` versión `v4`.
```84:88:.github/workflows/security-audit.md
          uses: actions/checkout@v4
        - name: Download evidence
          uses: actions/download-artifact@v4
          with:
            name: reporter-evidence
```
**Relevancia:** Los workflows usan actions/checkout, astral-sh/setup-uv, actions/setup-python, actions/upload-artifact y actions/download-artifact mediante tags como v4, v5 o v6. Un tag mutable puede apuntar posteriormente a código diferente y ejecutar cambios no revisados en el contexto del workflow.

**Mitigación:** Fijar cada action a un commit SHA completo y actualizarlo mediante revisiones controladas, manteniendo un registro de las versiones pretendidas.

## Otros hallazgos

| Identificador | Severidad | Ids | Ubicaciones |
|---|---|---|---|
| secret-env-read | low | F007 | miner/src/miner/cli.py:73 |
