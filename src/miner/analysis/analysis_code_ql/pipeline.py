"""Coordina el análisis de repositorios con CodeQL."""

from collections.abc import Callable
from pathlib import Path
from tempfile import mkdtemp

from ...clone.models import OrganizationCloneResult, Repository
from .codeql import CodeQLError, analyze_database, create_database
from .models import LanguageResult, OrganizationResult, RepositoryResult
from .report import write_report
from .sarif import SarifError, parse_sarif


def _create_analysis_directory(
    workspace: Path,
) -> Path:
    """Crea el directorio para una ejecución de análisis."""
    analysis_root = (workspace / "analysis_results").resolve()
    analysis_root.mkdir(parents=True, exist_ok=True)

    return Path(
        mkdtemp(
            prefix="analysis-",
            dir=analysis_root,
        )
    ).resolve()


def _process_repositories(
    clones: OrganizationCloneResult,
    root: Path,
    token: str,
    executable: str,
    timeout: float,
    progress: Callable[[str], None],
) -> OrganizationResult:
    """Analiza los repositorios de la organización."""
    repositories = sorted(
        clones.repositories,
        key=lambda item: item.repository.full_name,
    )

    report = OrganizationResult(
        organization=clones.organization,
        repositories=[],
    )

    for index, item in enumerate(repositories, 1):
        repository = item.repository

        progress(f"[{index}/{len(repositories)}] Analizando {repository.full_name}")

        if item.source is None:
            result = RepositoryResult(
                name=repository.full_name,
                url=repository.clone_url.removesuffix(".git"),
                status="clone_failed",
                error=item.error,
            )
        else:
            result = analyze_repository(
                repository,
                item.source,
                root / repository.full_name.replace("/", "-"),
                token=token,
                executable=executable,
                timeout=timeout,
            )

        report.repositories.append(result)

        progress(f"  {result.status}" + (f": {result.error}" if result.error else ""))

    return report


def analyze_organization(
    clones: OrganizationCloneResult,
    output: Path,
    *,
    token: str,
    executable: str = "codeql",
    timeout: float = 600,
    progress: Callable[[str], None] = print,
) -> OrganizationResult:
    """Analiza clones preparados y escribe avances, sin consultar GitHub ni clonar."""
    if not token.strip() or timeout <= 0:
        raise ValueError("Se requiere GITHUB_TOKEN y timeout positivo")

    analysis_directory = _create_analysis_directory(
        clones.workspace,
    )

    report_path = analysis_directory / "codeql-results.json"

    report = _process_repositories(
        clones,
        analysis_directory,
        token,
        executable,
        timeout,
        progress,
    )

    write_report(report, report_path)
    write_report(report, output)

    return report


def _language_databases(database: Path) -> list[tuple[str, Path]]:
    """Devuelve las bases del clúster ordenadas por lenguaje."""
    databases = []

    for path in database.iterdir():
        if not path.is_dir():
            continue

        if not (path / "codeql-database.yml").is_file():
            continue

        databases.append((path.name, path))

    return sorted(databases, key=lambda item: item[0])


def _analyze_language(
    database: Path,
    language: str,
    root: Path,
    executable: str,
    timeout: float,
) -> LanguageResult:
    """Analiza una base CodeQL correspondiente a un lenguaje."""

    sarif = root / language / "results.sarif"

    try:
        analyze_database(
            database,
            language,
            sarif,
            executable=executable,
            timeout=timeout,
        )
    except CodeQLError as error:
        return LanguageResult(
            language=language,
            status="analysis_failed",
            error=str(error),
        )

    try:
        findings = parse_sarif(sarif)
    except SarifError as error:
        return LanguageResult(
            language=language,
            status="sarif_failed",
            error=str(error),
        )

    return LanguageResult(
        language=language,
        status="analyzed",
        findings=findings,
    )


def _analyze_repository(
    repository: Repository,
    source: Path,
    root: Path,
    token: str,
    executable: str,
    timeout: float,
) -> RepositoryResult:
    try:
        database = create_database(
            source,
            root / "database",
            token=token,
            executable=executable,
            timeout=timeout,
        )
    except CodeQLError as error:
        return RepositoryResult(
            name=repository.full_name,
            url=repository.clone_url.removesuffix(".git"),
            status="database_failed",
            error=str(error),
        )

    databases = _language_databases(database)

    if not databases:
        return RepositoryResult(
            name=repository.full_name,
            url=repository.clone_url.removesuffix(".git"),
            status="unsupported",
            error="CodeQL no creó ninguna base de datos",
        )

    languages = [
        _analyze_language(
            database_path,
            language,
            root,
            executable,
            timeout,
        )
        for language, database_path in databases
    ]

    if all(language.status == "analyzed" for language in languages):
        status = "analyzed"
        error = None
    elif any(language.status == "analyzed" for language in languages):
        status = "partial"
        error = "Uno o más lenguajes no pudieron analizarse"
    else:
        status = "analysis_failed"
        error = "No se pudo analizar ningún lenguaje"

    return RepositoryResult(
        name=repository.full_name,
        url=repository.clone_url.removesuffix(".git"),
        status=status,
        error=error,
        languages=languages,
    )


def analyze_repository(
    repository: Repository,
    source: Path,
    root: Path,
    token: str,
    executable: str = "codeql",
    timeout: float = 600,
) -> RepositoryResult:
    """Analiza un repositorio ya preparado y consolida sus hallazgos."""

    try:
        return _analyze_repository(
            repository,
            source,
            root,
            token,
            executable,
            timeout,
        )
    except Exception as error:  # noqa: BLE001
        return RepositoryResult(
            name=repository.full_name,
            url=repository.clone_url.removesuffix(".git"),
            status="failed",
            error=f"Error inesperado: {type(error).__name__}",
        )
