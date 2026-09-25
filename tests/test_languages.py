from miner.analysis.analysis_code_ql.pipeline import _language_databases


def test_language_databases_sorted_and_filtered(tmp_path):
    for language in ["python", "javascript"]:
        database = tmp_path / language
        database.mkdir()
        (database / "codeql-database.yml").touch()
    (tmp_path / "log").mkdir()
    (tmp_path / "codeql-database.yml").touch()
    assert _language_databases(tmp_path) == [
        ("javascript", tmp_path / "javascript"),
        ("python", tmp_path / "python"),
    ]


def test_empty_cluster(tmp_path):
    assert _language_databases(tmp_path) == []
