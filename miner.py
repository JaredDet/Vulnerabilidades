"""Coordina el procesamiento independiente de repositorios y lenguajes."""

from collections.abc import Callable
from pathlib import Path
from tempfile import mkdtemp

from clone import CloneError, clone_repository
from codeql import CodeQLError, analyze_database, create_database, get_available_languages
from github_api import GitHubAPIError, get_organization_repositories, get_repository_languages
from languages import get_codeql_languages
from models import LanguageResult, OrganizationResult, Repository, RepositoryResult
from report import write_report
from sarif import SarifError, parse_sarif


def _analyze_language(source: Path, language: str, root: Path, executable: str,
                      timeout: float) -> LanguageResult:
    try:
        database = create_database(source, language, root / "databases" / language,
                                   executable=executable, timeout=timeout)
    except CodeQLError as error:
        return LanguageResult(language=language, status="database_failed", error=str(error))
    try:
        sarif = analyze_database(database, language, root / "sarif" / f"{language}.sarif",
                                 executable=executable, timeout=timeout)
    except CodeQLError as error:
        return LanguageResult(language=language, status="analysis_failed", error=str(error))
    try:
        return LanguageResult(language=language, status="analyzed", findings=parse_sarif(sarif))
    except SarifError as error:
        return LanguageResult(language=language, status="sarif_failed", error=str(error))


def _process_repository(repository: Repository, token: str, root: Path,
                        available: set[str], executable: str, timeout: float) -> RepositoryResult:
    result = RepositoryResult(name=repository.full_name, url=repository.clone_url.removesuffix(".git"),
                              status="failed")
    try:
        source = clone_repository(repository, root / "repositories", token=token)
    except CloneError as error:
        result.status, result.error = "clone_failed", str(error)
        return result
    try:
        result.detected_languages = get_repository_languages(repository.full_name, token)
    except GitHubAPIError as error:
        result.status, result.error = "language_detection_failed", str(error)
        return result
    selected = get_codeql_languages(result.detected_languages, available)
    if not selected:
        result.status = "unsupported"
        result.error = "Sin lenguajes compatibles con los extractores instalados para este análisis"
        return result
    for language in selected:
        try:
            analysis = _analyze_language(source, language, root / "analysis" / repository.full_name,
                                         executable, timeout)
        except Exception as error:
            # Aislamiento final: no volcar contenido arbitrario de excepciones o secretos.
            analysis = LanguageResult(language=language, status="failed",
                                      error=f"Error inesperado: {type(error).__name__}")
        result.analyses.append(analysis)
    result.languages = [a.language for a in result.analyses if a.status == "analyzed"]
    result.findings = [f for a in result.analyses for f in a.findings]
    failures = [a for a in result.analyses if a.status != "analyzed"]
    result.status = "analyzed" if not failures else ("partial" if result.languages else failures[0].status)
    result.error = "; ".join(f"{a.language}: {a.error}" for a in failures) or None
    return result


def scan_organization(organization: str, token: str, output: Path, *,
                      workspace: Path = Path("work"), executable: str = "codeql",
                      timeout: float = 600, progress: Callable[[str], None] = print) -> OrganizationResult:
    if not organization.strip() or not token.strip() or timeout <= 0:
        raise ValueError("Se requiere organización, GITHUB_TOKEN y timeout positivo")
    available = get_available_languages(executable)
    if not available:
        raise CodeQLError("CodeQL no tiene extractores disponibles")
    repositories = get_organization_repositories(organization, token)
    workspace.mkdir(parents=True, exist_ok=True)
    root = Path(mkdtemp(prefix="scan-", dir=workspace)).resolve()
    report = OrganizationResult(organization=organization.strip(), repositories=[])
    for index, repository in enumerate(sorted(repositories, key=lambda r: r.full_name), 1):
        progress(f"[{index}/{len(repositories)}] {repository.full_name}")
        try:
            result = _process_repository(repository, token, root, available, executable, timeout)
        except Exception as error:
            result = RepositoryResult(name=repository.full_name, url=repository.clone_url,
                                      status="failed", error=f"Error inesperado: {type(error).__name__}")
        report.repositories.append(result)
        progress(f"  {result.status}" + (f": {result.error}" if result.error else ""))
        write_report(report, output)
    write_report(report, output)
    return report
