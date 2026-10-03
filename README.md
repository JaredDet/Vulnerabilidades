# Miner

Herramienta para clonar repositorios de una organización de GitHub,
analizarlos con CodeQL y generar inventarios SBOM con Syft. Los resultados se guardan en JSON.

## Preparación

Requiere Python 3.11+, uv y Git. Para analizar también necesitas CodeQL CLI
con sus extractores y paquetes de consultas instalados. Git y CodeQL deben
estar en `PATH`, al igual que Syft y Grype.

```powershell
uv sync
Copy-Item .env.example .env
```

Completa `GITHUB_TOKEN` en `.env` con un token que pueda leer los repositorios.
La aplicación carga `.env` automáticamente mediante `python-dotenv`; también
puedes definir la variable en el entorno. `.env` está excluido de Git.
`uv sync` instala las dependencias, incluidas Typer y python-dotenv.

## Uso

Para ejecutar el flujo completo en orden: clonación, CodeQL, Syft, Grype y dataset:

```powershell
uv run miner run --organization pallets
```

`run` acepta `--workspace`, `--page-size` y `--timeout`
(600 segundos por operación). Todas las etapas reutilizan la misma ejecución
de clones y Grype consume el SBOM recién generado. Los fallos individuales se
conservan en los reportes; un error global detiene el flujo.

Para integrar resultados existentes sin volver a ejecutar las herramientas:

```powershell
uv run miner generate-dataset --organization pallets --run-id zrhbvqrb
```

El archivo `dataset.json` queda junto a `clones.json`, dentro de `clone-<id>/`.
Contiene una lista común de hallazgos de CodeQL y Grype, repositorio, identificador,
descripción, severidad, ubicaciones, lenguaje o paquete y versión, y rutas relativas
a la evidencia original. El commit se conserva cuando la fuente lo proporciona.
`severity_kind` distingue el nivel SARIF de la severidad de vulnerabilidad de Grype.
El esquema 1.1 incluye `scores`: una lista de puntajes originales con `value`,
`system`, `source`, `version`, `vector` e identificador de vulnerabilidad.
CodeQL aporta `security-severity`; Grype aporta los puntajes base CVSS disponibles,
incluidos los de vulnerabilidades relacionadas, sin elegir ni promediar fuentes.
Si no hay puntajes, la lista queda vacía. Los campos de versión o vector ausentes
quedan en `null`. No se calcula un puntaje a partir de la severidad cualitativa.
También conserva los estados y errores por repositorio; `not_run` significa que
no se encontró un reporte de esa herramienta. Selecciona el último reporte terminado
de cada herramienta dentro de la ejecución de clones indicada.

```powershell
# Consultar la organización y clonar repositorios
uv run miner clone-repositories --organization pallets

# Analizar la clonación más reciente, sin volver a clonar
uv run miner analyze-code --organization pallets --output results.json

# Elegir una ejecución concreta de clones
uv run miner analyze-code --organization pallets --run-id xkfbl6pl

# Buscar vulnerabilidades en las dependencias
uv run miner scan-dependency-vulnerabilities --organization pallets
uv run miner scan-dependency-vulnerabilities --organization pallets --run-id 7o9x8nb_
```

`clone-repositories` consulta la organización y muestra un JSON con las rutas
locales, errores y conteos en stdout. `analyze-code` busca la clonación
más reciente de la organización y analiza sus
repositorios locales. Si no hay clones, indica que debes ejecutar
`clone-repositories` primero.
El progreso de ambos comandos va a stderr.

| Opción | Comando | Uso |
| --- | --- | --- |
| `--workspace RUTA` | `clone-repositories` | Cambiar el directorio donde guardar las ejecuciones. |
| `--run-id ID` | `analyze-code`, `generate-sbom` | Elegir una ejecución de clones por su identificador, sin `clone-` ni la ruta completa. |
| `--run-id ID` | `scan-dependency-vulnerabilities` | Elegir una ejecución SBOM por su identificador, sin `sbom-` ni la ruta completa. |
| `--timeout SEGUNDOS` | `clone-repositories` | Límite por clonación; por defecto, 300. |
| `--timeout SEGUNDOS` | `analyze-code` | Límite por creación de base y análisis; por defecto, 600. |
| `--output ARCHIVO` | `analyze-code`, `generate-sbom`, `scan-dependency-vulnerabilities` | Exportar una copia adicional; no se exporta por defecto. |

Los códigos de salida permiten distinguir errores globales del comando:

| Código | Significado |
| --- | --- |
| `0` | Comando completado. |
| `1` | Error inesperado. |
| `2` | Uso o datos de entrada no válidos, incluidos los errores de opciones de Typer. |
| `3` | Conflicto, por ejemplo, un archivo de salida que ya existe. |
| `4` | Recurso solicitado no encontrado. |
| `5` | Autenticación no autorizada. |
| `6` | Acceso prohibido. |
| `7` | Error de un servicio externo. |
| `8` | Error de acceso al sistema de archivos. |

Los errores de repositorios individuales se incluyen en el reporte y no cambian
el código de salida si el comando pudo completar el resto del trabajo.

```powershell
uv run miner --help
```

