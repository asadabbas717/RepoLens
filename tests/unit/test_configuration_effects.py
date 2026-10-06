"""Selection never hides unavailable work; gates use active findings and impact order."""

from dataclasses import replace
from decimal import Decimal
from typing import cast
from unittest.mock import MagicMock

import pytest

from repolens.application.configuration import select_results
from repolens.application.gates import evaluate_gates
from repolens.application.scoring_policy import PYTHON_STATIC_V1
from repolens.cli import default_analyzer_plan
from repolens.domain.assessment_configuration import AppliedConfiguration, GateSettings
from repolens.domain.models import (
    AnalyzerResult,
    AnalyzerState,
    Evidence,
    Finding,
    Repository,
    Severity,
)
from repolens.domain.report import AnalysisReport


def reference(
    *, severity: Severity | None = None, state: AnalyzerState = AnalyzerState.COMPLETED
) -> AnalysisReport:
    plan = default_analyzer_plan(MagicMock())
    results: list[AnalyzerResult] = []
    for spec in plan.specs:
        findings: list[Finding] = []
        rule_severities = (
            (("REFERENCE", severity),)
            if severity is not None and spec.identifier == "python-static"
            else (("PY001", Severity.LOW), ("PY002", Severity.LOW))
            if severity is None and spec.identifier == "python-static"
            else (("BANDIT-B602", Severity.HIGH),)
            if severity is None and spec.identifier == "python-security"
            else (("RH001", Severity.INFO),)
            if severity is None and spec.identifier == "repository-hygiene"
            else ()
        )
        for rule, level in rule_severities:
            assert level is not None
            findings.append(
                Finding(
                    f"{spec.identifier}:{rule}",
                    rule,
                    spec.category,
                    level,
                    "Controlled",
                    "Reference observation",
                    (Evidence("Controlled evidence"),),
                    "Review",
                    spec.identifier,
                )
            )
        result_state = state if spec.identifier == "python-security" else AnalyzerState.COMPLETED
        results.append(
            AnalyzerResult(
                spec,
                result_state,
                tuple(findings) if result_state == AnalyzerState.COMPLETED else (),
                None if result_state == AnalyzerState.COMPLETED else "Controlled unavailable work",
            )
        )
    return AnalysisReport(Repository("reference"), plan.specs, tuple(results), PYTHON_STATIC_V1)


@pytest.mark.parametrize(
    "disabled, expected, remaining",
    [
        (("RH001",), "86.25", {"PY001", "PY002", "BANDIT-B602"}),
        (("PY002",), "87.50", {"RH001", "PY001", "BANDIT-B602"}),
        (("BANDIT-B602",), "97.50", {"RH001", "PY001", "PY002"}),
        (("PY001", "PY002"), "88.75", {"RH001", "BANDIT-B602"}),
    ],
)
def test_exact_suppression_changes_only_active_findings_and_expected_score(
    disabled: tuple[str, ...], expected: str, remaining: set[str]
) -> None:
    original = reference()
    selected = select_results(original.results, disabled)
    report = replace(
        original, results=selected, configuration=AppliedConfiguration(1, disabled_rules=disabled)
    )
    assert str(report.score.value) == expected
    assert {finding.rule_id for finding in report.findings} == remaining
    assert report.plan == original.plan
    assert tuple(r.state for r in selected) == tuple(r.state for r in original.results)
    assert len(original.findings) == 4
    assert select_results(original.results, ()) == original.results


@pytest.mark.parametrize(
    "state", [AnalyzerState.FAILED, AnalyzerState.SKIPPED, AnalyzerState.UNSUPPORTED]
)
def test_disabled_vendor_rule_does_not_hide_security_unavailability(state: AnalyzerState) -> None:
    original = reference(state=state)
    report = replace(
        original,
        results=select_results(original.results, ("BANDIT-B602",)),
        configuration=AppliedConfiguration(1, disabled_rules=("BANDIT-B602",)),
    )
    assert report.score.value is None
    assert (
        next(r for r in report.results if r.analyzer.identifier == "python-security").state == state
    )
    assert evaluate_gates(report, GateSettings(Decimal("0"), Severity.CRITICAL)).failed


def test_missing_results_remain_missing_and_cannot_be_selected_into_success() -> None:
    original = reference()
    results = tuple(r for r in original.results if r.analyzer.identifier != "python-security")
    report = replace(original, results=select_results(results, ("BANDIT-B602",)))
    assert report.score.value is None
    assert "python-security" in report.score.categories[2].unavailable_analyzers


@pytest.mark.parametrize("threshold", tuple(Severity))
@pytest.mark.parametrize("severity", tuple(Severity))
def test_severity_gate_uses_impact_order_including_info(
    severity: Severity, threshold: Severity
) -> None:
    report = reference(severity=severity)
    outcome = evaluate_gates(report, GateSettings(fail_on_severity=threshold))
    expected = tuple(Severity).index(severity) >= tuple(Severity).index(threshold)
    assert outcome.failed == expected
    assert outcome.severity == ("not met" if expected else "met")


def test_disabled_trigger_does_not_fail_severity_gate_and_gate_values_do_not_rescore() -> None:
    original = reference()
    assert evaluate_gates(original, GateSettings(fail_on_severity=Severity.HIGH)).failed
    report = replace(
        original,
        results=select_results(original.results, ("BANDIT-B602",)),
        configuration=AppliedConfiguration(1, disabled_rules=("BANDIT-B602",)),
    )
    score = report.score
    assert not evaluate_gates(report, GateSettings(Decimal("90"), Severity.HIGH)).failed
    assert evaluate_gates(report, GateSettings(Decimal("100"), Severity.CRITICAL)).failed
    assert report.score is score


def test_no_findings_and_non_applicable_work_do_not_trigger_severity_gate() -> None:
    original = reference()
    results = tuple(AnalyzerResult(r.analyzer, AnalyzerState.COMPLETED) for r in original.results)
    report = replace(original, results=results)
    assert not evaluate_gates(report, GateSettings(fail_on_severity=Severity.INFO)).failed
    results = tuple(
        AnalyzerResult(r.analyzer, AnalyzerState.NOT_APPLICABLE, reason="Controlled irrelevance")
        for r in results
    )
    assert evaluate_gates(
        replace(report, results=results), GateSettings(fail_on_severity=Severity.INFO)
    ).failed


def test_report_rejects_active_findings_contradicting_disabled_scope() -> None:
    with pytest.raises(ValueError, match="typed"):
        replace(reference(), configuration=cast(AppliedConfiguration, {}))
    with pytest.raises(ValueError, match="contradict"):
        replace(reference(), configuration=AppliedConfiguration(1, disabled_rules=("PY002",)))
