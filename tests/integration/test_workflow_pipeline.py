"""Real owned acquisition/read boundaries and inert CI/report composition."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from yaml.constructor import UnsafeConstructor

from repolens.analyzers.ci_static import GitHubActionsAnalyzer
from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.domain.models import AnalyzerState, Category, Severity
from repolens.domain.report import AnalysisReport
from repolens.domain.scoring import CategoryWeight, ScoringPolicy, SeverityPenalty
from repolens.domain.workflow import (
    MAX_WORKFLOW_BYTES,
    MAX_WORKFLOW_FILES,
    MAX_WORKFLOW_TOTAL_BYTES,
)
from repolens.infrastructure import verified_read
from repolens.infrastructure import workflow as boundary
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.git import GitRunner
from repolens.infrastructure.repository_source import RepositoryLease, RepositorySource
from repolens.infrastructure.traversal import TraversalLimits

TEXT = (
    "on: push\npermissions: write-all\njobs:\n  build:\n    runs-on: ubuntu-latest\n"
    "    steps:\n      - uses: actions/checkout@v4\n"
    "      - run: touch executed-marker # secret-token\n"
)


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    assert GitRunner().run(("init", "--quiet"), tmp_path, 10).returncode == 0
    (tmp_path / ".github/workflows").mkdir(parents=True)
    return tmp_path


def policy() -> ScoringPolicy:
    return ScoringPolicy(
        "synthetic-ci-fixture",
        tuple(SeverityPenalty(s, i * 5) for i, s in enumerate(Severity)),
        (CategoryWeight(Category.CI_CD, 1),),
    )


def test_detached_pipeline_no_execution_or_network(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / ".github/workflows/build.yml").write_text(TEXT, encoding="utf-8")
    (repository / "script.py").write_text("raise RuntimeError('must not import')", encoding="utf-8")
    with RepositorySource().local(repository) as lease:
        context = boundary.snapshot_workflow_context(lease)
        identity = lease.identity
    plan = AnalyzerPlan([GitHubActionsAnalyzer()])
    forbidden = MagicMock(
        side_effect=AssertionError("No analyzer I/O, execution, construction or network")
    )
    with monkeypatch.context() as scope:
        scope.setattr(Path, "open", forbidden)
        scope.setattr(GitRunner, "run", forbidden)
        scope.setattr("subprocess.Popen", forbidden)
        scope.setattr("socket.create_connection", forbidden)
        scope.setattr("urllib.request.urlopen", forbidden)
        scope.setattr("importlib.import_module", forbidden)
        scope.setattr(UnsafeConstructor, "construct_python_object_apply", forbidden)
        results = execute_analyzers(plan, context)
        report = AnalysisReport(identity, plan.specs, results, policy())
    forbidden.assert_not_called()
    assert results[0].state == AnalyzerState.COMPLETED
    assert {f.rule_id for f in report.findings} == {"CI002", "CI003"}
    assert report.score.value is not None and report.score.categories[0].value == 90
    assert "secret-token" not in repr(context) + repr(report) + repr(results)
    assert str(repository) not in repr(report)
    assert not (repository / "executed-marker").exists()
    assert execute_analyzers(plan, context) == results


@pytest.mark.parametrize("raw", [TEXT.encode(), b"\xef\xbb\xbf" + TEXT.encode()])
def test_utf8_bom_and_multiple_workflows(repository: Path, raw: bytes) -> None:
    for name in ("b.yaml", "a.yml"):
        (repository / ".github/workflows" / name).write_bytes(raw)
    with RepositorySource().local(repository) as lease:
        context = boundary.snapshot_workflow_context(lease)
    assert context.workflows is not None
    assert tuple(f.path for f in context.workflows.files) == (
        ".github/workflows/a.yml",
        ".github/workflows/b.yaml",
    )
    assert all(f.text == TEXT for f in context.workflows.files)


def test_zero_workflows_and_near_matches_no_content_reads(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        ".github/workflows/build.yml.example",
        ".github/workflows/build.YML",
        ".github/workflows/nested/build.yml",
        "docs/.github/workflows/example.yml",
        ".github/WORKFLOWS/build.yml",
        ".github/workflow/build.yml",
    ):
        path = repository / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("secret malformed [", encoding="utf-8")
    forbidden = MagicMock(side_effect=AssertionError("Only selected workflows may be read"))
    monkeypatch.setattr(boundary, "_read_verified", forbidden)
    with RepositorySource().local(repository) as lease:
        context = boundary.snapshot_workflow_context(lease)
    forbidden.assert_not_called()
    result = GitHubActionsAnalyzer().analyze(context)
    assert result.state == AnalyzerState.COMPLETED
    assert tuple(f.rule_id for f in result.findings) == ("CI001",)


@pytest.mark.parametrize("budget", ["file", "count", "aggregate", "traversal"])
def test_admission_limits_precede_reads(
    repository: Path, budget: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    if budget in {"file", "traversal"}:
        (repository / ".github/workflows/a.yml").write_bytes(b"x" * (MAX_WORKFLOW_BYTES + 1))
    else:
        count = (
            MAX_WORKFLOW_FILES + 1
            if budget == "count"
            else MAX_WORKFLOW_TOTAL_BYTES // MAX_WORKFLOW_BYTES + 1
        )
        raw = b"" if budget == "count" else b"x" * MAX_WORKFLOW_BYTES
        for i in range(count):
            (repository / f".github/workflows/{i}.yml").write_bytes(raw)
    forbidden = MagicMock(side_effect=AssertionError("No reads before complete admission"))
    monkeypatch.setattr(boundary, "_read_verified", forbidden)
    limits = TraversalLimits(max_file_bytes=10) if budget == "traversal" else None
    with (
        RepositorySource().local(repository) as lease,
        pytest.raises(AcquisitionError, match="limit"),
    ):
        boundary.snapshot_workflow_context(lease, limits)
    forbidden.assert_not_called()


@pytest.mark.parametrize(
    "mode", ["os-error", "decode", "changed-size", "directory", "reparse", "escape"]
)
def test_read_failures_never_publish_partial_workflows(
    repository: Path, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / ".github/workflows/a.yml").write_text(TEXT, encoding="utf-8")
    target = repository / ".github/workflows/z.yml"
    target.write_bytes(b"bad" if mode != "decode" else b"\xff-secret")
    original = verified_read._read_verified
    calls = 0

    def read(lease: RepositoryLease, path: str, limit: int) -> bytes:
        nonlocal calls
        calls += 1
        if path.endswith("a.yml"):
            return original(lease, path, limit)
        if mode == "os-error":
            raise OSError("secret-os-path")
        if mode == "changed-size":
            return b"longer"
        if mode == "directory":
            target.unlink()
            target.mkdir()
        if mode == "reparse":
            with monkeypatch.context() as scope:
                scope.setattr(verified_read, "_link_or_reparse", lambda checked: checked == target)
                return original(lease, path, limit)
        if mode == "escape":
            # Use the real lexical/containment guard, not a weakened reader.
            return original(lease, "../outside.yml", limit)
        return original(lease, path, limit)

    monkeypatch.setattr(boundary, "_read_verified", read)
    with RepositorySource().local(repository) as lease, pytest.raises(AcquisitionError) as error:
        boundary.snapshot_workflow_context(lease)
    assert calls >= 1 and "secret" not in str(error.value)


def test_closed_lease_and_unsupported_yaml_cannot_score_perfectly(repository: Path) -> None:
    (repository / ".github/workflows/a.yml").write_text("secret: [", encoding="utf-8")
    with RepositorySource().local(repository) as lease:
        context = boundary.snapshot_workflow_context(lease)
    with pytest.raises(AcquisitionError, match="closed"):
        boundary.snapshot_workflow_context(lease)
    plan = AnalyzerPlan([GitHubActionsAnalyzer()])
    results = execute_analyzers(plan, context)
    report = AnalysisReport(context.repository, plan.specs, results, policy())
    assert results[0].state == AnalyzerState.UNSUPPORTED
    assert report.score.value is None and report.findings == ()


def test_object_tag_never_invokes_constructor_or_creates_marker(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = repository / "executed-marker"
    raw = '!!python/object/apply:os.system ["touch executed-marker"]'
    (repository / ".github/workflows/a.yml").write_text(raw, encoding="utf-8")
    with RepositorySource().local(repository) as lease:
        context = boundary.snapshot_workflow_context(lease)
    forbidden = MagicMock(side_effect=AssertionError("No object construction"))
    with monkeypatch.context() as scope:
        scope.setattr(UnsafeConstructor, "construct_python_object_apply", forbidden)
        result = GitHubActionsAnalyzer().analyze(context)
    assert result.state == AnalyzerState.UNSUPPORTED
    forbidden.assert_not_called()
    assert not marker.exists()
