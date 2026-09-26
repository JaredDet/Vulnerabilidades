from core.exceptions import AppException, ErrorType


class CodeQLErrors:
    InvalidTimeout = AppException(
        "invalid_timeout",
        "El timeout debe ser mayor que cero",
        ErrorType.VALIDATION,
    )

    InvalidLanguage = AppException(
        "invalid_language",
        "Debes indicar un identificador de lenguaje CodeQL válido",
        ErrorType.VALIDATION,
    )

    SourceNotFound = AppException(
        "source_not_found",
        "La carpeta de código fuente no existe",
        ErrorType.NOT_FOUND,
    )

    DatabaseInsideSource = AppException(
        "database_inside_source",
        "La base debe quedar fuera de la carpeta de código fuente",
        ErrorType.VALIDATION,
    )

    DatabaseNotFound = AppException(
        "database_not_found",
        "No se encontró una base de datos CodeQL en la ruta indicada",
        ErrorType.NOT_FOUND,
    )

    SarifAlreadyExists = AppException(
        "sarif_already_exists",
        "El archivo de resultados ya existe",
        ErrorType.CONFLICT,
    )

    SarifInsideDatabase = AppException(
        "sarif_inside_database",
        "El SARIF debe quedar fuera de la base de datos",
        ErrorType.VALIDATION,
    )

    CodeQLNotAvailable = AppException(
        "codeql_not_available",
        "No se encontró CodeQL o una ruta necesaria",
        ErrorType.UNEXPECTED,
    )

    DatabaseCreationTimeout = AppException(
        "database_creation_timeout",
        "Se agotó el tiempo al crear las bases de datos CodeQL",
        ErrorType.UNEXPECTED,
    )

    DatabaseCreationFailed = AppException(
        "database_creation_failed",
        "CodeQL no pudo crear las bases de datos",
        ErrorType.UNEXPECTED,
    )

    AnalysisTimeout = AppException(
        "analysis_timeout",
        "Se agotó el tiempo al ejecutar las consultas CodeQL",
        ErrorType.UNEXPECTED,
    )

    AnalysisFailed = AppException(
        "analysis_failed",
        "El análisis CodeQL falló",
        ErrorType.UNEXPECTED,
    )

    SarifNotGenerated = AppException(
        "sarif_not_generated",
        "CodeQL terminó sin generar el archivo SARIF",
        ErrorType.UNEXPECTED,
    )

    CodeQLAccessFailed = AppException(
        "codeql_access_failed",
        "No se pudo ejecutar CodeQL o acceder a sus archivos",
        ErrorType.UNEXPECTED,
    )


class SarifErrors:
    InvalidIndex = AppException(
        "invalid_index",
        "El SARIF contiene un índice inválido",
        ErrorType.VALIDATION,
    )

    RuleMismatch = AppException(
        "rule_mismatch",
        "La regla del hallazgo no coincide con su índice",
        ErrorType.VALIDATION,
    )

    InvalidJson = AppException(
        "invalid_json",
        "No se pudo leer el SARIF como JSON UTF-8",
        ErrorType.UNEXPECTED,
    )

    InvalidDocument = AppException(
        "invalid_document",
        "Se esperaba un SARIF 2.1.0 con una lista de runs",
        ErrorType.VALIDATION,
    )

    AnalysisFailed = AppException(
        "analysis_failed",
        "El SARIF indica que la ejecución del análisis falló",
        ErrorType.UNEXPECTED,
    )

    InvalidResults = AppException(
        "invalid_results",
        "El SARIF contiene resultados inválidos",
        ErrorType.VALIDATION,
    )

    InvalidStructure = AppException(
        "invalid_structure",
        "El SARIF contiene un hallazgo o estructura inválida",
        ErrorType.VALIDATION,
    )
