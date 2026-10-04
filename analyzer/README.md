# Analyzer

Abre esta carpeta en VS Code con las extensiones Python y Jupyter.
Ejecuta `uv sync` y selecciona `.venv` como kernel del notebook
`notebooks/analyzer.ipynb`.

El notebook carga un `dataset.json` del Miner, comprueba su estructura y prepara
tablas de repositorios, hallazgos y puntajes. Cambia `DATASET_PATH` para seleccionar
la ejecución. Usa rutas relativas y conserva separadas las escalas de puntajes.

El notebook desarrolla diez preguntas de investigación, con método, resultados,
interpretación calculada y limitaciones. La pregunta 10 informa que la ejecución
actual no contiene análisis explícito de Actions; no interpreta esa falta de
cobertura como ausencia de problemas de CI.

## Evidencia de entrada

El notebook usa `data/django/clone-x269596i/dataset.json`. La carpeta
`data/django/clone-x269596i/` es una copia completa de la ejecución del Miner,
incluidos los repositorios, resultados de CodeQL, SBOM y resultados de Grype.
`data/django/provenance.json` registra el origen, la fecha de copia, el SHA-256
del dataset y la verificación de rutas y tamaños de los archivos copiados.

La evidencia para versionar incluye `dataset.json`, `clones.json`,
`provenance.json` y los SBOM de `sboms/sbom-j7jbqezb/`, con sus hashes en
`data/django/sbom-provenance.json`. También se versiona el reporte consolidado
`analysis_results/codeql-b4nijni0/codeql-results.json`, con su hash en
`data/django/codeql-provenance.json`, para comprobar la cobertura por lenguaje.
Los repositorios clonados y los demás artefactos de CodeQL y Grype se mantienen
localmente y están excluidos de Git. Las preguntas 1 a 6 necesitan el dataset;
las preguntas 7 a 9 cargan además los SBOM y la 10 carga el reporte de CodeQL.

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

## Ecosistemas del inventario

La pregunta 7 carga los documentos CycloneDX de la ejecución seleccionada
en `SBOM_REPORT_PATH`. Cuenta registros de componentes y clasifica el ecosistema
por `syft:package:type`, con el tipo de PURL como alternativa. Muestra cantidades
y proporciones globales y por repositorio, conservando por separado los
inventarios vacíos, fallidos, ausentes o inválidos. Utiliza el inventario completo,
incluidos los componentes sin coincidencias de Grype.

## Proporción de componentes con coincidencias

La pregunta 8 cruza SBOM y Grype por repositorio, ecosistema, nombre y versión.
Cada registro de componente cuenta una vez en el numerador, aunque tenga varios
identificadores asociados. Presenta tamaño del inventario, componentes afectados,
identidades distintas y proporciones, junto con la cobertura y los registros sin
correspondencia. Las proporciones quedan sin definir para inventarios vacíos,
análisis incompletos o correspondencias insuficientes.

## Componentes compartidos y seguridad de CI

La pregunta 9 compara paquetes y versiones entre repositorios usando el
inventario completo. Separa compartir un paquete de compartir su versión textual
y conserva los componentes sin coincidencias de Grype.

La pregunta 10 comprueba los resultados por lenguaje del reporte CodeQL.
Solo un resultado explícito de `actions` acredita análisis de ese lenguaje.
Muestra cobertura, reglas, niveles SARIF y ubicaciones cuando están disponibles;
los análisis de otros lenguajes no se utilizan como sustituto.

Las preguntas 1 y 2 interpretan automáticamente la concentración y repetición
observadas. La 2 incluye rankings globales y por repositorio; la 3 presenta
distribuciones completas de severidades y puntajes separados por escala y versión;
la 4 incluye rankings de todos los paquetes e identificadores de Grype, también
los que aparecen en un único repositorio.

## Puntajes de seguridad

El notebook documenta el uso directo de security-severity de las reglas CodeQL
y de los puntajes base CVSS publicados en los resultados de Grype. No convierte
etiquetas cualitativas en números. Los puntajes ausentes no se imputan como cero;
las escalas se mantienen separadas y múltiples puntajes no multiplican hallazgos.
