# Miner

Herramienta para listar y clonar repositorios de una organización de GitHub,
analizarlos con CodeQL y generar inventarios SBOM con Syft. Los resultados se guardan en JSON.

## Preparación

Requiere Python 3.11+, uv y Git. Para analizar también necesitas CodeQL CLI
con sus extractores y paquetes de consultas instalados. Git y CodeQL deben
estar en `PATH`; puedes indicar otra ruta de CodeQL con `--codeql`.

```powershell
uv sync
Copy-Item .env.example .env
```

Completa `GITHUB_TOKEN` en `.env` con un token que pueda leer los repositorios.
La aplicación carga `.env` automáticamente mediante `python-dotenv`; también
puedes definir la variable en el entorno. `.env` está excluido de Git.
`uv sync` instala las dependencias, incluidas Typer y python-dotenv.

## Uso

```powershell
# Listar repositorios
uv run miner list pallets

# Solo clonar, sin ejecutar CodeQL
uv run miner clone --organization pallets

# Analizar la clonación más reciente, sin volver a clonar
uv run miner analyze --organization pallets --output results.json

# Elegir una ejecución concreta (también acepta las carpetas scan antiguas)
uv run miner analyze --organization pallets --run-id xkfbl6pl
```

`clone` muestra un JSON con las rutas locales, errores y conteos en stdout.
`analyze` busca la clonación más reciente de la organización y analiza sus
repositorios locales. Si no hay clones, indica que debes ejecutar `clone` primero.
El progreso de ambos comandos va a stderr. `analyze` reemplaza al comando `scan`.

| Opción | Comando | Uso |
| --- | --- | --- |
| `--workspace RUTA` | `clone` | Cambiar el directorio donde guardar las ejecuciones. |
| `--run-id ID` | `analyze`, `sbom` | Elegir una ejecución por su identificador, sin `scan-`, `clone-` ni la ruta completa. |
| `--timeout SEGUNDOS` | `clone` | Límite por clonación; por defecto, 300. |
| `--timeout SEGUNDOS` | `analyze` | Límite por creación de base y análisis; por defecto, 600. |
| `--output ARCHIVO` | `analyze` | Reporte JSON; por defecto, `results.json`. |
| `--codeql RUTA` | `analyze` | Ejecutable de CodeQL; por defecto, `codeql`. |

```powershell
uv run miner analyze --organization pallets --codeql "C:\Program Files (x86)\codeql\codeql.exe"
uv run miner --help
```

Cada ejecución guarda sus clones en
`organizations/<organización>/work/clone-<id>/repositories/`.
Al terminar, guarda las rutas y los fallos en `clones.json` dentro de esa ejecución.
Sin `--run-id`, `analyze` busca en `organizations/<organización>/work/`.
Por ejemplo, `--run-id xkfbl6pl` selecciona `scan-xkfbl6pl` dentro de esa carpeta.
La búsqueda de `analyze` usa este directorio estándar; los clones guardados con
un `--workspace` personalizado pueden procesarse mediante la API de Python.
Las carpetas antiguas `scan-*` se leen directamente desde sus repositorios Git;
no permiten recuperar los fallos de clonación que no dejaron un repositorio.
El análisis crea un directorio `analysis-<id>/` dentro de esa misma ejecución
para las bases CodeQL y los archivos SARIF.

Para generar SBOM necesitas Syft instalado aparte del entorno Python. En Windows:

```powershell
winget install --id Anchore.Syft --exact
```

Abre una terminal nueva y comprueba `syft version`. Luego ejecuta:

```powershell
uv run miner sbom --organization pallets
uv run miner sbom --organization pallets --run-id xkfbl6pl --output sbom-results.json
# Si Syft no está en PATH
uv run miner sbom --organization pallets --syft "C:\tools\syft\syft.exe"
```

SBOM reutiliza los clones locales sin requerir token ni volver a clonar.
Acepta `--syft RUTA` y `--timeout SEGUNDOS` (600 por defecto).
Cada ejecución guarda archivos CycloneDX JSON en una carpeta nueva `sbom-<id>/`
dentro de la clonación, y un reporte con commit, versión de Syft, fecha,
cantidad de componentes y errores. Si no hay repositorios, escribe un reporte vacío.

## Resultados

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
El reporte se actualiza de forma atómica después de cada repositorio; una
organización vacía también genera un JSON.

## Desarrollo

```text
src/miner/
    cli.py        # Comandos y composición de los flujos
    clone/        # GitHub, clonación y modelos de clones
    analysis/     # CodeQL, SARIF, modelos y reporte
    sbom/         # Syft, CycloneDX y reporte
tests/
docs/             # Diagramas PlantUML de los flujos
```

`clone.pipeline.clone_organization` devuelve las rutas y los fallos de clonación.
`analysis.pipeline.analyze_organization` recibe ese resultado sin volver a
consultar GitHub ni clonar. Esta separación permite reutilizar los clones desde
Python. SBOM usa el mismo selector de clones que el comando `analyze`.

```powershell
uv run pytest -q
# Solo SBOM
uv run pytest tests/test_sbom.py tests/test_syft.py tests/test_sbom_report.py -q
```

Las pruebas simulan GitHub, CodeQL y Syft y verifican la clonación Git con un
repositorio temporal local. No requieren un token válido, CodeQL ni Syft instalado.
SBOM tiene pruebas de selección de clones, `--run-id`, ejecuciones repetidas,
errores, documentos inválidos, reportes vacíos, escritura atómica y CLI.

Los diagramas de [list](docs/list.puml), [clone](docs/clone.puml),
[analyze](docs/analyze.puml) y [sbom](docs/sbom.puml) están en [docs/](docs/README.md).

Los clones, bases, SARIF, entornos locales, `results.json` y `sbom-results.json`
están excluidos de Git.
