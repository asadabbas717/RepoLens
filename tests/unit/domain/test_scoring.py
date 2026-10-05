"""Synthetic policies verify arithmetic; their numbers are not product defaults."""

from dataclasses import replace
from decimal import Decimal, localcontext
from itertools import permutations
from typing import cast

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
from repolens.domain.scoring import (
    CategoryWeight,
    ScoreState,
    ScoringPolicy,
    SeverityPenalty,
    score_repository,
)


def policy(*categories: Category) -> ScoringPolicy:
    return ScoringPolicy(
        "synthetic-test-policy",
        tuple(
            SeverityPenalty(severity, points)
            for severity, points in zip(Severity, (0, 5, 10, 25, 50), strict=True)
        ),
        tuple(CategoryWeight(category, 1) for category in categories),
    )


def spec(identifier: str = "example", category: Category = Category.TESTING) -> AnalyzerSpec:
    return AnalyzerSpec(identifier, category, "Synthetic analyzer metadata")


def finding(
    identifier: str = "f1",
    severity: Severity = Severity.MEDIUM,
    rule: str = "EXAMPLE001",
    analyzer: AnalyzerSpec | None = None,
) -> Finding:
    owner = analyzer or spec()
    return Finding(
        identifier,
        rule,
        owner.category,
        severity,
        "Synthetic finding",
        "Test observation",
        (Evidence("Synthetic evidence"),),
        "Review observation",
        owner.identifier,
    )


@pytest.mark.parametrize(
    "severity, expected",
    [
        (Severity.INFO, 100),
        (Severity.LOW, 95),
        (Severity.MEDIUM, 90),
        (Severity.HIGH, 75),
        (Severity.CRITICAL, 50),
    ],
)
def test_category_score_is_traceable_to_policy_and_evidence(
    severity: Severity,
    expected: int,
) -> None:
    score = score_repository(
        (spec(),),
        (AnalyzerResult(spec(), AnalyzerState.COMPLETED, (finding(severity=severity),)),),
        policy(Category.TESTING),
    )
    assert score.value == Decimal(expected)
    assert score.categories[0].value == expected
    assert score.categories[0].deductions[0].finding_ids == ("f1",)
    assert score.categories[0].deductions[0].points == 100 - expected


def test_repeated_rule_occurrences_deduct_once_at_highest_severity() -> None:
    observations = (
        finding("a", Severity.LOW),
        finding("b", Severity.CRITICAL),
        finding("c", Severity.MEDIUM),
    )
    for order in permutations(observations):
        score = score_repository(
            (spec(),),
            (AnalyzerResult(spec(), AnalyzerState.COMPLETED, order),),
            policy(Category.TESTING),
        )
        assert score.value == Decimal("50.00")
        deduction = score.categories[0].deductions[0]
        assert deduction.severity == Severity.CRITICAL
        assert deduction.finding_ids == ("a", "b", "c")


def test_distinct_rules_accumulate_and_category_penalty_is_capped_at_100() -> None:
    score = score_repository(
        (spec(),),
        (
            AnalyzerResult(
                spec(),
                AnalyzerState.COMPLETED,
                tuple(finding(str(index), Severity.CRITICAL, f"RULE{index}") for index in range(3)),
            ),
        ),
        policy(Category.TESTING),
    )
    assert score.value == Decimal("0.00")
    assert sum(item.points for item in score.categories[0].deductions) == 150


@pytest.mark.parametrize(
    "state",
    [
        AnalyzerState.FAILED,
        AnalyzerState.SKIPPED,
        AnalyzerState.UNSUPPORTED,
    ],
)
def test_unavailable_analyzers_block_scores_even_with_other_completed_work(
    state: AnalyzerState,
) -> None:
    second = spec("second")
    score = score_repository(
        (spec(), second),
        (
            AnalyzerResult(spec(), AnalyzerState.COMPLETED, (finding(),)),
            AnalyzerResult(second, state, reason="Unavailable for a specific reason"),
        ),
        policy(Category.TESTING),
    )
    assert score.value is None
    category = score.categories[0]
    assert category.state == ScoreState.INCOMPLETE
    assert category.value is None
    assert category.unavailable_analyzers == ("second",)
    assert category.completed_analyzers == ("example",)
    assert category.deductions[0].points == 10


def test_missing_results_and_unplanned_categories_never_become_perfect_scores() -> None:
    score = score_repository((spec(),), (), policy(Category.TESTING, Category.SECURITY))
    assert score.value is None
    assert all(item.state == ScoreState.INCOMPLETE for item in score.categories)
    assert score.categories[0].unavailable_analyzers == ("example",)
    assert score.categories[1].unavailable_analyzers == ()
    assert score_repository((), (), policy(Category.TESTING)).value is None


def test_all_nonapplicable_work_has_no_score() -> None:
    score = score_repository(
        (spec(),),
        (AnalyzerResult(spec(), AnalyzerState.NOT_APPLICABLE, reason="Outside project context"),),
        policy(Category.TESTING),
    )
    assert score.value is None
    assert score.categories[0].value is None
    assert score.categories[0].state == ScoreState.NOT_APPLICABLE
    assert score.categories[0].non_applicable_analyzers == ("example",)


