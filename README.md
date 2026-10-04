# Análisis de vulnerabilidades

Este repositorio reúne la extracción de evidencia y su análisis reproducible.

| Carpeta | Contenido |
| --- | --- |
| [miner](miner/README.md) | CLI de clonación, CodeQL, Syft, Grype e integración del dataset. |
| [analyzer](analyzer/README.md) | Notebook con diez preguntas de investigación. |
| [miner/organizations](miner/organizations/README.md) | Resultados conservados de las ejecuciones de Django y Pallets. |
| [analyzer/data](analyzer/data) | Copias de evidencia utilizadas por el notebook, con archivos de procedencia. |

## Ejecutar Miner

Desde `miner/`, instala las dependencias con `uv sync` y configura `.env` a
partir de `.env.example`. Consulta su README para instalar CodeQL, Syft y Grype
y ejecutar los comandos de extracción.

## Reproducir el análisis

Desde `analyzer/`, ejecuta `uv sync` y abre
[`notebooks/analyzer.ipynb`](analyzer/notebooks/analyzer.ipynb) con el kernel
de su entorno `.venv`. El notebook usa por defecto la evidencia de Django.
Para ejecutar todas sus celdas sin abrir Jupyter:

```powershell
uv run --project analyzer python analyzer/scripts/validate_notebook.py
```

Se publican datasets, reportes consolidados, inventarios CycloneDX, resultados
originales de Grype y archivos SARIF disponibles. Los repositorios de terceros
clonados, las bases de datos temporales de CodeQL, entornos, cachés y credenciales
permanecen fuera de Git. Los reportes originales conservan sus rutas de origen;
el notebook resuelve la evidencia dentro de la copia del repositorio.

La pregunta sobre seguridad de CI informa falta de cobertura de Actions en la
ejecución disponible. La ausencia de análisis no significa ausencia de problemas.
