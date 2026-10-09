# Reporte de seguridad

- Repositorio: JaredDet/Vulnerabilidades
- Commit: a59c92b15abfbe2cdd0803d046a63c445425ef76
- Fecha: 2026-10-09T03:04:00Z

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

La auditoría identifica los grupos workflow-permissions-write (medium), token-passed-to-process (medium), GHSA-8988-9cw3-xx77 (High), GHSA-gh4c-6fx4-qh6g (Medium), GHSA-vxq7-64xx-v4gw (High), secret-env-read (low, no analizado), action-not-pinned-by-sha (medium) y remote-archive-extracted (medium). Los riesgos abarcan permisos excesivos y exposición del token en workflows y procesos, tres vulnerabilidades de urllib3 2.7.0 en miner, acciones de GitHub fijadas por tag, y extracción de archivos remotos durante la construcción de la imagen.

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
**Relevancia:** En workflows, contents: write permite que el token de GitHub modifique el contenido del repositorio. Si el workflow o una acción ejecutada dentro de él se compromete, este alcance puede facilitar cambios no autorizados.

**Mitigación:** Aplicar el principio de mínimo privilegio: eliminar contents: write y usar contents: read; conceder escritura únicamente al job y paso que la necesiten, con permisos explícitos y acotados.
### F002 — token-passed-to-process (medium)

El token se pasa al entorno de un proceso hijo.

**Evidencia:** `miner/src/miner/codeql/codeql.py:49`, identificador `F002`.
```47:51:miner/src/miner/codeql/codeql.py
        environment = {
            **os.environ,
            GITHUB_TOKEN_ENVIRONMENT_VARIABLE: token,
        }

```
**Relevancia:** En miner/src/miner/codeql/codeql.py, el token se incorpora al entorno heredado por un proceso hijo. Cualquier herramienta o subproceso ejecutado allí con acceso al entorno podría leer y exponer la credencial.

**Mitigación:** No heredar el entorno completo con el token; pásalo solo al proceso estrictamente necesario mediante un entorno mínimo, evita registrar el entorno y limpia la variable después de usarla.
### F003 — GHSA-8988-9cw3-xx77 (High)

urllib3: HTTPS proxy TLS configuration may be ignored or overridden

**Evidencia:** `miner/uv.lock`, identificador `F003`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner usa urllib3 2.7.0, afectado por una configuración TLS de proxy HTTPS que puede ignorarse o sobrescribirse. Esto puede debilitar las garantías TLS en conexiones que atraviesan un proxy.

**Mitigación:** Actualizar urllib3 a una versión que corrija GHSA-8988-9cw3-xx77 y regenerar miner/uv.lock; validar además que la configuración TLS del proxy se aplique y rechazar configuraciones inseguras.
### F004 — GHSA-gh4c-6fx4-qh6g (Medium)

urllib3: Chunked Deflate streaming can enter an infinite loop

**Evidencia:** `miner/uv.lock`, identificador `F004`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner usa urllib3 2.7.0, cuya lectura de streams Chunked Deflate puede entrar en un bucle infinito. Una respuesta remota puede provocar denegación de servicio y afectar la disponibilidad del proceso.

**Mitigación:** Actualizar urllib3 a una versión corregida y regenerar miner/uv.lock; establecer límites de tiempo, tamaño y duración para respuestas HTTP y cancelar streams que no progresen.
### F005 — GHSA-vxq7-64xx-v4gw (High)

urllib3: HTTPResponse.stream()/read_chunked() buffers an unbounded chunk-size line into memory

**Evidencia:** `miner/uv.lock`, identificador `F005`.
Paquete `urllib3` versión `2.7.0`.
**Relevancia:** miner usa urllib3 2.7.0, que puede acumular sin límite la línea del tamaño de un chunk en HTTPResponse.stream()/read_chunked(). Una respuesta controlada por un atacante puede agotar la memoria.

**Mitigación:** Actualizar urllib3 a una versión corregida y regenerar miner/uv.lock; imponer límites de tamaño y tiempo a las respuestas y evitar aceptar streams sin controles de consumo.
### F007, F008, F009, F010, F011, F012, F013, F014, F015, F016, F017, F018 — action-not-pinned-by-sha (medium)

La action está fijada por tag, no por SHA.

