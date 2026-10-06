"""Compact controlled report values; all renderers receive the same domain report."""

import pytest

from repolens.domain.models import (
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
from repolens.domain.scoring import CategoryWeight, ScoringPolicy, SeverityPenalty


@pytest.fixture
def clean_report() -> AnalysisReport:
    owner = AnalyzerSpec("example", Category.TESTING, "Controlled analyzer")
    policy = ScoringPolicy(
        "fixture-v1",
        tuple(SeverityPenalty(s, p) for s, p in zip(Severity, (0, 5, 15, 30, 60), strict=True)),
        (CategoryWeight(Category.TESTING, 1),),
    )
    return AnalysisReport(
        Repository("fixture"), (owner,), (AnalyzerResult(owner, AnalyzerState.COMPLETED),), policy
    )


@pytest.fixture
def mixed_report(clean_report: AnalysisReport) -> AnalysisReport:
    testing = clean_report.plan[0]
    security = AnalyzerSpec("security", Category.SECURITY, "Controlled security")
    policy = ScoringPolicy(
        clean_report.policy.identifier,
        clean_report.policy.penalties,
        (CategoryWeight(Category.TESTING, 1), CategoryWeight(Category.SECURITY, 2)),
    )
    info = Finding(
        "info",
        "TEST001",
        Category.TESTING,
        Severity.INFO,
        "Test observation",
        "Discovery is uncertain",
        (Evidence("No conventional source observed"),),
        "Review discovery",
        testing.identifier,
    )
    high = Finding(
        "security:a",
        "BANDIT-B602",
        Category.SECURITY,
        Severity.HIGH,
        "Security observation",
        "A static pattern",
        (Evidence("Controlled evidence", "src/app.py", 3), Evidence("Related path", "src/peer.py")),
        "Review intended behavior",
        security.identifier,
    )
    medium = Finding(
        "security:b",
        "BANDIT-B301",
        Category.SECURITY,
        Severity.MEDIUM,
        "Other observation",
        "Another static pattern",
        (Evidence("Controlled evidence", "src/app.py", 5),),
        "Review the pattern",
        security.identifier,
    )
    return AnalysisReport(
        clean_report.repository,
        (security, testing),
        (
            AnalyzerResult(security, AnalyzerState.COMPLETED, (medium, high)),
            AnalyzerResult(testing, AnalyzerState.COMPLETED, (info,)),
        ),
        policy,
    )
