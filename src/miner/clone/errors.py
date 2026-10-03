from core.exceptions import AppException, ErrorType


class CloneErrors:
    OrganizationRequired = AppException(
        "organization_required",
        "La organización es obligatoria",
        ErrorType.VALIDATION,
    )

    TokenRequired = AppException(
        "token_required",
        "El token de GitHub es obligatorio",
        ErrorType.VALIDATION,
    )

    InvalidTimeout = AppException(
        "invalid_timeout",
        "El timeout debe ser mayor que cero",
        ErrorType.VALIDATION,
    )

    InvalidRepositoryName = AppException(
        "invalid_repository_name",
        "El nombre debe tener el formato organización/repositorio",
        ErrorType.VALIDATION,
    )

    DestinationOutsideRoot = AppException(
        "destination_outside_root",
        "La ruta del repositorio queda fuera del destino",
        ErrorType.VALIDATION,
    )

    DestinationAlreadyExists = AppException(
        "destination_already_exists",
        "El destino del repositorio ya existe",
        ErrorType.CONFLICT,
    )

    GitCloneTimeout = AppException(
        "git_clone_timeout",
        "La clonación superó el tiempo límite",
        ErrorType.UNEXPECTED,
    )

    GitCloneFailed = AppException(
        "git_clone_failed",
        "No se pudo clonar el repositorio; revisa Git, la URL y el acceso al destino",
        ErrorType.UNEXPECTED,
    )

    GitHubUnauthorized = AppException(
        "github_unauthorized",
        "GitHub rechazó el token; comprueba su validez y caducidad",
        ErrorType.UNAUTHORIZED,
    )

    GitHubForbidden = AppException(
        "github_forbidden",
        "GitHub denegó el acceso; revisa permisos y restricciones de la organización",
        ErrorType.FORBIDDEN,
    )

    GitHubNotFound = AppException(
        "github_not_found",
        "La organización no existe o no es visible con este token",
        ErrorType.NOT_FOUND,
    )

    GitHubRateLimit = AppException(
        "github_rate_limit",
        "Se alcanzó el límite de solicitudes de GitHub; intenta más tarde",
        ErrorType.UNEXPECTED,
    )

    GitHubRequestFailed = AppException(
        "github_request_failed",
        "No se pudo consultar GitHub; revisa la conexión e intenta nuevamente",
        ErrorType.UNEXPECTED,
    )

    CloneNotFound = AppException(
        "clone_not_found",
        "No hay clones disponibles. Ejecuta primero `miner clone-repositories`.",
        ErrorType.NOT_FOUND,
    )

    InvalidRunId = AppException(
        "invalid_run_id",
        "--run-id debe ser solo el identificador de la ejecución",
        ErrorType.VALIDATION,
    )

    RunNotFound = AppException(
        "run_not_found",
        "No se encontró la ejecución indicada",
        ErrorType.NOT_FOUND,
    )

    InvalidCloneManifest = AppException(
        "invalid_clone_manifest",
        "No se pudo leer el manifest de clonación",
        ErrorType.UNEXPECTED,
    )

    WrongOrganization = AppException(
        "wrong_organization",
        "La clonación seleccionada pertenece a otra organización",
        ErrorType.VALIDATION,
    )
