import pytest

from core.exception_handler import ExitCode, handle_exception
from core.exceptions import AppException, ErrorType


@pytest.mark.parametrize(
    ("error_type", "expected_exit_code"),
    [
        (ErrorType.VALIDATION, ExitCode.VALIDATION),
        (ErrorType.CONFLICT, ExitCode.FAILURE),
        (ErrorType.NOT_FOUND, ExitCode.FAILURE),
        (ErrorType.UNAUTHORIZED, ExitCode.FAILURE),
        (ErrorType.FORBIDDEN, ExitCode.FAILURE),
        (ErrorType.EXTERNAL, ExitCode.FAILURE),
        (ErrorType.UNEXPECTED, ExitCode.FAILURE),
    ],
)
def test_handle_app_exception(error_type, expected_exit_code):
    messages = []
    error = AppException("sample_error", "Error de prueba", error_type)

    exit_code = handle_exception(error, write=messages.append)

    assert exit_code is expected_exit_code
    assert messages == ["Error de prueba"]


def test_handle_os_error():
    messages = []

    exit_code = handle_exception(OSError("disk error"), write=messages.append)

    assert exit_code is ExitCode.FAILURE
    assert messages == [
        "No se pudo acceder al directorio de trabajo o guardar el archivo"
    ]


def test_unknown_exception_is_reraised():
    error = RuntimeError("unexpected bug")

    with pytest.raises(RuntimeError) as raised:
        handle_exception(error, write=lambda _message: None)

    assert raised.value is error
