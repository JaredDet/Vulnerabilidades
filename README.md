# Miner de vulnerabilidades

Aplicación Python que consulta los repositorios accesibles de una organización,
clona cada uno, selecciona lenguajes mediante la API de GitHub y los extractores
instalados de CodeQL, ejecuta sus consultas estándar de seguridad y transforma
SARIF en un JSON consolidado con modelos Pydantic.

## Instalación

Requiere Python 3.11+, Git, uv y CodeQL CLI con extractores y paquetes de consultas.
Instala el bundle de CodeQL siguiendo la [documentación oficial](https://docs.github.com/en/code-security/how-tos/scan-code-for-vulnerabilities/scan-from-command-line/setting-up-the-codeql-cli).
Git y CodeQL deben estar en PATH; también se puede indicar `--codeql`.

```powershell
uv sync
git --version
codeql version
codeql resolve languages
codeql resolve packs
```

El proyecto se ha probado con CodeQL 2.26.4 en Windows. Los lenguajes compilados
pueden requerir sus compiladores, dependencias y herramientas de construcción.
La disponibilidad de un extractor no garantiza que el proyecto se pueda construir.
CodeQL puede ejecutar pasos de construcción del repositorio: utiliza un entorno
de análisis apropiado para el código que vas a procesar.

## Token

Crea un token personal de GitHub con lectura de los repositorios necesarios.
Para públicos basta acceso público de lectura. Para privados, el token necesita
acceso al repositorio y permisos de lectura de Metadata y Contents, además de las
autorizaciones que exija la organización.

Copia `.env.example` a `.env` e introduce el token solo en `.env`, que está excluido
de Git. El ejemplo contiene únicamente `GITHUB_TOKEN=`. No incluyas credenciales en
commits, URLs, ejemplos o documentación. También puedes definir `GITHUB_TOKEN`
directamente en el entorno; en ese caso omite `--env-file .env`.

## Ejecución

```powershell
uv run --env-file .env miner scan --organization pallets --output results.json
```

En Windows, si CodeQL no está en PATH:

```powershell
uv run --env-file .env miner scan --organization pallets --output results.json --codeql "C:\Program Files (x86)\codeql\codeql.exe"
```

Opciones: `--workspace work` controla los archivos de trabajo y `--timeout 600`
limita cada creación de base y cada análisis a ese número de segundos. La clonación
tiene un límite de 300 segundos. Cada ejecución crea un subdirectorio nuevo para
evitar sobrescribir clones y bases. Esos archivos quedan disponibles para diagnóstico
y no forman parte de la entrega; puedes eliminarlos cuando termines.

```powershell
uv run --env-file .env miner list pallets
uv run miner scan --help
uv run pytest -q
```

El comando antiguo `miner pallets` se reemplaza por `miner list pallets`.
La organización se recibe siempre por consola. El token se obtiene del entorno
y se transmite a Git mediante configuración temporal del proceso, sin guardarlo
en el remoto del repositorio clonado.

## Resultados y errores

El JSON incluye organización, resumen, resultados por repositorio y hallazgos.
`languages` contiene los identificadores cuyos análisis terminaron correctamente;
`detected_languages` conserva lo detectado por GitHub y `analyses` registra cada intento.
Cada hallazgo incluye regla, mensaje, nivel SARIF y ubicación principal si existe.
El nivel (`error`, `warning`, `note`, `none`) no es una puntuación CVSS.

Estados: `analyzed`, `clone_failed`, `unsupported`, `language_detection_failed`,
`database_failed`, `analysis_failed`, `sarif_failed`, `partial` y `failed`.
`partial` significa que algunos lenguajes se analizaron y otros fallaron.
Los fallos incluyen una razón y no detienen otros repositorios. Un fallo global
(token inválido, listado incompleto, CodeQL ausente o imposibilidad de escribir)
termina el comando con código distinto de cero. Una ejecución completa con fallos
individuales termina con cero: el resumen del JSON informa esos fallos.

Se guarda un avance atómico después de cada repositorio y un JSON final al terminar.
Los mensajes van a stderr; nunca se mezclan con el JSON. Los repositorios se ordenan
por nombre y los hallazgos por archivo, línea, regla y criterios de desempate.
Los conteos del resumen se calculan desde los modelos. Con iguales datos de entrada
la organización del JSON es estable; cambios en repositorios, API, dependencias o
paquetes CodeQL pueden cambiar los resultados.

Se utiliza la suite oficial `<lenguaje>-code-scanning.qls` del paquete
`codeql/<lenguaje>-queries`. No se descarga automáticamente durante el análisis:
debe estar instalado. Los extractores auxiliares se excluyen; YAML no se interpreta
como un workflow de GitHub Actions. El listado de lenguajes de GitHub es orientativo
y puede diferir del commit clonado. No se inspecciona el árbol local para detectarlos.

## Estructura

```text
miner/
├── src/miner/       # Paquete Python de la aplicación
├── tests/           # Pruebas por componente
├── work/            # Clones, bases y SARIF; excluido de Git
├── results.json     # Resultado consolidado de la ejecución
├── pyproject.toml
├── uv.lock
├── .env.example
└── README.md
```

Los módulos siguientes están dentro de `src/miner/`:

- `github_api.py`: Requests, autenticación, paginación y lenguajes.
- `clone.py`: clonación Git.
- `languages.py`: equivalencias y selección de extractores.
- `codeql.py`: ejecución del CLI, bases y análisis.
- `sarif.py`: interpretación de SARIF 2.1.0.
- `models.py`: modelos Pydantic.
- `report.py`: JSON estable y escritura atómica.
- `pipeline.py`: coordinación y aislamiento de errores.
- `cli.py`: aplicación Typer.
- `tests/`: pruebas pytest con HTTP/CodeQL simulados y clonación local.

El paquete también se puede ejecutar con `uv run python -m miner --help`.

## Entrega

Incluye el enlace al repositorio del proyecto y `results.json` de una ejecución
completa. No incluyas `.env`, ambientes virtuales, `work/`, repositorios clonados,
bases de datos o SARIF temporales. `uv.lock` y `.env.example` sí se versionan.

### Ejecución incluida

`results.json` se generó con una ejecución completa sobre `pallets`, CodeQL 2.26.4
y `--timeout 180`: 17 repositorios, 13 analizados, 3 sin lenguajes compatibles,
1 parcial y 86 hallazgos. En MarkupSafe se analizó Python y falló la creación
de la base C/C++; el motivo queda registrado en el JSON. Son alertas estáticas,
no una confirmación manual de vulnerabilidades explotables.

La validación del proyecto incluye 83 pruebas pytest aprobadas y construcción
correcta del wheel mediante `uv build`.

### Organización de las pruebas

Cada componente tiene su archivo en `tests/`: `test_github_api.py`, `test_clone.py`,
`test_languages.py`, `test_codeql.py`, `test_sarif.py`, `test_models.py`,
`test_report.py`, `test_cli.py` y `test_miner.py`.
Las pruebas no consultan GitHub ni ejecutan CodeQL; la clonación real se prueba
con un repositorio temporal local. No necesitan el token ni cargar `.env`.

```powershell
uv run pytest -q
uv run pytest tests/test_sarif.py tests/test_report.py -q
```
