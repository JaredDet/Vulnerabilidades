"""Selecciona lenguajes candidatos para CodeQL a partir de nombres de GitHub."""

from collections.abc import Iterable


# https://docs.github.com/en/code-security/reference/code-scanning/workflow-configuration-options
# Equivalencias de nombres; la disponibilidad se obtiene del CLI.
CODEQL_LANGUAGE_ALIASES: dict[str, str] = {
    "c": "cpp",
    "c++": "cpp",
    "c#": "csharp",
    "kotlin": "java",
    "typescript": "javascript",
}

# Extractores auxiliares, sin análisis de seguridad independiente en este flujo.
AUXILIARY_EXTRACTORS = frozenset({"csv", "html", "properties", "xml", "yaml"})


def get_codeql_languages(
    languages: Iterable[str], available_languages: Iterable[str]
) -> list[str]:
    """Devuelve identificadores únicos y ordenados; [] si no hay coincidencias.

    Recibe nombres de lenguajes de GitHub, no inspecciona archivos ni consulta
    la API. No garantiza que la base de datos pueda crearse. YAML no implica
    GitHub Actions, por lo que no se convierte automáticamente a actions.
    """
    available = set(available_languages) - AUXILIARY_EXTRACTORS
    normalized = (language.strip().lower() for language in languages)
    candidates = {CODEQL_LANGUAGE_ALIASES.get(name, name) for name in normalized}
    return sorted(candidates & available)