Cada ejecución guarda sus clones en
`organizations/<organización>/work/clone-<id>/repositories/`.
Al terminar, guarda las rutas y los fallos en `clones.json` dentro de esa ejecución.
Sin `--run-id`, `analyze-code` busca en `organizations/<organización>/work/`.
Por ejemplo, `--run-id xkfbl6pl` selecciona `clone-xkfbl6pl` dentro de esa carpeta.
La búsqueda de `analyze-code` usa este directorio estándar; los clones guardados con
un `--workspace` personalizado pueden procesarse mediante la API de Python.
El análisis crea un directorio `codeql-<id>/` dentro de esa misma ejecución
para las bases CodeQL y los archivos SARIF.

Para generar SBOM necesitas Syft instalado aparte del entorno Python. En Windows:

```powershell
winget install --id Anchore.Syft --exact
```

Abre una terminal nueva y comprueba `syft version`. Luego ejecuta:

```powershell
uv run miner generate-sbom --organization pallets
uv run miner generate-sbom --organization pallets --run-id xkfbl6pl --output sbom-results.json
```

SBOM reutiliza los clones locales sin requerir token ni volver a clonar.
Acepta `--timeout SEGUNDOS` (600 por defecto); Syft se busca en `PATH`.
Cada ejecución guarda archivos CycloneDX JSON en una carpeta nueva `sbom-<id>/`
dentro de la clonación, y un reporte con commit, versión de Syft, fecha,
cantidad de componentes y errores. Si no hay repositorios, escribe un reporte vacío.

El análisis de vulnerabilidades con Grype examina las dependencias identificadas
en esos SBOM. Su `--run-id` selecciona la ejecución SBOM (sin el prefijo `sbom-`):

```powershell
uv run miner scan-dependency-vulnerabilities --organization pallets
uv run miner scan-dependency-vulnerabilities --organization pallets --run-id 7o9x8nb_
```

## Resultados

Cada etapa guarda un único reporte dentro de la ejecución de clones:

- `analysis_results/codeql-<id>/codeql-results.json`
- `sboms/sbom-<id>/sbom-results.json`
- `vulnerabilities/vulnerability-<id>/vulnerability-results.json`

`clones.json` y `dataset.json` quedan junto a esas carpetas. Los comandos
individuales aceptan `--output` para exportar una copia cuando sea necesaria.
`--page-size` (o `-p`) controla los repositorios por petición a GitHub,
entre 1 y 100 (100 por defecto), en `clone-repositories` y `run`.
Se recorren todas las páginas sin filtrar por lenguaje ni limitar el total. Los límites de tiempo y la
selección por `--run-id` o última ejecución se mantienen. La API de Python
conserva la posibilidad de indicar ejecutables para integraciones y pruebas.
Los errores de acceso a cada herramienta se agrupan; los tiempos agotados,
conflictos y estados de análisis siguen distinguiéndose.

CodeQL detecta los lenguajes al crear el clúster de bases y ejecuta la suite
`<lenguaje>-code-scanning.qls`. Los proyectos compilados pueden necesitar sus
dependencias y herramientas de construcción.

El reporte incluye un resumen, resultados por repositorio y resultados por
lenguaje en `languages`. Cada hallazgo contiene regla, mensaje, nivel SARIF y
ubicación cuando está disponible. Son alertas estáticas, no vulnerabilidades
confirmadas.

Los fallos individuales quedan en el resultado y no detienen los demás
repositorios. `partial` indica que algunos lenguajes se analizaron y otros
fallaron. Revisa el resumen aunque el comando termine con código cero.
Los errores globales de consulta o escritura terminan con código distinto de cero.
El reporte se escribe de forma atómica al terminar la etapa; una
organización vacía también genera un JSON.

## Desarrollo

Cada pull request y cada push a `main` ejecuta las pruebas con Python 3.11 y
analiza el propio código con CodeQL, Syft y Grype en contenedores Docker. Los
reportes quedan disponibles como el artefacto `security-reports` de la ejecución
de GitHub Actions. Syft y Grype usan imágenes versionadas; la imagen de CodeQL
se configura en `CODEQL_IMAGE` porque el contenedor disponible está en vista
previa y puede cambiar.

La ejecución local busca `codeql`, `syft` y `grype` en `PATH`.

```text
src/miner/
    cli.py        # Comandos y composición de los flujos
    clone/        # GitHub, clonación y modelos de clones
    codeql/       # CodeQL, SARIF, modelos y reporte
    sbom/         # Syft, CycloneDX y reporte
    dependencies/ # Grype y vulnerabilidades de dependencias
tests/
docs/             # Diagramas PlantUML de los flujos
```

`clone.pipeline.clone_organization` devuelve las rutas y los fallos de clonación.
`codeql.pipeline.analyze_organization` recibe ese resultado sin volver a
consultar GitHub ni clonar. Esta separación permite reutilizar los clones desde
Python. SBOM usa el mismo selector de clones que `analyze-code`.

```powershell
uv run pytest -q
# Solo SBOM
uv run pytest tests/test_sbom.py tests/test_syft.py tests/test_sbom_report.py -q
```

Las pruebas simulan GitHub, CodeQL y Syft y verifican la clonación Git con un
repositorio temporal local. No requieren un token válido, CodeQL ni Syft instalado.
SBOM tiene pruebas de selección de clones, `--run-id`, ejecuciones repetidas,
errores, documentos inválidos, reportes vacíos, escritura atómica y CLI.

Los diagramas de [clonación](docs/clone.puml), [análisis](docs/analyze.puml),
[SBOM](docs/sbom.puml) y [vulnerabilidades de dependencias](docs/vulnerabilities.puml)
están en [docs/](docs/README.md).

Los clones, bases, SARIF, entornos locales, `results.json` y `sbom-results.json`
están excluidos de Git.
