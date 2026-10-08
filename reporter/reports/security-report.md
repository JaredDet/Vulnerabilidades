# Reporte de seguridad

- Repositorio: JaredDet/Vulnerabilidades
- Commit: 6acb1a64d580b11447b1779f02dea6ca5ff51c6f
- Fecha: 2026-10-08T05:56:48Z

## Cobertura

| Herramienta | Versión | Estado |
|---|---|---|
| codeql | 2.27.0 | analyzed |
| grype | 0.119.0 | analyzed; workflows sin SBOM que analizar |
| config-inventory | 1 | analyzed |

## Hallazgos

### F003 — GHSA-8988-9cw3-xx77 (High)

urllib3: HTTPS proxy TLS configuration may be ignored or overridden

**Evidencia:** `miner/uv.lock`, identificador `F003`.

**Evidencia de Grype:** paquete `urllib3`, versión `2.7.0`, en `miner/uv.lock`.

**Relevancia:** En el componente miner, una configuración TLS de proxy HTTPS ignorada o sobrescrita puede debilitar la validación de conexiones.

**Mitigación:** Actualizar urllib3 a una versión corregida y verificar explícitamente la configuración TLS de los proxies HTTPS.

### F005 — GHSA-vxq7-64xx-v4gw (High)

urllib3: HTTPResponse.stream()/read_chunked() buffers an unbounded chunk-size line into memory

**Evidencia:** `miner/uv.lock`, identificador `F005`.

**Evidencia de Grype:** paquete `urllib3`, versión `2.7.0`, en `miner/uv.lock`.

**Relevancia:** En el componente miner, una línea de tamaño de chunk sin límite puede provocar consumo excesivo de memoria al procesar respuestas HTTP.

**Mitigación:** Actualizar urllib3 a una versión corregida y aplicar límites de tamaño y tiempo a las respuestas HTTP.

### F001 — workflow-permissions-write (medium)

El workflow concede un permiso de escritura: contents: write

**Evidencia:** `.github/workflows/security-audit.md:66`, identificador `F001`.

```64:68:.github/workflows/security-audit.md
      runs-on: ubuntu-latest
      permissions:
        contents: write
      output: Reporte validado y subido a una rama nueva.
      inputs:
```

**Relevancia:** En workflows, `contents: write` amplía la capacidad del token para modificar el repositorio si el job o una acción es comprometida.

**Mitigación:** Cambiar a permisos mínimos, por ejemplo `contents: read`, y conceder escritura solo en un job estrictamente necesario y aislado.

### F002 — token-passed-to-process (medium)

El token se pasa al entorno de un proceso hijo.

**Evidencia:** `miner/src/miner/codeql/codeql.py:49`, identificador `F002`.

```47:51:miner/src/miner/codeql/codeql.py
        environment = {
            **os.environ,
            GITHUB_TOKEN_ENVIRONMENT_VARIABLE: token,
        }

```

**Relevancia:** En el componente miner, los procesos hijos heredan el token y cualquier herramienta ejecutada puede leerlo.

**Mitigación:** Evitar pasar el token por el entorno completo; proporcionar credenciales solo a la operación que las necesita y limpiar el entorno del proceso hijo.

### F004 — GHSA-gh4c-6fx4-qh6g (Medium)

urllib3: Chunked Deflate streaming can enter an infinite loop

**Evidencia:** `miner/uv.lock`, identificador `F004`.

**Evidencia de Grype:** paquete `urllib3`, versión `2.7.0`, en `miner/uv.lock`.

**Relevancia:** En el componente miner, una respuesta comprimida especialmente construida puede dejar el streaming en un bucle infinito y agotar recursos.

**Mitigación:** Actualizar urllib3 a una versión corregida y establecer límites de tiempo y recursos para el streaming.
### F007, F008, F009, F010, F011, F012, F013, F014, F015, F016, F017, F018 — action-not-pinned-by-sha (medium)

La action está fijada por tag, no por SHA.

**Evidencia:** `.github/workflows/ci.yml:19`, paquete `actions/checkout`, versión `v4`, identificador `F007`.

```17:21:.github/workflows/ci.yml
        working-directory: miner
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
```

**Evidencia:** `.github/workflows/ci.yml:20`, paquete `astral-sh/setup-uv`, versión `v6`, identificador `F008`.

```18:22:.github/workflows/ci.yml
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
```

