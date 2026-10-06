"""Neutral reference results lock the public v1 policy, not engine internals."""

from dataclasses import dataclass, replace
from decimal import Decimal, localcontext

import pytest

from repolens.application.scoring_policy import PYTHON_STATIC_V1
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
from repolens.domain.scoring import ScoreState, score_repository

SPECS = (
    AnalyzerSpec("quality", Category.CODE_QUALITY, "Controlled quality results"),
    AnalyzerSpec("testing", Category.TESTING, "Controlled testing results"),
    AnalyzerSpec("security", Category.SECURITY, "Controlled security results"),
    AnalyzerSpec("hygiene", Category.REPOSITORY_HYGIENE, "Controlled hygiene results"),
    AnalyzerSpec("ci", Category.CI_CD, "Controlled CI results"),
)


def observation(owner: AnalyzerSpec, rule: str, severity: Severity, index: int = 0) -> Finding:
    return Finding(
        f"{owner.identifier}:{rule}:{index}",
        rule,
        owner.category,
        severity,
        "Controlled observation",
        "Neutral calibration evidence, not a real repository assessment",
        (Evidence("Inert reference observation"),),
        "Review the observation",
        owner.identifier,
    )


def report(*findings: Finding) -> AnalysisReport:
    results = tuple(
        AnalyzerResult(
            owner,
            AnalyzerState.COMPLETED,
            tuple(item for item in findings if item.source_analyzer == owner.identifier),
        )
        for owner in SPECS
    )
    return AnalysisReport(Repository("neutral-reference"), SPECS, results, PYTHON_STATIC_V1)


@dataclass(frozen=True)
class Reference:
    name: str
    findings: tuple[Finding, ...]
    categories: tuple[int, ...]
    overall: str


REFERENCES = (
    Reference("clean-supported", (), (100, 100, 100, 100, 100), "100.00"),
    Reference(
        "info-only",
        (
            observation(SPECS[1], "TEST001", Severity.INFO),
            observation(SPECS[3], "RH001", Severity.INFO),
            observation(SPECS[4], "CI001", Severity.INFO),
        ),
        (100, 100, 100, 100, 100),
        "100.00",
    ),
    Reference(
        "one-low",
        (observation(SPECS[0], "PY001", Severity.LOW),),
        (95, 100, 100, 100, 100),
        "98.75",
    ),
    Reference(
        "distinct-low",
        tuple(observation(SPECS[0], rule, Severity.LOW) for rule in ("PY001", "PY002")),
        (90, 100, 100, 100, 100),
        "97.50",
    ),
    Reference(
        "twenty-occurrences",
        tuple(observation(SPECS[0], "PY001", Severity.LOW, i) for i in range(20)),
        (95, 100, 100, 100, 100),
        "98.75",
    ),
    Reference(
        "medium-security",
        (observation(SPECS[2], "BANDIT-B301", Severity.MEDIUM),),
        (100, 100, 85, 100, 100),
        "94.38",
    ),
    Reference(
        "high-security",
        (observation(SPECS[2], "BANDIT-B602", Severity.HIGH),),
        (100, 100, 70, 100, 100),
        "88.75",
    ),
    Reference(
        "serious-security-floor",
        tuple(observation(SPECS[2], f"BANDIT-B60{i}", Severity.HIGH) for i in range(1, 5)),
        (100, 100, 0, 100, 100),
        "62.50",
    ),
    Reference(
        "critical-floor",
        tuple(
            observation(SPECS[2], f"REFERENCE-CRITICAL-{i}", Severity.CRITICAL) for i in range(2)
        ),
        (100, 100, 0, 100, 100),
        "62.50",
    ),
    Reference(
        "mixed",
        (
            observation(SPECS[0], "PY001", Severity.LOW),
            observation(SPECS[0], "PY002", Severity.LOW),
            observation(SPECS[1], "TEST002", Severity.INFO),
            observation(SPECS[2], "BANDIT-B301", Severity.MEDIUM),
            observation(SPECS[2], "BANDIT-B602", Severity.HIGH),
            observation(SPECS[3], "RH002", Severity.LOW),
            observation(SPECS[4], "CI002", Severity.LOW),
            observation(SPECS[4], "CI003", Severity.LOW),
        ),
        (90, 100, 55, 95, 90),
        "78.75",
    ),
)


