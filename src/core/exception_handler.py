"""Traduce excepciones de la aplicación a mensajes y códigos de salida CLI."""

from collections.abc import Callable
from enum import Enum

from core.exceptions import AppException, ErrorType


class ExitCode(Enum):
    SUCCESS = 0
    VALIDATION = 2
    FAILURE = 1


_EXIT_CODES = {
    ErrorType.VALIDATION: ExitCode.VALIDATION,
    ErrorType.CONFLICT: ExitCode.FAILURE,
    ErrorType.NOT_FOUND: ExitCode.FAILURE,
    ErrorType.UNAUTHORIZED: ExitCode.FAILURE,
    ErrorType.FORBIDDEN: ExitCode.FAILURE,
    ErrorType.EXTERNAL: ExitCode.FAILURE,
    ErrorType.UNEXPECTED: ExitCode.FAILURE,
}


def handle_exception(
    error: Exception,
    *,
    write: Callable[[str], None],
) -> ExitCode:
    """Presenta un error conocido y devuelve el código de salida CLI asociado."""
    if isinstance(error, AppException):
        write(error.message)
        return _EXIT_CODES.get(error.error_type, ExitCode.FAILURE)

    if isinstance(error, OSError):
        write("No se pudo acceder al directorio de trabajo o guardar el archivo")
        return ExitCode.FAILURE

    raise error
