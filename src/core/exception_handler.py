"""Traduce excepciones de la aplicación a mensajes y códigos de salida CLI."""

from collections.abc import Callable
from enum import Enum

from core.exceptions import AppException, ErrorType


class ExitCode(Enum):
    SUCCESS = 0
    UNEXPECTED_ERROR = 1
    USAGE_ERROR = 2
    CONFLICT = 3
    NOT_FOUND = 4
    UNAUTHORIZED = 5
    FORBIDDEN = 6
    EXTERNAL_SERVICE_ERROR = 7
    FILESYSTEM_ERROR = 8


_EXIT_CODES = {
    ErrorType.VALIDATION: ExitCode.USAGE_ERROR,
    ErrorType.CONFLICT: ExitCode.CONFLICT,
    ErrorType.NOT_FOUND: ExitCode.NOT_FOUND,
    ErrorType.UNAUTHORIZED: ExitCode.UNAUTHORIZED,
    ErrorType.FORBIDDEN: ExitCode.FORBIDDEN,
    ErrorType.EXTERNAL: ExitCode.EXTERNAL_SERVICE_ERROR,
    ErrorType.UNEXPECTED: ExitCode.UNEXPECTED_ERROR,
}


def handle_exception(
    error: Exception,
    *,
    write: Callable[[str], None],
) -> ExitCode:
    """Presenta un error conocido y devuelve el código de salida CLI asociado."""
    if isinstance(error, AppException):
        write(error.message)
        return _EXIT_CODES.get(error.error_type, ExitCode.UNEXPECTED_ERROR)

    if isinstance(error, OSError):
        write("No se pudo acceder al directorio de trabajo o guardar el archivo")
        return ExitCode.FILESYSTEM_ERROR

    raise error
