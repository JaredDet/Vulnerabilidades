# Analyzer

Abre esta carpeta en VS Code con las extensiones Python y Jupyter.
Ejecuta `uv sync` y selecciona `.venv` como kernel del notebook
`notebooks/analyzer.ipynb`.

El notebook carga un `dataset.json` del Miner, comprueba su estructura y prepara
tablas de repositorios, hallazgos y puntajes. Cambia `DATASET_PATH` para seleccionar
la ejecución. Usa rutas relativas y conserva separadas las escalas de puntajes.

El notebook desarrolla seis preguntas de investigación. Las preguntas 1 y 2
mantienen su interpretación pendiente; las preguntas 3 a 6 incluyen resúmenes
calculados a partir de la evidencia seleccionada.

## Evidencia de entrada

El notebook usa `data/django/clone-x269596i/dataset.json`. La carpeta
`data/django/clone-x269596i/` es una copia completa de la ejecución del Miner,
incluidos los repositorios, resultados de CodeQL, SBOM y resultados de Grype.
`data/django/provenance.json` registra el origen, la fecha de copia, el SHA-256
del dataset y la verificación de rutas y tamaños de los archivos copiados.

Git conserva `dataset.json`, `clones.json` y `provenance.json`. La copia completa
de repositorios y artefactos se mantiene localmente y está excluida de Git;
las preguntas 1 a 6 solo necesitan el dataset versionado.

La copia anterior de Pallets sigue en `data/pallets/dataset.json`, con su propio
`provenance.json`. Conserva estas entradas sin modificar; para estudiar otra
ejecución, guarda una copia independiente y cambia `DATASET_PATH`.
Las rutas originales dentro de los reportes se conservan como evidencia; el
notebook carga el dataset desde la copia local.

## Concentración por archivo

La pregunta 6 muestra los tres archivos con más hallazgos de CodeQL por
repositorio, sus reglas distintas y la proporción de hallazgos que reúnen.
Cada hallazgo cuenta una vez por archivo; la concentración conjunta del top 3
usa hallazgos únicos para evitar duplicarlos entre ubicaciones. Se informa
la cobertura de ubicación y el estado del análisis, incluidos los fallos.

## Puntajes de seguridad

El notebook documenta el uso directo de security-severity de las reglas CodeQL
y de los puntajes base CVSS publicados en los resultados de Grype. No convierte
etiquetas cualitativas en números. Los puntajes ausentes no se imputan como cero;
las escalas se mantienen separadas y múltiples puntajes no multiplican hallazgos.
