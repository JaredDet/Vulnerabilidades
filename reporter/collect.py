"""Recolecta evidencia de seguridad del repositorio sin usar el CLI del Miner."""

import argparse
import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

SCAN_TIMEOUT = 300
CODEQL_TIMEOUT = 600
VERSION_TIMEOUT = 30
SNIPPET_LINES = 8
SUMMARY_LIMIT = 500

EXCLUDED_PREFIXES = (
    "analyzer/data/",
    "analyzer/outputs/",
    "miner/organizations/",
)
EXCLUDED_DIRECTORIES = {
    "node_modules",
    "tests",
    ".git",
    ".angular",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
}
TEST_FILE = re.compile(r"(^|/)(test_.+\.py|.+_test\.py|.+\.spec\.ts)$")
SOURCE_SUFFIXES = {".py", ".ts", ".js", ".yml", ".yaml", ".sh"}

SECRET_NAMES = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "OPENAI_API_KEY",
    "CODEX_API_KEY",
    "ANTHROPIC_API_KEY",
)
HARDCODED_SECRET = re.compile(
    r"ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}",
)
SECRET_ASSIGNMENT = re.compile(
    r"""(?i)((?:token|secret|password|api_key|apikey)\s*[=:]\s*['\"])([^'\"]{12,})""",
)
ENV_READ = re.compile(
    r"os\.environ|os\.getenv|process\.env|secrets\.",
)
TOKEN_TO_CHILD = re.compile(
    r"(?:GITHUB_TOKEN_ENVIRONMENT_VARIABLE|GITHUB_TOKEN|GH_TOKEN)\s*:",
)
ACTION_USE = re.compile(r"uses:\s+([^\s@]+)@([^\s#]+)")
PINNED_SHA = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$", re.IGNORECASE)
PERMISSIONS_KEY = re.compile(r"^(\s*)permissions:\s*(.*?)\s*$")
WRITE_PERMISSION = re.compile(r"(?i)\bwrite(?:-all)?\b")

CODEQL_LANGUAGES = (
    ("python", ("miner", "analyzer")),
    ("javascript", ("visualizer",)),
)
SYFT_EXCLUDES = (
    "./analyzer/data/**",
    "./analyzer/outputs/**",
    "./miner/organizations/**",
    "./miner/tests/**",
    "./analyzer/tests/**",
    "**/node_modules/**",
    "**/.git/**",
)

def _run(command: list[str], *, timeout: float, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )


def _failure(error: Exception) -> str:
    if isinstance(error, subprocess.TimeoutExpired):
        return "timed out"
    if isinstance(error, FileNotFoundError):
        return "not installed"
    if isinstance(error, subprocess.CalledProcessError):
        return f"exit code {error.returncode}"
    return "failed"


