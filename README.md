# Analyzer

Abre esta carpeta en VS Code con las extensiones Python y Jupyter.
Ejecuta `uv sync` y selecciona `.venv` como kernel del notebook
`notebooks/analyzer.ipynb`.

El notebook carga un `dataset.json` del Miner, comprueba su estructura y prepara
tablas de repositorios, hallazgos y puntajes. Cambia `DATASET_PATH` para seleccionar
la ejecución. Usa rutas relativas y conserva separadas las escalas de puntajes.

Esta es una base para el estudio, sin conclusiones automáticas. Las secciones de
investigación están pendientes de desarrollar e interpretar.

## Evidencia de entrada

El notebook usa data/pallets/dataset.json como copia fija del dataset del Miner.
El archivo data/pallets/provenance.json registra la ruta de origen, ejecución,
fecha de copia y SHA-256. Conserva esta entrada sin modificar; para estudiar
otra ejecución, guarda una copia independiente y cambia DATASET_PATH.
