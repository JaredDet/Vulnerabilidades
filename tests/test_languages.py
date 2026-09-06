import pytest

from languages import get_codeql_languages

AVAILABLE = {"cpp", "csharp", "go", "java", "javascript", "python", "ruby", "rust", "swift"}


@pytest.mark.parametrize("languages, expected", [
    ([], []),
    (["HTML", "CSS", "YAML"], []),
    (["Python", "HTML"], ["python"]),
    (["Java", "Kotlin"], ["java"]),
    (["JavaScript", "TypeScript", "JavaScript"], ["javascript"]),
    (["C", "C++"], ["cpp"]),
    (["Python", "Go", "C#"], ["csharp", "go", "python"]),
])
def test_select_languages(languages, expected):
    assert get_codeql_languages(languages, AVAILABLE) == expected


def test_order_is_stable():
    languages = ["Swift", "Ruby", "Rust", "Python"]
    assert get_codeql_languages(languages, AVAILABLE) == get_codeql_languages(reversed(languages), AVAILABLE)


def test_filters_unavailable():
    assert get_codeql_languages(["Python", "Java"], {"python"}) == ["python"]
    assert get_codeql_languages(["Python"], set()) == []


def test_auxiliary_extractors_are_excluded():
    auxiliary = {"csv", "html", "properties", "xml", "yaml"}
    assert get_codeql_languages([name.upper() for name in auxiliary], auxiliary) == []


def test_normalization_and_aliases():
    assert get_codeql_languages([" PYTHON ", "typescript", "C#"], AVAILABLE) == [
        "csharp", "javascript", "python"
    ]


def test_new_extractor_needs_no_name_mapping():
    assert get_codeql_languages(["ExampleLanguage"], {"examplelanguage"}) == ["examplelanguage"]
