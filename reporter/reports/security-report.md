# Reporte de seguridad

- Repositorio: JaredDet/Vulnerabilidades
- Commit: e740d87876c7171fc149031f4913b19a10771c5d
- Fecha: 2026-10-09T16:14:37Z

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

La auditoría identifica ocho grupos: workflow-permissions-write (medio), token-passed-to-process (medio), GHSA-8988-9cw3-xx77 (alto), GHSA-gh4c-6fx4-qh6g (medio), GHSA-vxq7-64xx-v4gw (alto), secret-env-read (bajo), remote-archive-extracted (medio) y action-not-pinned-by-sha (medio). Se analizan los siete grupos marcados para análisis; secret-env-read queda documentado pero no se analiza.

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
**Relevancia:** En .github/workflows/security-audit.md, el workflow concede contents: write. Ese permiso permite que el token de GitHub modifique contenido del repositorio desde el contexto de ejecución.

**Mitigación:** Aplicar el principio de mínimo privilegio: retirar contents: write y usar contents: read, concediendo escritura únicamente a un job o paso estrictamente necesario y con alcance mínimo.
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
**Relevancia:** En miner/src/miner/codeql/codeql.py el token se incorpora al entorno de un proceso hijo; scripts/miner.sh también inspecciona GITHUB_TOKEN. Esto amplía la superficie de exposición del secreto a procesos descendientes y comandos que hereden el entorno.

**Mitigación:** Evitar pasar el token mediante el entorno de procesos hijos; usar un mecanismo de credenciales con alcance y duración mínimos, limitar la herencia del entorno y eliminar el token inmediatamente después de la operación que lo requiere.
### F004 — GHSA-8988-9cw3-xx77 (High)

urllib3: HTTPS proxy TLS configuration may be ignored or overridden

**Evidencia:** `miner/uv.lock`, identificador `F004`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner depende de urllib3 2.7.0 en miner/uv.lock y la alerta describe que la configuración TLS de un proxy HTTPS puede ignorarse o sobrescribirse. Las conexiones que atraviesen un proxy pueden quedar con garantías TLS distintas de las esperadas.

**Mitigación:** Actualizar urllib3 a una versión corregida y regenerar miner/uv.lock; revisar además la configuración de proxies HTTPS y probar que la verificación TLS efectiva coincide con la política del proyecto.
### F005 — GHSA-gh4c-6fx4-qh6g (Medium)

urllib3: Chunked Deflate streaming can enter an infinite loop

**Evidencia:** `miner/uv.lock`, identificador `F005`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner fija urllib3 2.7.0 en miner/uv.lock, versión afectada por un posible bucle infinito al procesar streaming Chunked Deflate. Una respuesta remota especialmente diseñada puede provocar consumo prolongado de recursos y afectar la disponibilidad.

**Mitigación:** Actualizar urllib3 a una versión corregida y regenerar miner/uv.lock; establecer límites de tiempo, tamaño y duración para respuestas HTTP antes de procesar contenido comprimido.
### F006 — GHSA-vxq7-64xx-v4gw (High)

urllib3: HTTPResponse.stream()/read_chunked() buffers an unbounded chunk-size line into memory

**Evidencia:** `miner/uv.lock`, identificador `F006`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner fija urllib3 2.7.0 en miner/uv.lock, versión afectada por el almacenamiento sin límite de la línea de tamaño de chunks en HTTPResponse.stream()/read_chunked(). Una respuesta remota puede provocar consumo excesivo de memoria.

**Mitigación:** Actualizar urllib3 a una versión corregida y regenerar miner/uv.lock; imponer límites de tamaño a respuestas y streams y rechazar entradas que excedan esos límites.
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
**Relevancia:** Los Dockerfiles .devcontainer/Dockerfile y miner/Dockerfile descargan archivos remotos con curl y los extraen directamente con tar. Si el recurso remoto o su integridad se ve comprometido, la construcción puede incorporar contenido no confiable.

**Mitigación:** Fijar versiones inmutables, verificar hashes o firmas antes de extraer, descargar a un archivo temporal y validar su contenido y rutas antes de instalarlo.
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
**Relevancia:** Los workflows usan actions/checkout, astral-sh/setup-uv, actions/setup-python, actions/upload-artifact y actions/download-artifact fijadas por tags, no por SHA. Un cambio posterior del tag podría alterar el código ejecutado en CI.

**Mitigación:** Reemplazar cada referencia por el SHA completo de un commit revisado, conservar el nombre y la versión como comentario para facilitar mantenimiento, y actualizar los SHA mediante un proceso controlado.

## Otros hallazgos

| Identificador | Severidad | Ids | Ubicaciones |
|---|---|---|---|
| secret-env-read | low | F007 | miner/src/miner/cli.py:73 |