def test_nonapplicable_work_is_excluded_without_blocking_completed_work() -> None:
    second = spec("second", Category.SECURITY)
    score = score_repository(
        (spec(), second),
        (
            AnalyzerResult(spec(), AnalyzerState.COMPLETED),
            AnalyzerResult(second, AnalyzerState.NOT_APPLICABLE, reason="Explicitly irrelevant"),
        ),
        policy(Category.TESTING, Category.SECURITY),
    )
    assert score.value == Decimal("100.00")
    third = spec("third")
    mixed = score_repository(
        (spec(), third),
        (
            AnalyzerResult(spec(), AnalyzerState.COMPLETED),
            AnalyzerResult(third, AnalyzerState.NOT_APPLICABLE, reason="Explicitly irrelevant"),
        ),
        policy(Category.TESTING),
    )
    assert mixed.categories[0].value == 100


@pytest.mark.parametrize(
    "weight, expected",
    [
        (2, "83.33"),
        (7, "93.75"),
        (31, "98.44"),
        (9999, "100.00"),
    ],
)
def test_weighted_mean_uses_exact_half_up_rounding_independent_of_decimal_context(
    weight: int,
    expected: str,
) -> None:
    second = spec("second", Category.SECURITY)
    custom = replace(
        policy(Category.TESTING, Category.SECURITY),
        weights=(
            CategoryWeight(Category.TESTING, weight),
            CategoryWeight(Category.SECURITY, 1),
        ),
    )
    with localcontext() as context:
        context.prec = 2
        score = score_repository(
            (spec(), second),
            (
                AnalyzerResult(spec(), AnalyzerState.COMPLETED),
                AnalyzerResult(
                    second,
                    AnalyzerState.COMPLETED,
                    (finding(severity=Severity.CRITICAL, analyzer=second),),
                ),
            ),
            custom,
        )
    assert score.value == Decimal(expected)


def test_reports_derive_scores_and_order_findings_without_rendering() -> None:
    first, second = spec(), spec("second")
    results = (
        AnalyzerResult(second, AnalyzerState.COMPLETED, (finding("b", analyzer=second),)),
        AnalyzerResult(first, AnalyzerState.COMPLETED, (finding("a"),)),
    )
    forward = AnalysisReport(
        Repository("fixture"), (second, first), results, policy(Category.TESTING)
    )
    backward = AnalysisReport(
        Repository("fixture"), (first, second), tuple(reversed(results)), policy(Category.TESTING)
    )
    assert forward == backward
    assert forward.score.value == Decimal("90.00")
    assert tuple(item.identifier for item in forward.findings) == ("a", "b")
    assert forward.score.categories[0].deductions[0].finding_ids == ("a", "b")


@pytest.mark.parametrize("points", [-1, 101, True])
def test_invalid_penalties_are_rejected(points: int) -> None:
    with pytest.raises(ValueError, match="penalty"):
        SeverityPenalty(Severity.HIGH, points)


@pytest.mark.parametrize("weight", [0, -1, True])
def test_invalid_weights_are_rejected(weight: int) -> None:
    with pytest.raises(ValueError, match="weights"):
        CategoryWeight(Category.TESTING, weight)


def test_policy_entries_reject_raw_strings_from_untyped_callers() -> None:
    with pytest.raises(ValueError, match="Severity"):
        SeverityPenalty(cast(Severity, "high"), 10)
    with pytest.raises(ValueError, match="Category"):
        CategoryWeight(cast(Category, "testing"), 1)


def test_policy_requires_complete_unique_monotonic_penalties_and_explicit_scope() -> None:
    base = policy(Category.TESTING)
    with pytest.raises(ValueError):
        replace(base, identifier="")
    for entries in ((), base.penalties[:-1], (*base.penalties, base.penalties[0])):
        with pytest.raises(ValueError, match="every severity"):
            replace(base, penalties=entries)
    for points in ((1, 5, 10, 25, 50), (0, 5, 4, 25, 50), (0, 0, 0, 0, 0)):
        with pytest.raises(ValueError, match="monotonically"):
            replace(
                base,
                penalties=tuple(
                    SeverityPenalty(severity, value)
                    for severity, value in zip(Severity, points, strict=True)
                ),
            )
    for weights in ((), (*base.weights, base.weights[0])):
        with pytest.raises(ValueError, match="unique category"):
            replace(base, weights=weights)


def test_plan_and_result_identity_errors_are_rejected() -> None:
    result = AnalyzerResult(spec(), AnalyzerState.COMPLETED)
    with pytest.raises(ValueError, match="planned analyzer identifiers"):
        score_repository((spec(), spec()), (), policy(Category.TESTING))
    with pytest.raises(ValueError, match="policy scope"):
        score_repository((spec(),), (), policy(Category.SECURITY))
    with pytest.raises(ValueError, match="metadata"):
        score_repository((), (result,), policy(Category.TESTING))
    with pytest.raises(ValueError, match="metadata"):
        score_repository(
            (replace(spec(), description="Different"),), (result,), policy(Category.TESTING)
        )
    with pytest.raises(ValueError, match="at most one"):
        score_repository((spec(),), (result, result), policy(Category.TESTING))


def test_cross_analyzer_duplicate_findings_and_conflicting_rule_categories_are_rejected() -> None:
    second = spec("second")
    first_result = AnalyzerResult(spec(), AnalyzerState.COMPLETED, (finding(),))
    duplicate = AnalyzerResult(second, AnalyzerState.COMPLETED, (finding(analyzer=second),))
    with pytest.raises(ValueError, match="globally unique"):
        score_repository((spec(), second), (first_result, duplicate), policy(Category.TESTING))
    security = spec("security", Category.SECURITY)
    conflict = AnalyzerResult(
        security, AnalyzerState.COMPLETED, (finding("different", analyzer=security),)
    )
    with pytest.raises(ValueError, match="exactly one category"):
        score_repository(
            (spec(), security),
            (first_result, conflict),
            policy(Category.TESTING, Category.SECURITY),
        )