**Evidencia:** `.github/workflows/ci.yml:19`, identificador `F007`.
Paquete `actions/checkout` versión `v4`.
```17:21:.github/workflows/ci.yml
        working-directory: miner
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
```
**Evidencia:** `.github/workflows/ci.yml:20`, identificador `F008`.
Paquete `astral-sh/setup-uv` versión `v6`.
```18:22:.github/workflows/ci.yml
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
```
**Evidencia:** `.github/workflows/ci.yml:23`, identificador `F009`.
Paquete `actions/setup-python` versión `v5`.
```21:25:.github/workflows/ci.yml
        with:
          enable-cache: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
```
**Evidencia:** `.github/workflows/ci.yml:33`, identificador `F010`.
Paquete `actions/checkout` versión `v4`.
```31:35:.github/workflows/ci.yml
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
```
**Evidencia:** `.github/workflows/ci.yml:34`, identificador `F011`.
Paquete `astral-sh/setup-uv` versión `v6`.
```32:36:.github/workflows/ci.yml
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
```
**Evidencia:** `.github/workflows/ci.yml:37`, identificador `F012`.
Paquete `actions/setup-python` versión `v5`.
```35:39:.github/workflows/ci.yml
        with:
          enable-cache: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
```
**Evidencia:** `.github/workflows/ci.yml:43`, identificador `F013`.
Paquete `actions/upload-artifact` versión `v4`.
```41:45:.github/workflows/ci.yml
      - run: uv run --project analyzer python analyzer/scripts/validate_notebook.py
      - run: uv run --project analyzer python -m unittest discover -s analyzer/tests
      - uses: actions/upload-artifact@v4
        with:
          name: analyzer-results
```
**Evidencia:** `.github/workflows/ci.yml:53`, identificador `F014`.
Paquete `actions/checkout` versión `v4`.
```51:55:.github/workflows/ci.yml
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Create artifact directories
```
**Evidencia:** `.github/workflows/ci.yml:98`, identificador `F015`.
Paquete `actions/upload-artifact` versión `v4`.
```96:100:.github/workflows/ci.yml
      - name: Upload scanner reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
```
**Evidencia:** `.github/workflows/security-audit.md:42`, identificador `F016`.
Paquete `actions/upload-artifact` versión `v4`.
```40:44:.github/workflows/security-audit.md
        python reporter/collect.py --repo /repo --output /evidence/summary.json
  - name: Upload evidence
    uses: actions/upload-artifact@v4
    with:
      name: reporter-evidence
```
**Evidencia:** `.github/workflows/security-audit.md:84`, identificador `F017`.
Paquete `actions/checkout` versión `v4`.
```82:86:.github/workflows/security-audit.md
      steps:
        - name: Checkout
          uses: actions/checkout@v4
        - name: Download evidence
          uses: actions/download-artifact@v4
```
**Evidencia:** `.github/workflows/security-audit.md:86`, identificador `F018`.
Paquete `actions/download-artifact` versión `v4`.
```84:88:.github/workflows/security-audit.md
          uses: actions/checkout@v4
        - name: Download evidence
          uses: actions/download-artifact@v4
          with:
            name: reporter-evidence
```
**Relevancia:** Los workflows usan actions/checkout, astral-sh/setup-uv, actions/setup-python, actions/upload-artifact y actions/download-artifact mediante tags. Un tag mutable puede cambiar y ejecutar código distinto al revisado en futuras ejecuciones.

**Mitigación:** Fijar cada referencia de action a un commit SHA completo y mantener un registro controlado de las versiones; revisar y actualizar esos SHA mediante cambios auditables.
### F019 — remote-archive-extracted (medium)

Un RUN descarga un archivo remoto y lo extrae con tar.

**Evidencia:** `miner/Dockerfile:18`, identificador `F019`.
```18:25:miner/Dockerfile
RUN mkdir -p /opt/codeql \
    && curl -fsSL \
        "https://github.com/github/codeql-action/releases/download/codeql-bundle-v${CODEQL_VERSION}/codeql-bundle-linux64.tar.gz" \
        | tar -xz -C /opt/codeql --strip-components=1 \
    && curl -fsSL \
        "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz" \
        | tar -xz -C /usr/local/bin syft \
    && curl -fsSL \
```
**Relevancia:** El Dockerfile de miner descarga varios archivos remotos y los extrae directamente con tar. Si el recurso cambia o se suplanta, el proceso de construcción puede incorporar contenido no confiable.

**Mitigación:** Fijar las descargas a versiones inmutables, verificar hashes o firmas antes de extraer y hacer fallar la construcción si la verificación no coincide; limitar además el contenido y destino de la extracción.

## Otros hallazgos

| Identificador | Severidad | Ids | Ubicaciones |
|---|---|---|---|
| secret-env-read | low | F006 | miner/src/miner/cli.py:73 |
