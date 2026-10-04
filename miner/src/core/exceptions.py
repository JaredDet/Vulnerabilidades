from enum import Enum


class ErrorType(Enum):
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    EXTERNAL = "external"
    UNEXPECTED = "unexpected"


class AppException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        error_type: ErrorType,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.error_type = error_type
