"""Compose real domain reports and acquired identity without target execution."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerResult,
    AnalyzerSpec,
    AnalyzerState,
    Category,
    Evidence,
    Finding,
    Repository,
    Severity,
)
from repolens.domain.report import AnalysisReport
from repolens.domain.scoring import CategoryWeight, ScoreState, ScoringPolicy, SeverityPenalty
from repolens.infrastructure.git import GitRunner
from repolens.infrastructure.repository_source import RepositorySource


def synthetic_policy() -> ScoringPolicy:
    return ScoringPolicy(
        "synthetic-orchestration-fixture",
        tuple(SeverityPenalty(severity, index * 5) for index, severity in enumerate(Severity)),
        (CategoryWeight(Category.TESTING, 1),),
    )


class ControlledAnalyzer:
    def __init__(self, identifier: str, state: AnalyzerState) -> None:
        self.spec = AnalyzerSpec(identifier, Category.TESTING, "Controlled fixture")
        self.state = state

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        if self.state == AnalyzerState.FAILED:
            raise OSError("secret diagnostics")
        if self.state != AnalyzerState.COMPLETED:
            return AnalyzerResult(self.spec, self.state, reason="Controlled outcome")
        return AnalyzerResult(
            self.spec,
            self.state,
            (
                Finding(
                    self.spec.identifier + "-finding",
                    "TEST001",
                    Category.TESTING,
                    Severity.LOW,
                    "Fixture",
                    "Controlled observation",
                    (Evidence("Redacted"),),
                    "Review fixture",
                    self.spec.identifier,
                ),
            ),
        )


@pytest.mark.parametrize(
    "unavailable", [AnalyzerState.FAILED, AnalyzerState.SKIPPED, AnalyzerState.UNSUPPORTED]
)
def test_unavailable_execution_cannot_produce_false_perfect_report(
    unavailable: AnalyzerState,
) -> None:
    plan = AnalyzerPlan(
        [
            ControlledAnalyzer("completed", AnalyzerState.COMPLETED),
            ControlledAnalyzer("unavailable", unavailable),
        ]
    )
    context = AnalysisContext(Repository("fixture"))
    report = AnalysisReport(
        context.repository, plan.specs, execute_analyzers(plan, context), synthetic_policy()
    )
    assert report.score.value is None
    assert report.score.categories[0].state == ScoreState.INCOMPLETE
    assert report.score.categories[0].unavailable_analyzers == ("unavailable",)
    assert len(report.findings) == 1


def test_non_applicable_outcome_stays_distinct_from_unavailable_work() -> None:
    context = AnalysisContext(Repository("fixture"))
    plan = AnalyzerPlan([ControlledAnalyzer("not-applicable", AnalyzerState.NOT_APPLICABLE)])
    report = AnalysisReport(
        context.repository, plan.specs, execute_analyzers(plan, context), synthetic_policy()
    )
    assert report.score.value is None
    assert report.score.categories[0].state == ScoreState.NOT_APPLICABLE


def test_acquired_identity_composes_without_engine_io_or_target_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert GitRunner().run(("init", "--quiet"), tmp_path, 10).returncode == 0
    marker = tmp_path / "executed"
    (tmp_path / "target.py").write_text(
        "from pathlib import Path\nPath(__file__).with_name('executed').touch()\n",
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text("invalid target configuration", encoding="utf-8")
    forbidden = MagicMock(side_effect=AssertionError("Orchestration must not perform I/O"))
    with RepositorySource().local(tmp_path) as lease:
        context = AnalysisContext(lease.identity)
        plan = AnalyzerPlan([ControlledAnalyzer("fixture", AnalyzerState.COMPLETED)])
        with monkeypatch.context() as scope:
            scope.setattr(GitRunner, "run", forbidden)
            scope.setattr(RepositorySource, "local", forbidden)
            scope.setattr(RepositorySource, "github", forbidden)
            scope.setattr("repolens.infrastructure.traversal.repository_files", forbidden)
            scope.setattr("subprocess.Popen", forbidden)
            report = AnalysisReport(
                lease.identity, plan.specs, execute_analyzers(plan, context), synthetic_policy()
            )
        forbidden.assert_not_called()
        assert report.repository == lease.identity
        assert report.score.categories[0].value == 95
        assert not marker.exists()
    assert tmp_path.exists()


def test_empty_run_preserves_unavailable_policy_scope() -> None:
    plan = AnalyzerPlan(())
    context = AnalysisContext(Repository("fixture"))
    report = AnalysisReport(
        context.repository, plan.specs, execute_analyzers(plan, context), synthetic_policy()
    )
    assert report.score.value is None
    assert report.score.categories[0].state == ScoreState.INCOMPLETE
