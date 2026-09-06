"""Interacción con CodeQL CLI."""

import json
import re
import subprocess
from pathlib import Path

DEFAULT_CODEQL_EXECUTABLE = "codeql"
DEFAULT_RESOLVE_TIMEOUT = 30
DEFAULT_DATABASE_TIMEOUT = 600
DEFAULT_ANALYSIS_TIMEOUT = 600
CODEQL_LANGUAGE_PATTERN = re.compile(r"[a-z][a-z0-9-]*")
SECURITY_SUITE_TEMPLATE = "codeql/{language}-queries:codeql-suites/{language}-code-scanning.qls"


def analyze_database(
    database_path: Path,
    language: str,
    sarif_path: Path,
    *,
    executable: str = DEFAULT_CODEQL_EXECUTABLE,
    timeout: float = DEFAULT_ANALYSIS_TIMEOUT,
) -> Path:
    """Ejecuta la suite estándar code-scanning y devuelve la ruta del SARIF.

    Requiere el paquete codeql/<language>-queries instalado. No sobrescribe
    resultados existentes. Los fallos del CLI se comunican como CodeQLError.
    """
    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")
    language = language.strip()
    if not CODEQL_LANGUAGE_PATTERN.fullmatch(language):
        raise ValueError("Debes indicar un identificador de lenguaje CodeQL válido")
    try:
        database = Path(database_path).resolve()
        output = Path(sarif_path).resolve()
        if not (database / "codeql-database.yml").is_file():
            raise CodeQLError("No se encontró una base de datos CodeQL en la ruta indicada")
        if output.exists():
            raise CodeQLError(f"El archivo de resultados ya existe: {output}")
        if output.is_relative_to(database):
            raise CodeQLError("El SARIF debe quedar fuera de la base de datos")
        output.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [executable, "database", "analyze", str(database),
             SECURITY_SUITE_TEMPLATE.format(language=language),
             "--format=sarifv2.1.0", f"--output={output}"],
            check=True, capture_output=True, timeout=timeout,
        )
        if not output.is_file():
            raise CodeQLError("CodeQL terminó sin generar el archivo SARIF")
    except FileNotFoundError:
        raise CodeQLError("No se encontró CodeQL o una ruta necesaria") from None
    except subprocess.TimeoutExpired:
        raise CodeQLError("Se agotó el tiempo al ejecutar las consultas CodeQL") from None
    except subprocess.CalledProcessError as error:
        raise CodeQLError(
            f"El análisis CodeQL falló (código {error.returncode}); "
            "revisa la base y el paquete de consultas instalado"
        ) from None
    except OSError:
        raise CodeQLError("No se pudo ejecutar CodeQL o acceder a sus archivos") from None
    return output


class CodeQLError(RuntimeError):
    """No se pudo ejecutar CodeQL o interpretar su respuesta."""


def create_database(
    source_path: Path,
    language: str,
    database_path: Path,
    *,
    executable: str = DEFAULT_CODEQL_EXECUTABLE,
    timeout: float = DEFAULT_DATABASE_TIMEOUT,
) -> Path:
    """Crea una base para un lenguaje y devuelve su ruta absoluta.

    CodeQL selecciona la extracción o construcción automática del proyecto.
    No sobrescribe bases existentes. Si falla, conserva los archivos parciales
    para diagnóstico y lanza CodeQLError.
    """
    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")
    language = language.strip()
    if not language or "," in language:
        raise ValueError("Debes indicar un único lenguaje de CodeQL")
    try:
        source = Path(source_path).resolve()
        database = Path(database_path).resolve()
        if not source.is_dir():
            raise CodeQLError("La carpeta de código fuente no existe")
        if database.exists():
            raise CodeQLError(f"El destino de la base ya existe: {database}")
        if database.is_relative_to(source):
            raise CodeQLError("La base debe quedar fuera de la carpeta de código fuente")
        database.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [executable, "database", "create", str(database),
             f"--language={language}", f"--source-root={source}"],
            check=True, capture_output=True, timeout=timeout,
        )
    except FileNotFoundError:
        raise CodeQLError("No se encontró CodeQL o una ruta necesaria") from None
    except subprocess.TimeoutExpired:
        raise CodeQLError("Se agotó el tiempo al crear la base de datos CodeQL") from None
    except subprocess.CalledProcessError as error:
        raise CodeQLError(
            f"CodeQL no pudo crear la base para {language} (código {error.returncode})"
        ) from None
    except OSError:
        raise CodeQLError("No se pudo ejecutar CodeQL o acceder a sus carpetas") from None
    return database


def get_available_languages(
    executable: str = DEFAULT_CODEQL_EXECUTABLE,
    *,
    timeout: float = DEFAULT_RESOLVE_TIMEOUT,
) -> set[str]:
    """Consulta los extractores una vez; el llamador reutiliza el resultado.

    Acepta una ruta al ejecutable cuando CodeQL no está en PATH. Los extractores
    disponibles no garantizan la presencia de consultas de seguridad.
    """
    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")
    try:
        result = subprocess.run(
            [executable, "resolve", "languages", "--format=json"],
            check=True, capture_output=True, timeout=timeout,
        )
    except FileNotFoundError:
        raise CodeQLError("No se encontró CodeQL; revisa PATH o indica su ruta") from None
    except subprocess.TimeoutExpired:
        raise CodeQLError("Se agotó el tiempo al consultar los lenguajes de CodeQL") from None
    except subprocess.CalledProcessError as error:
        raise CodeQLError(f"CodeQL terminó con código {error.returncode}") from None
    except OSError:
        raise CodeQLError("No se pudo ejecutar CodeQL") from None

    try:
        data = json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise CodeQLError("CodeQL devolvió JSON inválido") from None
    if not isinstance(data, dict) or any(
        not name.strip() or not isinstance(paths, list)
        or not all(isinstance(path, str) and path.strip() for path in paths)
        for name, paths in data.items()
    ):
        raise CodeQLError("CodeQL devolvió un formato de extractores inesperado")
    return {name for name, paths in data.items() if paths}
