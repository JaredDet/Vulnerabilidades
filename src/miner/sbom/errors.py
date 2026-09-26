from core.exceptions import AppException, ErrorType


class SBOMErrors:
    InvalidTimeout = AppException(
        "invalid_timeout",
        "El timeout debe ser mayor que cero",
        ErrorType.VALIDATION,
    )

    SourceNotFound = AppException(
        "source_not_found",
        "La carpeta del repositorio no existe",
        ErrorType.NOT_FOUND,
    )

    SbomAlreadyExists = AppException(
        "sbom_already_exists",
        "El archivo SBOM ya existe",
        ErrorType.CONFLICT,
    )

    SbomInsideSource = AppException(
        "sbom_inside_source",
        "El SBOM debe quedar fuera de la carpeta del repositorio",
        ErrorType.VALIDATION,
    )

    SyftNotAvailable = AppException(
        "syft_not_available",
        "No se encontró Syft o una ruta necesaria",
        ErrorType.UNEXPECTED,
    )

    VersionTimeout = AppException(
        "version_timeout",
        "Se agotó el tiempo al consultar la versión de Syft",
        ErrorType.UNEXPECTED,
    )

    VersionFailed = AppException(
        "version_failed",
        "Syft no pudo obtener su versión",
        ErrorType.UNEXPECTED,
    )

    InvalidVersionResponse = AppException(
        "invalid_version_response",
        "Syft devolvió una versión con formato inválido",
        ErrorType.UNEXPECTED,
    )

    GenerationTimeout = AppException(
        "generation_timeout",
        "Se agotó el tiempo al generar el SBOM",
        ErrorType.UNEXPECTED,
    )

    GenerationFailed = AppException(
        "generation_failed",
        "Syft no pudo generar el SBOM",
        ErrorType.UNEXPECTED,
    )

    SbomNotGenerated = AppException(
        "sbom_not_generated",
        "Syft terminó sin generar el archivo SBOM",
        ErrorType.UNEXPECTED,
    )

    SyftAccessFailed = AppException(
        "syft_access_failed",
        "No se pudo ejecutar Syft o acceder a sus archivos",
        ErrorType.UNEXPECTED,
    )
