# Analyzer

Estudia concentraciones, diferencias y relaciones mediante diez preguntas de
investigación. Exporta tablas y observaciones para el Visualizer.

## Ejecutar

Desde la raíz del repositorio:

```powershell
uv sync --project analyzer
uv run --project analyzer python analyzer/scripts/validate_notebook.py
```

También puedes abrir [el notebook](notebooks/analyzer.ipynb), seleccionar
`analyzer/.venv` como kernel y ejecutar todas las celdas en orden.
La configuración selecciona organización, clonación y ejecución SBOM; por
defecto usa la evidencia de Django en `data/django/clone-x269596i/`.

## Salida

La última celda genera
[`outputs/django/clone-x269596i/analysis.json`](outputs/django/clone-x269596i/analysis.json).
Incluye resultados, interpretaciones, cobertura, limitaciones y procedencia.
El [contrato del Visualizer](docs/visualizer-contract.md) describe su estructura.

La pregunta 10 queda sin respuesta de seguridad de CI porque esta ejecución
no contiene análisis de Actions. Los fallos y datos ausentes no equivalen a cero.