def test_v1_identifier_penalties_weights_and_scope_are_compatibility_goldens() -> None:
    assert PYTHON_STATIC_V1.identifier == "repolens-python-static-v1"
    assert tuple((p.severity, p.points) for p in PYTHON_STATIC_V1.penalties) == (
        (Severity.INFO, 0),
        (Severity.LOW, 5),
        (Severity.MEDIUM, 15),
        (Severity.HIGH, 30),
        (Severity.CRITICAL, 60),
    )
    assert tuple((w.category, w.weight) for w in PYTHON_STATIC_V1.weights) == (
        (Category.CODE_QUALITY, 2),
        (Category.TESTING, 1),
        (Category.SECURITY, 3),
        (Category.REPOSITORY_HYGIENE, 1),
        (Category.CI_CD, 1),
    )
    assert Category.DOCUMENTATION not in {c.category for c in report().score.categories}
    assert Category.MAINTAINABILITY not in {c.category for c in report().score.categories}


@pytest.mark.parametrize("reference", REFERENCES, ids=lambda reference: reference.name)
def test_reference_scores(reference: Reference) -> None:
    assessment = report(*reference.findings)
    assert tuple(c.value for c in assessment.score.categories) == reference.categories
    assert assessment.score.value == Decimal(reference.overall)
    assert assessment.score.value.as_tuple().exponent == -2
    assert all(c.state == ScoreState.ASSESSED for c in assessment.score.categories)
    assert assessment.findings == tuple(sorted(reference.findings, key=lambda f: f.identifier))


@pytest.mark.parametrize(
    "severity, category_value, overall",
    [
        (Severity.INFO, 100, "100.00"),
        (Severity.LOW, 95, "98.13"),
        (Severity.MEDIUM, 85, "94.38"),
        (Severity.HIGH, 70, "88.75"),
        (Severity.CRITICAL, 40, "77.50"),
    ],
)
def test_single_security_rule_sensitivity(
    severity: Severity, category_value: int, overall: str
) -> None:
    assessment = report(observation(SPECS[2], "REFERENCE-SENSITIVITY", severity))
    assert assessment.score.categories[2].value == category_value
    assert assessment.score.value == Decimal(overall)


@pytest.mark.parametrize(
    "owner, overall", [(SPECS[0], "98.75"), (SPECS[3], "99.38"), (SPECS[4], "99.38")]
)
def test_low_rule_impact_by_category(owner: AnalyzerSpec, overall: str) -> None:
    assert report(observation(owner, "REFERENCE-LOW", Severity.LOW)).score.value == Decimal(overall)


def test_repeated_bandit_rule_uses_highest_severity_and_retains_every_finding() -> None:
    findings = tuple(
        observation(SPECS[2], "BANDIT-B602", severity, i)
        for i, severity in enumerate((Severity.LOW, Severity.HIGH, Severity.MEDIUM) * 7)
    )
    assessment = report(*findings)
    deduction = assessment.score.categories[2].deductions[0]
    assert assessment.score.value == Decimal("88.75")
    assert deduction.severity == Severity.HIGH
    assert deduction.points == 30
    assert deduction.finding_ids == tuple(sorted(f.identifier for f in findings))
    assert len(assessment.findings) == 21


def test_info_findings_and_zero_point_records_remain_visible_at_100() -> None:
    assessment = report(*REFERENCES[1].findings)
    deductions = tuple(d for category in assessment.score.categories for d in category.deductions)
    assert {d.rule_id for d in deductions} == {"TEST001", "RH001", "CI001"}
    assert all(d.points == 0 for d in deductions)
    assert len(assessment.findings) == 3
    assert assessment.score.value == Decimal("100.00")


def test_saturation_preserves_raw_deductions() -> None:
    assessment = report(*REFERENCES[7].findings)
    security = assessment.score.categories[2]
    assert security.value == 0
    assert sum(d.points for d in security.deductions) == 120
    assert len(security.deductions) == 4


@pytest.mark.parametrize(
    "state", [AnalyzerState.FAILED, AnalyzerState.SKIPPED, AnalyzerState.UNSUPPORTED]
)
def test_unavailable_security_blocks_overall_without_losing_observed_deductions(
    state: AnalyzerState,
) -> None:
    assessment = report(observation(SPECS[2], "BANDIT-B602", Severity.HIGH))
    extra = AnalyzerSpec("additional-security", Category.SECURITY, "Additional declared work")
    result = AnalyzerResult(extra, state, reason="Controlled unavailable work")
    score = score_repository((*SPECS, extra), (*assessment.results, result), PYTHON_STATIC_V1)
    assert score.value is None
    assert score.categories[2].state == ScoreState.INCOMPLETE
    assert score.categories[2].value is None
    assert score.categories[2].deductions[0].points == 30
    assert score.categories[2].unavailable_analyzers == (extra.identifier,)


