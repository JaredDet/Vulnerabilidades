# Miner

Extrae repositorios de GitHub, analiza código con CodeQL y dependencias con
Syft y Grype. Integra la evidencia en `dataset.json` para el Analyzer.

## Ejecutar

Requiere Python 3.11+, uv, Git, CodeQL, Syft y Grype en `PATH`.
Desde `miner/`:

```powershell
uv sync
Copy-Item .env.example .env
```

Configura `GITHUB_TOKEN` en `.env` y ejecuta:

```powershell
uv run miner run --organization django
```

Para consultar comandos y opciones: `uv run miner --help`.
Para ejecutar las pruebas: `uv run pytest -q`.

## Resultados

Cada ejecución se guarda en `organizations/<organización>/work/clone-<id>/`:
`clones.json`, `dataset.json` y carpetas de CodeQL, SBOM y Grype.
Los reportes conservan los fallos por repositorio; revisa su cobertura aunque
el comando termine correctamente. Los hallazgos no son vulnerabilidades confirmadas.

Consulta los [resultados conservados](organizations/README.md) y los
[diagramas de los flujos](docs/README.md).
