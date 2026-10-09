# Análisis de vulnerabilidades

[**Miner**](miner/README.md) recopila evidencia con CodeQL, Syft y Grype.
[**Analyzer**](analyzer/README.md) estudia patrones de seguridad y genera
resultados estructurados para el Visualizer.
El [**Visualizer**](visualizer/README.md) muestra esa salida.
El **Reporter** revisa este repositorio y no forma parte de esa cadena.

## Entorno reproducible

Hace falta Docker y un cliente de Dev Containers, en VS Code o Cursor.
La imagen es `linux/amd64`. La primera construcción descarga el bundle de CodeQL.

Abre el repositorio en el contenedor. El script de creación instala las
dependencias de los cuatro componentes y registra el kernel `analyzer`.
No ejecuta el pipeline.

`GITHUB_TOKEN` se toma del entorno del host al abrir el contenedor.
También puedes copiar `miner/.env.example` a `miner/.env` y definir ahí el
token. Los objetivos `make` descartan un token vacío para que ese archivo
pueda usarse. El token no se guarda en Git. Analyzer y Visualizer, sobre
evidencia ya generada, no lo necesitan.

`OPENAI_API_KEY` y `CODEX_API_KEY` son secrets del repositorio en GitHub
Actions. El modelo del Reporter los usa allí. No van en el contenedor ni en Git.

## Pipeline

Desde la raíz del contenedor:

```bash
make pipeline ORG=django
```

Eso ejecuta, en orden, el Miner, el Analyzer y la publicación al Visualizer.
El Miner escribe `dataset.json` y los SBOM en
`miner/organizations/<organización>/work/`. El Analyzer lee esa ejecución y
escribe `analyzer/outputs/<organización>/<clone-run>/analysis.json`.
`make publish` deja `visualizer/public/analysis.json` apuntando a ese archivo.

Sin una salida del Miner, `make analyze` usa la evidencia versionada de Django.

Una etapa del Miner:

```bash
make clone ORG=django
make codeql ORG=django
make sbom ORG=django
make grype ORG=django
make dataset ORG=django
```

El CLI del Miner pide la etapa anterior si falta su entrada.
`make miner` recorre las cinco.

Para abrir el tablero:

```bash
make serve
```

Queda en `http://localhost:4200`. Recarga la página después de `make publish`.

## Reporter

La recolección local usa las herramientas del contenedor:

```bash
reporter/.venv/bin/python reporter/collect.py --repo . --output /tmp/summary.json
```

La interpretación de esa evidencia la hace el workflow de Actions con el
modelo. Con el JSON resultante:

```bash
reporter/.venv/bin/python reporter/validate_analysis.py \
  --evidence /tmp/summary.json \
  --analysis /tmp/analysis-raw.txt \
  --output /tmp/analysis.json
reporter/.venv/bin/python reporter/render.py \
  --evidence /tmp/summary.json \
  --analysis /tmp/analysis.json \
  --output reporter/reports/security-report.md
```

- [Notebook con las preguntas de investigación](analyzer/notebooks/analyzer.ipynb)
- [Salida para el Visualizer](analyzer/outputs/django/clone-x269596i/analysis.json)
- [Resultados originales de Django y Pallets](miner/organizations/README.md)

Se conservan los reportes y su procedencia. Credenciales, entornos locales,
clones de terceros y bases temporales de CodeQL quedan fuera de Git.
