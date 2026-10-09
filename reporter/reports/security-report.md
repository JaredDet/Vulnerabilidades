# Reporte de seguridad

- Repositorio: JaredDet/Vulnerabilidades
- Commit: 55bed92028fd9d5372a0af7371484e9091a7f40b
- Fecha: 2026-10-09T13:52:38Z

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

La auditoría identifica los grupos workflow-permissions-write (medio), token-passed-to-process (medio), GHSA-8988-9cw3-xx77 (alto), GHSA-gh4c-6fx4-qh6g (medio), GHSA-vxq7-64xx-v4gw (alto), secret-env-read (bajo), remote-archive-extracted (medio) y action-not-pinned-by-sha (medio). Los hallazgos abarcan permisos del workflow, exposición del token a procesos, tres vulnerabilidades de urllib3, lectura de secretos del entorno, extracción de archivos remotos y acciones fijadas por tag.

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
**Relevancia:** El workflow .github/workflows/security-audit.md concede contents: write, por lo que el token del workflow puede modificar contenido del repositorio y un compromiso del job tendría un impacto elevado.

**Mitigación:** Aplicar el principio de mínimo privilegio: eliminar contents: write y declarar contents: read, concediendo escritura únicamente en un job separado si es estrictamente necesaria y limitando su alcance.
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
**Relevancia:** miner/src/miner/codeql/codeql.py pasa el token al entorno de un proceso hijo y scripts/miner.sh interactúa con GITHUB_TOKEN; cualquier herramienta ejecutada en esos contextos puede acceder al secreto.

**Mitigación:** Evitar propagar el token mediante el entorno de procesos hijos; pasar credenciales solo a la operación que las necesita, restringir el entorno heredado y usar tokens con permisos y duración mínimos.
### F004 — GHSA-8988-9cw3-xx77 (High)

urllib3: HTTPS proxy TLS configuration may be ignored or overridden

**Evidencia:** `miner/uv.lock`, identificador `F004`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner depende de urllib3 2.7.0 en miner/uv.lock, afectado por una configuración TLS de proxy HTTPS que puede ignorarse o sobrescribirse, debilitando las garantías de conexión cuando se usa un proxy.

**Mitigación:** Actualizar urllib3 a una versión que corrija GHSA-8988-9cw3-xx77 y regenerar miner/uv.lock; revisar además que la configuración TLS del proxy se valide explícitamente.
### F005 — GHSA-gh4c-6fx4-qh6g (Medium)

urllib3: Chunked Deflate streaming can enter an infinite loop

**Evidencia:** `miner/uv.lock`, identificador `F005`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner depende de urllib3 2.7.0 en miner/uv.lock, cuya gestión de streaming Chunked Deflate puede entrar en un bucle infinito y provocar una denegación de servicio.

**Mitigación:** Actualizar urllib3 a una versión corregida y regenerar miner/uv.lock; mantener límites de tiempo y de recursos para respuestas HTTP.
### F006 — GHSA-vxq7-64xx-v4gw (High)

urllib3: HTTPResponse.stream()/read_chunked() buffers an unbounded chunk-size line into memory

**Evidencia:** `miner/uv.lock`, identificador `F006`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner depende de urllib3 2.7.0 en miner/uv.lock, y HTTPResponse.stream()/read_chunked() puede almacenar en memoria una línea de tamaño de chunk sin límite, con riesgo de agotamiento de recursos.

**Mitigación:** Actualizar urllib3 a una versión corregida y regenerar miner/uv.lock; aplicar límites de tamaño y controles de consumo al procesar respuestas fragmentadas.
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
**Relevancia:** Los Dockerfile de .devcontainer y miner descargan archivos remotos y los extraen directamente con tar, de modo que la integridad y el contenido del archivo controlan lo que se incorpora a la imagen.

**Mitigación:** Verificar hashes o firmas de cada archivo descargado antes de extraerlo, fijar las fuentes a versiones inmutables y extraer con rutas y permisos restringidos.
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
**Relevancia:** Los workflows usan actions/checkout@v4, astral-sh/setup-uv@v6, actions/setup-python@v5, actions/upload-artifact@v4 y actions/download-artifact@v4 fijadas por tag; un cambio posterior del tag podría alterar la ejecución del pipeline.

**Mitigación:** Reemplazar cada referencia por el SHA completo del commit de la versión aprobada y mantener un proceso controlado para actualizar esos SHAs.

## Otros hallazgos

| Identificador | Severidad | Ids | Ubicaciones |
|---|---|---|---|
| secret-env-read | low | F007 | miner/src/miner/cli.py:73 |
