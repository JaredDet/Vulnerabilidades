# Miner

Herramienta para listar y clonar repositorios de una organización de GitHub,
analizarlos con CodeQL y guardar los hallazgos en JSON.

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
uv run miner analyze --organization pallets --ruta xkfbl6pl
```

`clone` muestra un JSON con las rutas locales, errores y conteos en stdout.
`analyze` busca la clonación más reciente de la organización y analiza sus
repositorios locales. Si no hay clones, indica que debes ejecutar `clone` primero.
El progreso de ambos comandos va a stderr. `analyze` reemplaza al comando `scan`.

| Opción | Comando | Uso |
| --- | --- | --- |
| `--workspace RUTA` | `clone` | Cambiar el directorio donde guardar las ejecuciones. |
| `--ruta ID` | `analyze` | Elegir una ejecución por su identificador, sin `scan-`, `clone-` ni la ruta completa. |
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
Sin `--ruta`, `analyze` busca en `organizations/<organización>/work/`.
Por ejemplo, `--ruta xkfbl6pl` selecciona `scan-xkfbl6pl` dentro de esa carpeta.
La búsqueda de `analyze` usa este directorio estándar; los clones guardados con
un `--workspace` personalizado pueden procesarse mediante la API de Python.
Las carpetas antiguas `scan-*` se leen directamente desde sus repositorios Git;
no permiten recuperar los fallos de clonación que no dejaron un repositorio.
El análisis crea un directorio `analysis-<id>/` dentro de esa misma ejecución
para las bases CodeQL y los archivos SARIF.

**SBOM está pendiente:** el comando `sbom` y sus módulos todavía no generan resultados.

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
    sbom/         # Pendiente de implementar
tests/
```

`clone.pipeline.clone_organization` devuelve las rutas y los fallos de clonación.
`analysis.pipeline.analyze_organization` recibe ese resultado sin volver a
consultar GitHub ni clonar. Esta separación permite reutilizar los clones desde
Python y conectar el flujo de SBOM más adelante.

```powershell
uv run pytest -q
```

Las pruebas simulan GitHub y CodeQL y verifican Git con un repositorio temporal
local. No requieren un token válido ni CodeQL instalado.

Los clones, bases, SARIF, entornos locales y `results.json` están excluidos de Git.
