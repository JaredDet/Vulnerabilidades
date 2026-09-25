"""Interacción con CodeQL CLI."""

import os
import re
import shutil
import subprocess
from pathlib import Path

DEFAULT_CODEQL_EXECUTABLE = "codeql"
DEFAULT_DATABASE_TIMEOUT = 600
DEFAULT_ANALYSIS_TIMEOUT = 600

CODEQL_LANGUAGE_PATTERN = re.compile(r"[a-z][a-z0-9-]*")

SECURITY_SUITE_TEMPLATE = (
    "codeql/{language}-queries:codeql-suites/{language}-code-scanning.qls"
)


class CodeQLError(RuntimeError):
    """No se pudo ejecutar CodeQL o interpretar su respuesta."""


def create_database(
    source_path: Path,
    database_path: Path,
    *,
    token: str,
    executable: str = DEFAULT_CODEQL_EXECUTABLE,
    timeout: float = DEFAULT_DATABASE_TIMEOUT,
) -> Path:
    """Crea un clúster de bases CodeQL y devuelve su ruta absoluta.

    CodeQL determina automáticamente los lenguajes que puede analizar
    y crea una base independiente para cada lenguaje detectado.
    """
    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")

    try:
        source = Path(source_path).resolve()
        database = Path(database_path).resolve()

        if not source.is_dir():
            raise CodeQLError("La carpeta de código fuente no existe")

        if database.is_relative_to(source):
            raise CodeQLError(
                "La base debe quedar fuera de la carpeta de código fuente"
            )

        if database.exists():
            shutil.rmtree(database)

        database.parent.mkdir(parents=True, exist_ok=True)

        environment = {
            **os.environ,
            "GITHUB_TOKEN": token,
        }

        subprocess.run(
            [
                executable,
                "database",
                "create",
                str(database),
                "--db-cluster",
                f"--source-root={source}",
            ],
            check=True,
            capture_output=True,
            timeout=timeout,
            env=environment,
        )

    except FileNotFoundError:
        raise CodeQLError("No se encontró CodeQL o una ruta necesaria") from None

    except subprocess.TimeoutExpired:
        raise CodeQLError(
            "Se agotó el tiempo al crear las bases de datos CodeQL"
        ) from None

    except subprocess.CalledProcessError as error:
        raise CodeQLError(
            f"CodeQL no pudo crear las bases de datos (código {error.returncode})"
        ) from None

    except OSError:
        raise CodeQLError(
            "No se pudo ejecutar CodeQL o acceder a sus carpetas"
        ) from None

    return database


def analyze_database(
    database_path: Path,
    language: str,
    sarif_path: Path,
    *,
    executable: str = DEFAULT_CODEQL_EXECUTABLE,
    timeout: float = DEFAULT_ANALYSIS_TIMEOUT,
) -> Path:
    """Analiza una base CodeQL con la suite estándar de Code Scanning."""

    if timeout <= 0:
        raise ValueError("timeout debe ser mayor que cero")

    language = language.strip()

    if not CODEQL_LANGUAGE_PATTERN.fullmatch(language):
        raise ValueError("Debes indicar un identificador de lenguaje CodeQL válido")

    try:
        database = Path(database_path).resolve()
        output = Path(sarif_path).resolve()

        if not (database / "codeql-database.yml").is_file():
            raise CodeQLError(
                "No se encontró una base de datos CodeQL en la ruta indicada"
            )

        # TODO: verify if the results file name follows the results-scan-XXXXX convention upon creation.
        if output.exists():
            raise CodeQLError(f"El archivo de resultados ya existe: {output}")

        if output.is_relative_to(database):
            raise CodeQLError("El SARIF debe quedar fuera de la base de datos")

        output.parent.mkdir(parents=True, exist_ok=True)

        suite = SECURITY_SUITE_TEMPLATE.format(
            language=language,
        )

        subprocess.run(
            [
                executable,
                "database",
                "analyze",
                str(database),
                suite,
                "--format=sarifv2.1.0",
                f"--output={output}",
            ],
            check=True,
            capture_output=True,
            timeout=timeout,
        )

        if not output.is_file():
            raise CodeQLError("CodeQL terminó sin generar el archivo SARIF")

    except FileNotFoundError:
        raise CodeQLError("No se encontró CodeQL o una ruta necesaria") from None

    except subprocess.TimeoutExpired:
        raise CodeQLError(
            "Se agotó el tiempo al ejecutar las consultas CodeQL"
        ) from None

    except subprocess.CalledProcessError as error:
        raise CodeQLError(
            f"El análisis CodeQL falló (código {error.returncode}); "
            "revisa la base y el paquete de consultas instalado"
        ) from None

    except OSError:
        raise CodeQLError(
            "No se pudo ejecutar CodeQL o acceder a sus archivos"
        ) from None

    return output
