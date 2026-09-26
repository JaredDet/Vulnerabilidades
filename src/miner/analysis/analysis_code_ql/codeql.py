"""Interacción con CodeQL CLI."""

import os
import shutil
import subprocess
from pathlib import Path

from .constants import (
    CODEQL_ANALYZE_COMMAND,
    CODEQL_CREATE_COMMAND,
    CODEQL_DATABASE_COMMAND,
    CODEQL_DATABASE_FILENAME,
    CODEQL_LANGUAGE_PATTERN,
    CODEQL_SARIF_FORMAT,
    DEFAULT_ANALYSIS_TIMEOUT,
    DEFAULT_CODEQL_EXECUTABLE,
    DEFAULT_DATABASE_TIMEOUT,
    GITHUB_TOKEN_ENVIRONMENT_VARIABLE,
    SECURITY_SUITE_TEMPLATE,
)
from .errors import CodeQLErrors


def create_database(
    source_path: Path,
    database_path: Path,
    *,
    token: str,
    executable: str = DEFAULT_CODEQL_EXECUTABLE,
    timeout: float = DEFAULT_DATABASE_TIMEOUT,
) -> Path:
    """Crea un clúster de bases CodeQL y devuelve su ruta absoluta."""
    if timeout <= 0:
        raise CodeQLErrors.InvalidTimeout

    try:
        source = source_path.resolve()
        database = database_path.resolve()

        if not source.is_dir():
            raise CodeQLErrors.SourceNotFound

        if database.is_relative_to(source):
            raise CodeQLErrors.DatabaseInsideSource

        if database.exists():
            shutil.rmtree(database)

        database.parent.mkdir(parents=True, exist_ok=True)

        environment = {
            **os.environ,
            GITHUB_TOKEN_ENVIRONMENT_VARIABLE: token,
        }

        subprocess.run(
            [
                executable,
                CODEQL_DATABASE_COMMAND,
                CODEQL_CREATE_COMMAND,
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
        raise CodeQLErrors.CodeQLNotAvailable from None
    except subprocess.TimeoutExpired:
        raise CodeQLErrors.DatabaseCreationTimeout from None
    except subprocess.CalledProcessError:
        raise CodeQLErrors.DatabaseCreationFailed from None
    except OSError:
        raise CodeQLErrors.CodeQLAccessFailed from None

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
        raise CodeQLErrors.InvalidTimeout

    language = language.strip()

    if not CODEQL_LANGUAGE_PATTERN.fullmatch(language):
        raise CodeQLErrors.InvalidLanguage

    try:
        database = database_path.resolve()
        output = sarif_path.resolve()

        if not (database / CODEQL_DATABASE_FILENAME).is_file():
            raise CodeQLErrors.DatabaseNotFound

        if output.exists():
            raise CodeQLErrors.SarifAlreadyExists

        if output.is_relative_to(database):
            raise CodeQLErrors.SarifInsideDatabase

        output.parent.mkdir(parents=True, exist_ok=True)

        suite = SECURITY_SUITE_TEMPLATE.format(language=language)

        subprocess.run(
            [
                executable,
                CODEQL_DATABASE_COMMAND,
                CODEQL_ANALYZE_COMMAND,
                str(database),
                suite,
                f"--format={CODEQL_SARIF_FORMAT}",
                f"--output={output}",
            ],
            check=True,
            capture_output=True,
            timeout=timeout,
        )

        if not output.is_file():
            raise CodeQLErrors.SarifNotGenerated

    except FileNotFoundError:
        raise CodeQLErrors.CodeQLNotAvailable from None
    except subprocess.TimeoutExpired:
        raise CodeQLErrors.AnalysisTimeout from None
    except subprocess.CalledProcessError:
        raise CodeQLErrors.AnalysisFailed from None
    except OSError:
        raise CodeQLErrors.CodeQLAccessFailed from None

    return output
