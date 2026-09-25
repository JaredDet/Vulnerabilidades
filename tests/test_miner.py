import json
from unittest.mock import Mock

import pytest

from miner.clone import pipeline as miner
from miner.analysis.analysis_code_ql import pipeline as analysis
from miner.analysis.analysis_code_ql.codeql import CodeQLError
from miner.analysis.analysis_code_ql.sarif import SarifError
from miner.clone.clone import CloneError
from miner.clone.github_api import GitHubAPIError
from miner.clone.models import Repository
from miner.analysis.analysis_code_ql.models import Finding


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr(
        miner,
        "get_organization_repositories",
        Mock(
            return_value=[
                Repository(full_name="org/b", clone_url="https://github.com/org/b.git"),
                Repository(full_name="org/a", clone_url="https://github.com/org/a.git"),
            ]
        ),
    )
    monkeypatch.setattr(miner, "clone_repository", Mock(return_value=tmp_path))
    database = tmp_path / "database"
    (database / "python").mkdir(parents=True)
    (database / "python" / "codeql-database.yml").touch()
    monkeypatch.setattr(analysis, "create_database", Mock(return_value=database))
    monkeypatch.setattr(
        analysis, "analyze_database", Mock(return_value=tmp_path / "output.sarif")
    )
    monkeypatch.setattr(
        analysis,
        "parse_sarif",
        Mock(return_value=[Finding(rule_id="py/a", message="Example")]),
    )
    def run():
        clones = miner.clone_organization(
            "org", "test-token", workspace=tmp_path / "work", progress=lambda _: None,
        )
        return analysis.analyze_organization(
            clones, tmp_path / "results.json", token="test-token", progress=lambda _: None,
        )

    return run


def test_complete_pipeline(pipeline, tmp_path):
    result = pipeline()
    assert result.summary.analyzed == 2
    assert result.summary.findings == 2
    data = json.loads((tmp_path / "results.json").read_text())
    assert [repo["name"] for repo in data["repositories"]] == ["org/a", "org/b"]
    assert data["summary"]["findings"] == 2
    miner.clone_repository.assert_called()
    assert miner.clone_repository.call_args.kwargs["token"] == "test-token"


@pytest.mark.parametrize(
    "component,error,status",
    [
        ("clone_repository", CloneError("clone"), "clone_failed"),
        ("create_database", CodeQLError("database"), "database_failed"),
        ("analyze_database", CodeQLError("analysis"), "analysis_failed"),
        ("parse_sarif", SarifError("sarif"), "analysis_failed"),
    ],
)
def test_continue_after_failure(pipeline, component, error, status):
    function = getattr(miner if component == "clone_repository" else analysis, component)
    function.side_effect = [error, function.return_value]
    result = pipeline()
    assert [repo.status for repo in result.repositories] == [status, "analyzed"]
    assert result.summary.failed == 1


def test_partial_languages(pipeline):
    database = analysis.create_database.return_value
    (database / "javascript").mkdir()
    (database / "javascript" / "codeql-database.yml").touch()
    analysis.analyze_database.side_effect = [
        CodeQLError("bad"), analysis.analyze_database.return_value,
    ] * 2
    result = pipeline()
    assert result.summary.partial == 2
    assert [(item.language, item.status) for item in result.repositories[0].languages] == [
        ("javascript", "analysis_failed"), ("python", "analyzed"),
    ]
    assert result.summary.findings == 2


def test_unsupported(pipeline):
    (analysis.create_database.return_value / "python" / "codeql-database.yml").unlink()
    assert pipeline().summary.unsupported == 2
    analysis.analyze_database.assert_not_called()


def test_empty_organization(pipeline, tmp_path):
    miner.get_organization_repositories.return_value = []
    result = pipeline()
    assert result.summary.repositories == 0
    assert json.loads((tmp_path / "results.json").read_text())["repositories"] == []


def test_failed_list_does_not_replace_report(pipeline, tmp_path):
    output = tmp_path / "results.json"
    output.write_text("existing report")
    miner.get_organization_repositories.side_effect = GitHubAPIError("failed page")
    with pytest.raises(GitHubAPIError):
        pipeline()
    assert output.read_text() == "existing report"


def test_scan_parses_sarif_and_writes_language_results(pipeline, monkeypatch):
    from miner.analysis.analysis_code_ql.sarif import parse_sarif

    monkeypatch.setattr(analysis, "parse_sarif", parse_sarif)

    def analyze(database, language, output, **kwargs):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "version": "2.1.0",
            "runs": [{"results": [{
                "ruleId": "py/example", "message": {"text": "Example finding"},
            }]}],
        }), encoding="utf-8")
        return output

    analysis.analyze_database.side_effect = analyze
    result = pipeline()
    assert result.summary.analyzed == 2
    assert result.summary.findings == 2
    language = result.repositories[0].languages[0]
    assert language.language == "python"
    assert language.findings[0].rule_id == "py/example"


def test_sarif_failure_preserves_language_status(pipeline):
    analysis.parse_sarif.side_effect = SarifError("invalid SARIF")
    result = pipeline()
    assert result.summary.failed == 2
    assert result.repositories[0].languages[0].status == "sarif_failed"


def test_unexpected_failure_continues_to_next_repository(pipeline):
    analysis.create_database.side_effect = [
        RuntimeError("private details"), analysis.create_database.return_value,
    ]
    result = pipeline()
    assert [repo.status for repo in result.repositories] == ["failed", "analyzed"]
    assert result.repositories[0].error == "Error inesperado: RuntimeError"


def test_clones_can_be_reused_without_cloning_again(pipeline, tmp_path):
    clones = miner.clone_organization(
        "org", "test-token", workspace=tmp_path / "work", progress=lambda _: None,
    )
    assert clones.cloned == 2
    assert clones.failed == 0
    assert clones.workspace.is_absolute()
    analysis.create_database.assert_not_called()
    miner.clone_repository.reset_mock()
    miner.get_organization_repositories.reset_mock()

    for name in ["first.json", "second.json"]:
        result = analysis.analyze_organization(
            clones, tmp_path / name, token="test-token", progress=lambda _: None,
        )
        assert result.summary.analyzed == 2

    miner.clone_repository.assert_not_called()
    miner.get_organization_repositories.assert_not_called()
    paths = [call.args[1] for call in analysis.create_database.call_args_list]
    assert paths[0] != paths[2]


def test_clone_failure_is_available_without_analysis(pipeline, tmp_path):
    miner.clone_repository.side_effect = [CloneError("clone failed"), tmp_path]
    clones = miner.clone_organization(
        "org", "test-token", workspace=tmp_path / "work", progress=lambda _: None,
    )
    assert clones.cloned == 1
    assert clones.failed == 1
    assert clones.repositories[0].repository.full_name == "org/a"
    assert clones.repositories[0].source is None
    assert clones.repositories[0].error == "clone failed"
    assert clones.repositories[1].source == tmp_path
    analysis.create_database.assert_not_called()
