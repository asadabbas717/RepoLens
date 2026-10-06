"""Owned acquisition through detached testing/report composition, without execution."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.analyzers.testing_static import TestingStaticAnalyzer
from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.domain.models import AnalyzerState, Category, Severity
from repolens.domain.report import AnalysisReport
from repolens.domain.scoring import CategoryWeight, ScoringPolicy, SeverityPenalty
from repolens.infrastructure import python_source as boundary
from repolens.infrastructure.git import GitRunner
from repolens.infrastructure.python_source import snapshot_python_context
from repolens.infrastructure.repository_source import RepositorySource


@pytest.mark.parametrize("candidate", [False, True])
def test_acquired_detached_pipeline(
    candidate: bool, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert GitRunner().run(("init", "--quiet"), tmp_path, 10).returncode == 0
    marker = tmp_path / "executed"
    hostile = (
        "from pathlib import Path\nPath(__file__).with_name('executed').touch()\n"
        "raise RuntimeError('fixture-secret')\n"
    )
    for name in ("app.py", "conftest.py", "noxfile.py"):
        (tmp_path / name).write_text(hostile, encoding="utf-8")
    if candidate:
        (tmp_path / "test_api.py").write_text(hostile, encoding="utf-8")
    # These filenames/content do not establish testing configuration.
    for name in (
        "pytest.ini",
        "pytest.ini.example",
        "pyproject.toml",
        "tox.ini",
        "setup.cfg",
        ".coveragerc",
    ):
        (tmp_path / name).write_text("malformed [ secret=credential", encoding="utf-8")
    with RepositorySource().local(tmp_path) as lease:
        context = snapshot_python_context(lease)
        identity = lease.identity
    plan = AnalyzerPlan([TestingStaticAnalyzer()])
    forbidden = MagicMock(
        side_effect=AssertionError("Detached analysis must not perform I/O or imports")
    )
    policy = ScoringPolicy(
        "synthetic-testing-fixture",
        tuple(SeverityPenalty(s, i * 5) for i, s in enumerate(Severity)),
        (CategoryWeight(Category.TESTING, 1),),
    )
    with monkeypatch.context() as scope:
        scope.setattr(boundary, "_read_source", forbidden)
        scope.setattr(Path, "open", forbidden)
        scope.setattr(GitRunner, "run", forbidden)
        scope.setattr("subprocess.Popen", forbidden)
        scope.setattr("importlib.import_module", forbidden)
        results = execute_analyzers(plan, context)
        report = AnalysisReport(identity, plan.specs, results, policy)
    forbidden.assert_not_called()
    assert results[0].state == AnalyzerState.COMPLETED
    assert tuple(f.rule_id for f in report.findings) == (
        ("TEST002",) if candidate else ("TEST001",)
    )
    assert report.score.categories[0].value == 100  # INFO contributes zero by domain contract.
    assert "fixture-secret" not in repr(report) and "credential" not in repr(report)
    assert not marker.exists()
    assert execute_analyzers(plan, context) == results


@pytest.mark.parametrize("available", [False, True])
def test_unavailable_testing_cannot_score_perfectly(available: bool) -> None:
    from repolens.domain.models import AnalysisContext, FileInventory, Repository
    from repolens.domain.python_source import PythonSourceFile, PythonSourceSnapshot

    context = AnalysisContext(Repository("fixture"))
    if available:
        context = AnalysisContext(
            context.repository,
            FileInventory(("test_a.py",)),
            PythonSourceSnapshot((PythonSourceFile("test_a.py", "def secret(:"),)),
        )
    plan = AnalyzerPlan([TestingStaticAnalyzer()])
    results = execute_analyzers(plan, context)
    policy = ScoringPolicy(
        "synthetic-unavailable-testing",
        tuple(SeverityPenalty(s, i * 5) for i, s in enumerate(Severity)),
        (CategoryWeight(Category.TESTING, 1),),
    )
    report = AnalysisReport(context.repository, plan.specs, results, policy)
    assert results[0].state == (AnalyzerState.UNSUPPORTED if available else AnalyzerState.FAILED)
    assert report.score.value is None
    assert report.score.categories[0].value is None
    assert report.findings == ()
