from core.exceptions import AppException, ErrorType


class GrypeErrors:
    InvalidTimeout = AppException(
        "invalid_timeout",
        "El timeout debe ser mayor que cero",
        ErrorType.VALIDATION,
    )

    OrganizationRequired = AppException(
        "organization_required",
        "La organización es obligatoria",
        ErrorType.VALIDATION,
    )

    SbomDirectoryNotFound = AppException(
        "sbom_directory_not_found",
        "No existe el directorio de SBOMs",
        ErrorType.NOT_FOUND,
    )

    SbomRunNotFound = AppException(
        "sbom_run_not_found",
        "No se encontró la ejecución de SBOM indicada",
        ErrorType.NOT_FOUND,
    )

    SbomNotFound = AppException(
        "sbom_not_found",
        "El archivo SBOM no existe",
        ErrorType.NOT_FOUND,
    )

    InvalidSbomReport = AppException(
        "invalid_sbom_report",
        "No se pudo leer el reporte de SBOM",
        ErrorType.UNEXPECTED,
    )

    SbomGenerationFailed = AppException(
        "sbom_generation_failed",
        "El SBOM no pudo generarse",
        ErrorType.UNEXPECTED,
    )

    ResultAlreadyExists = AppException(
        "result_already_exists",
        "El archivo de resultados ya existe",
        ErrorType.CONFLICT,
    )

    GrypeNotAvailable = AppException(
        "grype_not_available",
        "No se encontró Grype o una ruta necesaria",
        ErrorType.UNEXPECTED,
    )

    VersionTimeout = AppException(
        "version_timeout",
        "Grype excedió el tiempo al obtener su versión",
        ErrorType.UNEXPECTED,
    )

    VersionFailed = AppException(
        "version_failed",
        "No se pudo obtener la versión de Grype",
        ErrorType.UNEXPECTED,
    )

    InvalidVersionResponse = AppException(
        "invalid_version_response",
        "Grype no devolvió su versión",
        ErrorType.UNEXPECTED,
    )

    ScanTimeout = AppException(
        "scan_timeout",
        "Se agotó el tiempo al buscar vulnerabilidades",
        ErrorType.UNEXPECTED,
    )

    ScanFailed = AppException(
        "scan_failed",
        "Grype no pudo completar el análisis",
        ErrorType.UNEXPECTED,
    )

    ResultsNotGenerated = AppException(
        "results_not_generated",
        "Grype terminó sin generar el archivo de resultados",
        ErrorType.UNEXPECTED,
    )

    GrypeAccessFailed = AppException(
        "grype_access_failed",
        "No se pudo ejecutar Grype o acceder a sus archivos",
        ErrorType.UNEXPECTED,
    )