**Evidencia:** `.github/workflows/ci.yml:23`, paquete `actions/setup-python`, versión `v5`, identificador `F009`.

```21:25:.github/workflows/ci.yml
        with:
          enable-cache: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
```

**Evidencia:** `.github/workflows/ci.yml:33`, paquete `actions/checkout`, versión `v4`, identificador `F010`.

```31:35:.github/workflows/ci.yml
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
```

**Evidencia:** `.github/workflows/ci.yml:34`, paquete `astral-sh/setup-uv`, versión `v6`, identificador `F011`.

```32:36:.github/workflows/ci.yml
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
        with:
          enable-cache: true
```

**Evidencia:** `.github/workflows/ci.yml:37`, paquete `actions/setup-python`, versión `v5`, identificador `F012`.

```35:39:.github/workflows/ci.yml
        with:
          enable-cache: true
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
```

**Evidencia:** `.github/workflows/ci.yml:43`, paquete `actions/upload-artifact`, versión `v4`, identificador `F013`.

```41:45:.github/workflows/ci.yml
      - run: uv run --project analyzer python analyzer/scripts/validate_notebook.py
      - run: uv run --project analyzer python -m unittest discover -s analyzer/tests
      - uses: actions/upload-artifact@v4
        with:
          name: analyzer-results
```

**Evidencia:** `.github/workflows/ci.yml:53`, paquete `actions/checkout`, versión `v4`, identificador `F014`.

```51:55:.github/workflows/ci.yml
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Create artifact directories
```

**Evidencia:** `.github/workflows/ci.yml:98`, paquete `actions/upload-artifact`, versión `v4`, identificador `F015`.

```96:100:.github/workflows/ci.yml
      - name: Upload scanner reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: security-reports
```

**Evidencia:** `.github/workflows/security-audit.md:42`, paquete `actions/upload-artifact`, versión `v4`, identificador `F016`.

```40:44:.github/workflows/security-audit.md
        python reporter/collect.py --repo /repo --output /evidence/summary.json
  - name: Upload evidence
    uses: actions/upload-artifact@v4
    with:
      name: reporter-evidence
```

**Evidencia:** `.github/workflows/security-audit.md:75`, paquete `actions/checkout`, versión `v4`, identificador `F017`.

```73:77:.github/workflows/security-audit.md
      steps:
        - name: Checkout
          uses: actions/checkout@v4
        - name: Download evidence
          uses: actions/download-artifact@v4
```

**Evidencia:** `.github/workflows/security-audit.md:77`, paquete `actions/download-artifact`, versión `v4`, identificador `F018`.

```75:79:.github/workflows/security-audit.md
          uses: actions/checkout@v4
        - name: Download evidence
          uses: actions/download-artifact@v4
          with:
            name: reporter-evidence
```

**Relevancia:** En workflows, los tags mutables permiten que una actualización no fijada de una action introduzca cambios no revisados en el pipeline.

**Mitigación:** Fijar cada action a un commit SHA completo y actualizar esos SHAs mediante revisiones controladas.

### F019 — remote-archive-extracted (medium)

Un RUN descarga un archivo remoto y lo extrae con tar.

**Evidencia:** `miner/Dockerfile:17`, identificador `F019`.

```17:24:miner/Dockerfile
RUN mkdir -p /opt/codeql \
    && curl -fsSL \
        "https://github.com/github/codeql-action/releases/download/codeql-bundle-v${CODEQL_VERSION}/codeql-bundle-linux64.tar.gz" \
        | tar -xz -C /opt/codeql --strip-components=1 \
    && curl -fsSL \
        "https://github.com/anchore/syft/releases/download/v${SYFT_VERSION}/syft_${SYFT_VERSION}_linux_amd64.tar.gz" \
        | tar -xz -C /usr/local/bin syft \
    && curl -fsSL \
```

**Relevancia:** En el componente miner, extraer archivos remotos durante la construcción amplía la cadena de suministro y depende de la integridad de las descargas.

**Mitigación:** Verificar hashes o firmas de cada archivo antes de extraerlo y fijar versiones y fuentes de descarga reproducibles.

## Otros hallazgos

| Id | Identificador | Severidad | Ubicación |
|---|---|---|---|
| F006 | secret-env-read | low | miner/src/miner/cli.py:73 |

## Sin evidencia suficiente

Ninguno.
