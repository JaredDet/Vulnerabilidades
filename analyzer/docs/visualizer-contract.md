# Entrada del Visualizer · versión 1.1

Ejecutar todas las celdas de `notebooks/analyzer.ipynb` genera
`outputs/<organización>/<clone-run>/analysis.json`. La exportación reemplaza
atómicamente la salida de esa ejecución y conserva intactas las entradas.
También se genera al ejecutar `scripts/validate_notebook.py`.

## Estructura

| Campo | Contenido |
| --- | --- |
| `schema_version` | Versión del contrato; actualmente `1.1`. |
| `generated_at_utc` | Fecha y hora ISO 8601 de generación. |
| `organization`, `clone_run` | Ejecución estudiada. |
| `summary` | Tamaño de la evidencia y alcance del análisis. |
| `conventions` | Significado de nulos, proporciones y estados. |
| `provenance` | Rutas relativas, hashes de evidencia y código, versiones de Python y librerías. |
| `coverage` | Tablas de cobertura de herramientas y SBOM. |
| `questions` | Nueve objetos con identificadores estables `q01` a `q09`. |

Cada pregunta contiene `title`, `status`, `method_and_definitions_markdown`,
`population_and_denominators`, `limitations_markdown`, `metrics`,
`observations` y `tables`. Las observaciones incluyen texto interpretativo y
referencias `evidence_tables` a las tablas que sustentan la pregunta.

Cada tabla contiene `grain` (qué representa una fila), `columns`, `row_count`,
`metric_definitions` y `rows`. Los registros conservan nombres de columnas
estables, listas de versiones o identificadores y valores nulos.
No se exportan solo los primeros registros mostrados por el notebook: los
rankings globales y detalles completos permanecen disponibles.

Cada pregunta incluye `visualizations`: especificaciones con `id`, `type`,
título, `data_table`, codificaciones (`x`, `y`, `series`, `facet` y `tooltip`,
según corresponda) y, cuando aplica, `value_format`. Los tipos usados son
`bar`, `bar_horizontal`, `bar_stacked`, `bar_horizontal_facets`, `heatmap` y
`scatter`. `data_table` referencia la tabla cuantitativa completa en
`question.tables`; no duplica las filas. Cada observación cualitativa declara
`visualization_ids` para vincular su texto con los gráficos que lo respaldan.
El Visualizer puede mostrar juntos la interpretación Markdown, los gráficos y
las tablas de datos.

## Estados y métricas

- `answered`: respuesta para la población declarada, con sus limitaciones.
- `partial_evidence`: existen resultados con cobertura, identificación o puntuación incompleta.
- `insufficient_evidence`: no hay evidencia suficiente para responder; el Visualizer debe mostrar esa condición.
- `null` significa ausencia o métrica no definida; no se transforma en cero.
- Las proporciones usan escala **0–1**. El denominador está definido en la pregunta y en las métricas.
- `q05.metrics` incluye `rho_spearman`, `sample_size` y `p_value: null`: no se realizó una prueba de significancia.
- Los niveles SARIF, `security-severity` y CVSS se mantienen separados.

## Uso

```javascript
const analysis = await fetch("analysis.json").then(response => response.json());
const question = analysis.questions.find(item => item.id === "q08");
const rows = question.tables.componentes_por_repositorio.rows;
// Usar proporcion_afectada junto a componentes_totales y comparacion_completa.
```

Mostrar las observaciones y limitaciones junto a los gráficos permite interpretar
concentraciones, componentes compartidos y asociaciones sin confundir frecuencia
con riesgo o causalidad. El Visualizer representa los resultados calculados; no
necesita volver a ejecutar CodeQL, Grype ni las métricas del notebook.

El hash `notebook_source_sha256` se calcula sobre tipo y fuente de cada celda,
excluyendo salidas y metadatos de ejecución. Los hashes de evidencia corresponden
a los bytes originales. La fecha de generación puede cambiar entre ejecuciones.
