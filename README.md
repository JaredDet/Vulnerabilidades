# Análisis de vulnerabilidades

[**Miner**](miner/README.md) recopila evidencia con CodeQL, Syft y Grype.
[**Analyzer**](analyzer/README.md) estudia patrones de seguridad y genera
resultados estructurados para el Visualizer.

Desde la raíz, para reproducir el análisis de Django y generar su salida:

```powershell
uv sync --project analyzer
uv run --project analyzer python analyzer/scripts/validate_notebook.py
```

- [Notebook con las preguntas de investigación](analyzer/notebooks/analyzer.ipynb)
- [Salida para el Visualizer](analyzer/outputs/django/clone-x269596i/analysis.json)
- [Resultados originales de Django y Pallets](miner/organizations/README.md)

Se conservan los reportes y su procedencia. Credenciales, entornos locales,
clones de terceros y bases temporales de CodeQL quedan fuera de Git.