def test_missing_result_and_empty_or_partial_plan_never_default_to_100() -> None:
    assessment = report()
    missing = score_repository(
        SPECS, tuple(r for r in assessment.results if r.analyzer != SPECS[4]), PYTHON_STATIC_V1
    )
    assert missing.value is None
    assert missing.categories[-1].unavailable_analyzers == ("ci",)
    empty = score_repository((), (), PYTHON_STATIC_V1)
    assert empty.value is None
    assert all(c.state == ScoreState.INCOMPLETE and c.value is None for c in empty.categories)
    quality = next(r for r in assessment.results if r.analyzer == SPECS[0])
    partial = score_repository((SPECS[0],), (quality,), PYTHON_STATIC_V1)
    assert partial.value is None
    assert sum(c.state == ScoreState.INCOMPLETE for c in partial.categories) == 4


def test_non_applicable_weight_is_excluded_and_all_non_applicable_is_not_numeric() -> None:
    assessment = report(observation(SPECS[3], "RH002", Severity.LOW))
    outcomes = tuple(
        AnalyzerResult(r.analyzer, AnalyzerState.NOT_APPLICABLE, reason="Explicitly irrelevant")
        if r.analyzer.category == Category.TESTING
        else r
        for r in assessment.results
    )
    score = score_repository(SPECS, outcomes, PYTHON_STATIC_V1)
    assert score.value == Decimal("99.29")  # (200 + 300 + 95 + 100) / 7
    assert score.categories[1].state == ScoreState.NOT_APPLICABLE
    assert score.categories[1].value is None
    all_non_applicable = tuple(
        AnalyzerResult(owner, AnalyzerState.NOT_APPLICABLE, reason="Controlled irrelevant scope")
        for owner in SPECS
    )
    assert score_repository(SPECS, all_non_applicable, PYTHON_STATIC_V1).value is None


def test_completed_and_non_applicable_same_category_remains_assessed() -> None:
    extra = AnalyzerSpec("irrelevant-security", Category.SECURITY, "Explicit irrelevant work")
    result = AnalyzerResult(extra, AnalyzerState.NOT_APPLICABLE, reason="Controlled irrelevance")
    score = score_repository((*SPECS, extra), (*report().results, result), PYTHON_STATIC_V1)
    assert score.value == Decimal("100.00")
    assert score.categories[2].non_applicable_analyzers == (extra.identifier,)


def test_informational_testing_share_is_visible_without_claiming_test_effectiveness() -> None:
    assessment = report(*REFERENCES[9].findings)
    outcomes = tuple(
        AnalyzerResult(r.analyzer, AnalyzerState.NOT_APPLICABLE, reason="Controlled irrelevance")
        if r.analyzer.category == Category.TESTING
        else r
        for r in assessment.results
    )
    assert assessment.score.value == Decimal("78.75")
    assert score_repository(SPECS, outcomes, PYTHON_STATIC_V1).value == Decimal("75.71")


@pytest.mark.parametrize("precision", [1, 2, 28])
def test_actual_policy_half_up_rounding_and_order_are_context_independent(precision: int) -> None:
    findings = REFERENCES[5].findings
    assessment = report(*findings)
    with localcontext() as context:
        context.prec = precision
        reversed_score = score_repository(
            tuple(reversed(SPECS)),
            tuple(reversed(assessment.results)),
            replace(
                PYTHON_STATIC_V1,
                penalties=tuple(reversed(PYTHON_STATIC_V1.penalties)),
                weights=tuple(reversed(PYTHON_STATIC_V1.weights)),
            ),
        )
    assert reversed_score == assessment.score
    assert reversed_score.value == Decimal("94.38")  # Exact unrounded 94.375.


def test_out_of_scope_analyzer_is_rejected_rather_than_given_artificial_score() -> None:
    owner = AnalyzerSpec("not-shipped", Category.DOCUMENTATION, "Not implemented")
    with pytest.raises(ValueError, match="policy scope"):
        score_repository((*SPECS, owner), report().results, PYTHON_STATIC_V1)