def _tool_version(command: list[str]) -> tuple[str, str | None]:
    try:
        result = _run(command, timeout=VERSION_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as error:
        return "unknown", _failure(error)

    stdout = result.stdout.strip()
    try:
        version = json.loads(stdout).get("version")
        if isinstance(version, str) and version.strip():
            return version.strip(), None
    except json.JSONDecodeError:
        pass

    line = stdout.splitlines()[0].strip() if stdout else ""
    if not line:
        return "unknown", "version command returned no output"
    return line, None


def _relative(path: str, repo: Path) -> str:
    normalized = path.replace("\\", "/")
    repo_prefix = f"{repo.resolve().as_posix()}/"
    if normalized.startswith(repo_prefix):
        return normalized[len(repo_prefix):]
    if "/repo/" in normalized:
        return normalized.split("/repo/", 1)[1]
    if normalized.startswith("/"):
        parts = Path(normalized).parts
        for index in range(1, len(parts)):
            candidate = "/".join(parts[index:])
            if (repo / candidate).exists():
                return candidate
    return normalized.lstrip("./")


ANALYZE_SEVERITIES = {"critical", "high", "medium", "error", "warning"}


def _excluded(relative: str) -> bool:
    if relative.startswith(".github/workflows/") and relative.endswith(".lock.yml"):
        return True
    if relative.startswith(EXCLUDED_PREFIXES) or relative == "miner/.env.example":
        return True
    parts = Path(relative).parts
    if any(part in EXCLUDED_DIRECTORIES for part in parts):
        return True
    return TEST_FILE.search(relative) is not None


def _component(relative: str) -> str:
    if relative.startswith("miner/") or relative == "miner":
        return "miner"
    if relative.startswith("analyzer/") or relative == "analyzer":
        return "analyzer"
    if relative.startswith("visualizer/") or relative == "visualizer":
        return "visualizer"
    if relative.startswith(".github/"):
        return "workflows"
    return "repository"


def _redact(text: str) -> str:
    text = HARDCODED_SECRET.sub("[REDACTED]", text)
    return SECRET_ASSIGNMENT.sub(r"\1[REDACTED]", text)


def _read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return []


def _snippet(lines: list[str], start_line: int, end_line: int | None) -> dict | None:
    if not lines or start_line < 1:
        return None

    if end_line is None:
        start = max(1, start_line - 2)
        end = min(len(lines), start_line + 2)
    else:
        start = start_line
        end = min(len(lines), end_line)

    end = min(end, start + SNIPPET_LINES - 1)
    if start > len(lines):
        return None

    text = "\n".join(_redact(line) for line in lines[start - 1:end])
    return {"start_line": start, "end_line": end, "text": text}


def _finding(
    *,
    source: str,
    identifier: str,
    severity: str,
    severity_kind: str,
    summary: str,
    component: str,
    file: str,
    start_line: int | None = None,
    excerpt: str | None = None,
    snippet: dict | None = None,
    scores: list[dict] | None = None,
    package: str | None = None,
    version: str | None = None,
    package_type: str | None = None,
    manifest: str | None = None,
) -> dict:
    return {
        "source": source,
        "identifier": identifier,
        "severity": severity,
        "severity_kind": severity_kind,
        "scores": scores or [],
        "summary": summary[:SUMMARY_LIMIT],
        "package": package,
        "version": version,
        "package_type": package_type,
        "manifest": manifest,
        "location": {"file": file, "start_line": start_line},
        "excerpt": excerpt,
        "snippet": snippet,
        "component": component,
    }


def _group_findings(findings: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    order: list[tuple] = []
    for finding in _assign_ids(findings):
        key = (finding["source"], finding["identifier"], finding["severity"])
        if key not in grouped:
            grouped[key] = {
                "source": finding["source"],
                "identifier": finding["identifier"],
                "severity": finding["severity"],
                "severity_kind": finding["severity_kind"],
                "summary": finding["summary"],
                "analyze": finding["severity"].lower() in ANALYZE_SEVERITIES,
                "findings": [],
            }
            order.append(key)
        grouped[key]["findings"].append({
            "id": finding["id"],
            "scores": finding["scores"],
            "package": finding["package"],
            "version": finding["version"],
            "package_type": finding["package_type"],
            "manifest": finding["manifest"],
            "component": finding["component"],
            "location": finding["location"],
            "excerpt": finding["excerpt"],
            "snippet": finding["snippet"],
        })
    return [grouped[key] for key in order]


def _assign_ids(findings: list[dict]) -> list[dict]:
    findings.sort(key=lambda item: (
        item["source"],
        item["location"]["file"] or "",
        item["location"]["start_line"] or 0,
        item["identifier"],
        item["package"] or "",
        item["version"] or "",
    ))
    for index, finding in enumerate(findings, start=1):
        finding["id"] = f"F{index:03d}"
    return findings


def _commit(repo: Path) -> str:
    result = _run(
        ["git", "-c", f"safe.directory={repo.resolve()}", "-C", str(repo), "rev-parse", "HEAD"],
        timeout=VERSION_TIMEOUT,
    )
    commit = result.stdout.strip()
    if not commit:
        raise RuntimeError("git rev-parse returned no commit")
    return commit


def _scan_syft(repo: Path, sbom_path: Path) -> tuple[str, str | None]:
    version, version_error = _tool_version(["syft", "version", "--output", "json"])
    if version_error == "not installed":
        return version, version_error

    command = ["syft", "scan", f"dir:{repo.resolve()}", "--output", f"cyclonedx-json={sbom_path}"]
    for pattern in SYFT_EXCLUDES:
        command.extend(["--exclude", pattern])

    try:
        _run(command, timeout=SCAN_TIMEOUT)
    except (OSError, subprocess.SubprocessError) as error:
        return version, _failure(error)

    if not sbom_path.is_file():
        return version, "sbom was not created"
    return version, None


def _scan_grype(repo: Path, sbom_path: Path, output_path: Path) -> tuple[str, str | None, list[dict]]:
    version, version_error = _tool_version(["grype", "version"])
    if version_error == "not installed":
        return version, version_error, []
    if not sbom_path.is_file():
        return version, "sbom is missing", []

    try:
        _run(
            ["grype", f"sbom:{sbom_path}", "--output", "json", "--file", str(output_path)],
            timeout=SCAN_TIMEOUT,
        )
        data = json.loads(output_path.read_text(encoding="utf-8"))
        matches = data["matches"]
        if not isinstance(matches, list):
            raise ValueError("matches must be a list")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        return version, _failure(error) if not isinstance(error, ValueError | KeyError | TypeError | json.JSONDecodeError) else "invalid grype json", []

    findings = []
    seen = set()
    for match in matches:
        vulnerability = match.get("vulnerability") or {}
        artifact = match.get("artifact") or {}
        identifier = vulnerability.get("id")
        package = artifact.get("name")
        package_version = artifact.get("version")
        if not identifier or not package or package_version is None:
            continue

        locations = artifact.get("locations") or []
        manifests = []
        for location in locations:
            if isinstance(location, dict) and location.get("path"):
                relative = _relative(str(location["path"]), repo)
                if not _excluded(relative):
                    manifests.append(relative)
        manifest = manifests[0] if manifests else None
        if manifest is None:
            continue

        key = (identifier, package, str(package_version), manifest)
        if key in seen:
            continue
        seen.add(key)

        scores = []
        for cvss in vulnerability.get("cvss") or []:
            value = (cvss.get("metrics") or {}).get("baseScore")
            if isinstance(value, bool) or not isinstance(value, int | float):
                continue
            scores.append({
                "system": "CVSS",
                "value": float(value),
                "vector": cvss.get("vector"),
            })

        findings.append(_finding(
            source="grype",
            identifier=str(identifier),
            severity=str(vulnerability.get("severity") or "Unknown"),
            severity_kind="cvss",
            summary=str(vulnerability.get("description") or identifier),
            component=_component(manifest),
            file=manifest,
            scores=scores,
            package=str(package),
            version=str(package_version),
            package_type=artifact.get("type"),
            manifest=manifest,
        ))
    return version, None, findings


def _sarif_text(message: object) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        text = message.get("text") or message.get("markdown") or ""
        return str(text)
    return ""


def _parse_sarif(sarif_path: Path, repo: Path) -> list[dict]:
    data = json.loads(sarif_path.read_text(encoding="utf-8-sig"))
    findings = []
    for run in data.get("runs") or []:
        if any(invocation.get("executionSuccessful") is False for invocation in run.get("invocations") or []):
            raise ValueError("codeql execution failed")

        rules = (run.get("tool") or {}).get("driver", {}).get("rules") or []
        for result in run.get("results") or []:
            rule_index = result.get("ruleIndex")
            rule = rules[rule_index] if isinstance(rule_index, int) and 0 <= rule_index < len(rules) else {}
            identifier = result.get("ruleId") or rule.get("id")
            if not identifier:
                continue

            locations = result.get("locations") or []
            physical = locations[0].get("physicalLocation", {}) if locations else {}
            artifact = physical.get("artifactLocation") or {}
            uri = artifact.get("uri")
            if not uri:
                continue
            relative = _relative(str(uri), repo)
            if _excluded(relative) or not (repo / relative).is_file():
                continue

            region = physical.get("region") or {}
            start_line = region.get("startLine")
            end_line = region.get("endLine")
            if not isinstance(start_line, int):
                start_line = None
            if not isinstance(end_line, int):
                end_line = None

            file_path = repo / relative
            lines = _read_lines(file_path)
            snippet = _snippet(lines, start_line, end_line) if start_line else None
            excerpt = _redact(lines[start_line - 1]) if start_line and start_line <= len(lines) else None
            severity = result.get("level") or (rule.get("defaultConfiguration") or {}).get("level") or "note"
            score = (rule.get("properties") or {}).get("security-severity")
            scores = []
            if isinstance(score, int | float) and not isinstance(score, bool):
                scores.append({"system": "security-severity", "value": float(score), "vector": None})

            findings.append(_finding(
                source="codeql",
                identifier=str(identifier),
                severity=str(severity),
                severity_kind="sarif_level",
                summary=_sarif_text(result.get("message")),
                component=_component(relative),
                file=relative,
                start_line=start_line,
                excerpt=excerpt,
                snippet=snippet,
                scores=scores,
            ))
    return findings


def _stage_codeql_sources(repo: Path, stage: Path) -> dict[str, bool]:
    present = {"miner": False, "analyzer": False, "visualizer": False}
    copies = (
        (repo / "miner" / "src", stage / "miner" / "src", "miner"),
        (repo / "analyzer" / "scripts", stage / "analyzer" / "scripts", "analyzer"),
        (repo / "analyzer" / "notebooks", stage / "analyzer" / "notebooks", "analyzer"),
        (repo / "visualizer" / "src", stage / "visualizer" / "src", "visualizer"),
    )
    for source, target, component in copies:
        if not source.is_dir():
            continue
        shutil.copytree(
            source,
            target,
            ignore=shutil.ignore_patterns("*.spec.ts", "test_*.py", "*_test.py"),
        )
        present[component] = True

    analyzer = repo / "analyzer"
    if analyzer.is_dir():
        for path in analyzer.glob("*.py"):
            target = stage / "analyzer" / path.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
            present["analyzer"] = True
    return present


def _scan_codeql(repo: Path, work: Path) -> tuple[str, str | None, dict[str, str], list[dict]]:
    version, version_error = _tool_version(["codeql", "version", "--format=terse"])
    coverage = {component: "not_run" for _, components in CODEQL_LANGUAGES for component in components}
    if version_error == "not installed":
        return version, version_error, {name: "failed" for name in coverage}, []

    stage = work / "sources"
    present = _stage_codeql_sources(repo, stage)
    for component, included in present.items():
        if not included:
            coverage[component] = "not_applicable"

    errors = []
    findings = []
    for language, components in CODEQL_LANGUAGES:
        included = [component for component in components if present[component]]
        if not included:
            continue

        database = work / f"codeql-{language}"
        sarif = work / f"{language}.sarif"
        suite = f"codeql/{language}-queries:codeql-suites/{language}-code-scanning.qls"
        try:
            _run(
                [
                    "codeql", "database", "create", str(database),
                    f"--language={language}",
                    "--build-mode=none",
                    f"--source-root={stage.resolve()}",
                ],
                timeout=CODEQL_TIMEOUT,
            )
            _run(
                [
                    "codeql", "database", "analyze", str(database), suite,
                    "--format=sarifv2.1.0",
                    f"--output={sarif}",
                ],
                timeout=CODEQL_TIMEOUT,
            )
            findings.extend(_parse_sarif(sarif, repo))
            for component in included:
                coverage[component] = "analyzed"
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as error:
            for component in included:
                coverage[component] = "failed"
            reason = "invalid sarif" if isinstance(error, ValueError | json.JSONDecodeError) else _failure(error)
            errors.append(f"{language}: {reason}")

    return version, "; ".join(errors) or None, coverage, findings


def _iter_sources(repo: Path):
    for directory, dirnames, filenames in os.walk(repo):
        relative_dir = Path(directory).relative_to(repo).as_posix()
        if relative_dir == ".":
            relative_dir = ""
        dirnames[:] = [
            name for name in dirnames
            if name not in EXCLUDED_DIRECTORIES
            and not _excluded(f"{relative_dir}/{name}".lstrip("/") + "/placeholder")
            and f"{relative_dir}/{name}".lstrip("/") not in {"analyzer/data", "analyzer/outputs", "miner/organizations"}
        ]
        for filename in filenames:
            path = Path(directory) / filename
            relative = path.relative_to(repo).as_posix()
            if _excluded(relative):
                continue
            workflow_markdown = relative.startswith(".github/workflows/") and path.suffix.lower() == ".md"
            if path.suffix.lower() in SOURCE_SUFFIXES or path.name == "Dockerfile" or workflow_markdown:
                yield path, relative


def _permission_blocks(lines: list[str]) -> list[tuple[int, list[tuple[int, str]]]]:
    blocks = []
    for index, line in enumerate(lines):
        match = PERMISSIONS_KEY.match(line)
        if not match:
            continue
        indent = len(match.group(1))
        inline = match.group(2)
        values = [(index + 1, inline)] if inline else []
        if not inline:
            for later_index in range(index + 1, len(lines)):
                later = lines[later_index]
                if not later.strip():
                    continue
                later_indent = len(later) - len(later.lstrip(" "))
                if later_indent <= indent:
                    break
                values.append((later_index + 1, later.strip()))
        blocks.append((index + 1, values))
    return blocks


def _config_findings(repo: Path) -> tuple[list[dict], list[dict], list[dict]]:
    secrets: list[dict] = []
    tokens: list[dict] = []
    workflows: list[dict] = []
    for path, relative in _iter_sources(repo):
        workflow = relative.startswith(".github/workflows/")
        lines = _read_lines(path)
        component = _component(relative)

        if workflow:
            blocks = _permission_blocks(lines)
            if not blocks:
                tokens.append(_finding(
                    source="github-token-auditor",
                    identifier="workflow-permissions-missing",
                    severity="medium",
                    severity_kind="rule",
                    summary="El workflow no declara permissions.",
                    component="workflows",
                    file=relative,
                    start_line=1,
                    excerpt=_redact(lines[0]) if lines else None,
                    snippet=_snippet(lines, 1, None),
                ))
            for _, values in blocks:
                write_values = [(line_number, value) for line_number, value in values if WRITE_PERMISSION.search(value)]
                if not write_values:
                    continue
                line_number, value = write_values[0]
                tokens.append(_finding(
                    source="github-token-auditor",
                    identifier="workflow-permissions-write",
                    severity="medium",
                    severity_kind="rule",
                    summary=f"El workflow concede un permiso de escritura: {value}",
                    component="workflows",
                    file=relative,
                    start_line=line_number,
                    excerpt=_redact(lines[line_number - 1]),
                    snippet=_snippet(lines, line_number, None),
                ))

            for line_number, line in enumerate(lines, start=1):
                match = ACTION_USE.search(line)
                if not match or match.group(1).startswith("./"):
                    continue
                if PINNED_SHA.fullmatch(match.group(2)):
                    continue
                workflows.append(_finding(
                    source="workflow-analyzer",
                    identifier="action-not-pinned-by-sha",
                    severity="medium",
                    severity_kind="rule",
                    summary="La action está fijada por tag, no por SHA.",
                    component="workflows",
                    file=relative,
                    start_line=line_number,
                    excerpt=_redact(line),
                    snippet=_snippet(lines, line_number, None),
                    package=match.group(1),
                    version=match.group(2),
                ))

        if path.name == "Dockerfile":
            run_start = None
            run_lines: list[str] = []
            for line_number, line in enumerate(lines, start=1):
                stripped = line.strip()
                if run_start is None and not stripped.startswith("RUN "):
                    continue
                if run_start is None:
                    run_start = line_number
                run_lines.append(stripped.removeprefix("RUN ").removesuffix("\\").strip())
                if stripped.endswith("\\"):
                    continue
                instruction = " ".join(run_lines)
                if re.search(r"\b(curl|wget)\b", instruction) and re.search(r"\|\s*tar\b", instruction):
                    workflows.append(_finding(
                        source="workflow-analyzer",
                        identifier="remote-archive-extracted",
                        severity="medium",
                        severity_kind="rule",
                        summary="Un RUN descarga un archivo remoto y lo extrae con tar.",
                        component=component,
                        file=relative,
                        start_line=run_start,
                        excerpt=_redact(lines[run_start - 1]),
                        snippet=_snippet(lines, run_start, line_number),
                    ))
                run_start = None
                run_lines = []

        for line_number, line in enumerate(lines, start=1):
            if HARDCODED_SECRET.search(line) or (
                SECRET_ASSIGNMENT.search(line) and "[REDACTED]" not in line
            ):
                redacted = _redact(line)
                if redacted == line and not HARDCODED_SECRET.search(line):
                    continue
                window = lines[:]
                window[line_number - 1] = redacted
                secrets.append(_finding(
                    source="secret-scanner",
                    identifier="hardcoded-secret",
                    severity="high",
                    severity_kind="rule",
                    summary="Hay un secreto embebido en el archivo.",
                    component=component,
                    file=relative,
                    start_line=line_number,
                    excerpt=redacted.strip(),
                    snippet=_snippet(window, line_number, None),
                ))
                continue

            if TOKEN_TO_CHILD.search(line) and "environ.get" not in line and "getenv" not in line:
                tokens.append(_finding(
                    source="github-token-auditor",
                    identifier="token-passed-to-process",
                    severity="medium",
                    severity_kind="rule",
                    summary="El token se pasa al entorno de un proceso hijo.",
                    component=component,
                    file=relative,
                    start_line=line_number,
                    excerpt=_redact(line).strip(),
                    snippet=_snippet(lines, line_number, None),
                ))
                continue

            if ENV_READ.search(line) and any(name in line for name in SECRET_NAMES):
                secrets.append(_finding(
                    source="secret-scanner",
                    identifier="secret-env-read",
                    severity="low",
                    severity_kind="rule",
                    summary="El código lee un secreto desde el entorno.",
                    component=component,
                    file=relative,
                    start_line=line_number,
                    excerpt=_redact(line).strip(),
                    snippet=_snippet(lines, line_number, None),
                ))
    return secrets, tokens, workflows


def _tool(name: str, version: str, status: str, error: str | None) -> dict:
    return {
        "name": name,
        "version": version,
        "status": status,
        "error": error,
    }


def collect(repo: Path) -> dict:
    repo = repo.resolve()
    commit = _commit(repo)
    work = Path(tempfile.mkdtemp(prefix="reporter-"))
    try:
        sbom_path = work / "sbom.json"
        grype_path = work / "grype.json"
        syft_version, syft_error = _scan_syft(repo, sbom_path)
        grype_version, grype_error, grype_findings = _scan_grype(repo, sbom_path, grype_path)
        codeql_version, codeql_error, codeql_coverage, codeql_findings = _scan_codeql(repo, work)
        secret_findings: list[dict] = []
        token_findings: list[dict] = []
        workflow_findings: list[dict] = []
        secret_error = token_error = workflow_error = None
        try:
            secret_findings, token_findings, workflow_findings = _config_findings(repo)
        except (OSError, UnicodeError) as error:
            secret_error = token_error = workflow_error = _failure(error)

        sbom_ok = syft_error is None
        return {
            "schema_version": "2.0",
            "repository": os.environ.get("GITHUB_REPOSITORY", "local"),
            "commit": commit,
            "analyzed_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tools": [
                _tool("codeql", codeql_version, "failed" if codeql_error else "analyzed", codeql_error),
                _tool("syft", syft_version, "failed" if syft_error else "analyzed", syft_error),
                _tool("grype", grype_version, "failed" if grype_error else "analyzed", grype_error),
                _tool("secret-scanner", "1", "failed" if secret_error else "analyzed", secret_error),
                _tool("github-token-auditor", "1", "failed" if token_error else "analyzed", token_error),
                _tool("workflow-analyzer", "1", "failed" if workflow_error else "analyzed", workflow_error),
            ],
            "coverage": [
                {"component": "miner", "codeql": codeql_coverage.get("miner", "not_run"), "sbom": sbom_ok},
                {"component": "analyzer", "codeql": codeql_coverage.get("analyzer", "not_run"), "sbom": sbom_ok},
                {"component": "visualizer", "codeql": codeql_coverage.get("visualizer", "not_run"), "sbom": sbom_ok},
                {"component": "workflows", "codeql": "not_applicable", "sbom": False},
            ],
            "groups": _group_findings([
                *codeql_findings,
                *grype_findings,
                *secret_findings,
                *token_findings,
                *workflow_findings,
            ]),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Recolecta evidencia de seguridad del repositorio.")
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    evidence = collect(args.repo)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
