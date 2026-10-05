"""Direct construction must preserve domain integrity without evaluating policy."""

from dataclasses import replace
from decimal import Decimal
from typing import cast

import pytest

from repolens.domain.models import Category, Severity
from repolens.domain.scoring import CategoryScore, RepositoryScore, RuleDeduction, ScoreState


def deduction() -> RuleDeduction:
    return RuleDeduction("EXAMPLE001", Severity.HIGH, 25, ("f1",))


def assessed(value: int = 75) -> CategoryScore:
    return CategoryScore(
        Category.TESTING, ScoreState.ASSESSED, value, (deduction(),), ("a",), (), ()
    )


def incomplete() -> CategoryScore:
    return CategoryScore(Category.TESTING, ScoreState.INCOMPLETE, None, (), (), ("a",), ())


def non_applicable() -> CategoryScore:
    return CategoryScore(Category.TESTING, ScoreState.NOT_APPLICABLE, None, (), (), (), ("a",))


def test_severity_order_is_impact_order_not_lexical_order() -> None:
    assert tuple(Severity) == (
        Severity.INFO,
        Severity.LOW,
        Severity.MEDIUM,
        Severity.HIGH,
        Severity.CRITICAL,
    )


@pytest.mark.parametrize("points", [-1, 101, True, 1.5])
def test_deduction_rejects_invalid_points(points: object) -> None:
    with pytest.raises(ValueError, match="deduction points"):
        replace(deduction(), points=cast(int, points))


@pytest.mark.parametrize("ids", [(), ("",), (" ",), ("f1", "f1")])
def test_deduction_requires_nonempty_unique_nonblank_finding_ids(ids: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        replace(deduction(), finding_ids=ids)


def test_deduction_rejects_blank_rules_unknown_severity_and_positive_info_penalty() -> None:
    with pytest.raises(ValueError, match="rule_id"):
        replace(deduction(), rule_id=" ")
    with pytest.raises(ValueError, match="string"):
        replace(deduction(), rule_id=cast(str, 123))
    with pytest.raises(ValueError, match="string"):
        replace(deduction(), finding_ids=(cast(str, 123),))
    with pytest.raises(ValueError, match="Severity"):
        replace(deduction(), severity=cast(Severity, "high"))
    with pytest.raises(ValueError, match="INFO"):
        replace(deduction(), severity=Severity.INFO)
    assert replace(deduction(), severity=Severity.INFO, points=0).points == 0
    assert replace(deduction(), points=100).points == 100


@pytest.mark.parametrize("value", [None, -1, 101, True, Decimal("75.00"), 75.5])
def test_assessed_category_requires_bounded_integer(value: object) -> None:
    with pytest.raises(ValueError, match="assessed values"):
        replace(assessed(), value=cast(int | None, value))


@pytest.mark.parametrize("state", [ScoreState.INCOMPLETE, ScoreState.NOT_APPLICABLE])
def test_unassessed_categories_reject_numeric_values(state: ScoreState) -> None:
    base = incomplete() if state == ScoreState.INCOMPLETE else non_applicable()
    with pytest.raises(ValueError, match="numeric values"):
        replace(base, value=0)


def test_category_rejects_unknown_enums() -> None:
    with pytest.raises(ValueError, match="Category"):
        replace(assessed(), category=cast(Category, "testing"))
    with pytest.raises(ValueError, match="ScoreState"):
        replace(assessed(), state=cast(ScoreState, "assessed"))


@pytest.mark.parametrize("ids", [(" ",), ("a", "a")])
def test_every_analyzer_collection_rejects_invalid_identifiers(ids: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        replace(assessed(), completed_analyzers=ids)
    with pytest.raises(ValueError):
        replace(incomplete(), unavailable_analyzers=ids)
    with pytest.raises(ValueError):
        replace(non_applicable(), non_applicable_analyzers=ids)


def test_analyzer_membership_cannot_overlap_between_outcomes() -> None:
    with pytest.raises(ValueError, match="disjoint"):
        replace(assessed(), non_applicable_analyzers=("a",))
    with pytest.raises(ValueError, match="disjoint"):
        replace(incomplete(), completed_analyzers=("a",))
    with pytest.raises(ValueError, match="disjoint"):
        replace(incomplete(), non_applicable_analyzers=("a",))


def test_category_states_require_corresponding_work() -> None:
    with pytest.raises(ValueError, match="completed work"):
        replace(assessed(), completed_analyzers=())
    with pytest.raises(ValueError, match="no unavailable"):
        replace(assessed(), unavailable_analyzers=("b",))
    with pytest.raises(ValueError, match="only non-applicable"):
        replace(non_applicable(), non_applicable_analyzers=())
    with pytest.raises(ValueError, match="only non-applicable"):
        replace(non_applicable(), completed_analyzers=("b",))
    with pytest.raises(ValueError, match="only non-applicable"):
        replace(non_applicable(), unavailable_analyzers=("b",))
    with pytest.raises(ValueError, match="unavailable work"):
        replace(incomplete(), unavailable_analyzers=(), completed_analyzers=("b",))
    with pytest.raises(ValueError, match="unavailable work"):
        replace(incomplete(), unavailable_analyzers=(), non_applicable_analyzers=("b",))
    assert replace(incomplete(), unavailable_analyzers=()).state == ScoreState.INCOMPLETE


def test_deductions_require_completed_work_and_unique_rule_and_finding_references() -> None:
    with pytest.raises(ValueError, match="completed analyzer"):
        replace(incomplete(), deductions=(deduction(),))
    with pytest.raises(ValueError, match="completed analyzer"):
        replace(non_applicable(), deductions=(deduction(),))
    with pytest.raises(ValueError, match="rule IDs"):
        replace(assessed(), deductions=(deduction(), deduction()))
    with pytest.raises(ValueError, match="finding IDs"):
        replace(assessed(), deductions=(deduction(), replace(deduction(), rule_id="OTHER001")))
    assert (
        replace(incomplete(), deductions=(deduction(),), completed_analyzers=("b",)).value is None
    )


@pytest.mark.parametrize(
    "value",
    [
        Decimal("-0.01"),
        Decimal("100.01"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("75"),
        Decimal("75.0"),
        Decimal("75.000"),
        Decimal("75.001"),
        75,
        75.0,
        True,
    ],
)
def test_overall_requires_finite_bounded_two_decimal_representation(value: object) -> None:
    with pytest.raises(ValueError, match="finite Decimal"):
        RepositoryScore((assessed(),), cast(Decimal, value))


def test_repository_requires_unique_nonempty_category_scope() -> None:
    with pytest.raises(ValueError, match="scope"):
        RepositoryScore((), None)
    with pytest.raises(ValueError, match="unique"):
        RepositoryScore((incomplete(), incomplete()), None)


def test_overall_availability_must_agree_with_category_states() -> None:
    with pytest.raises(ValueError, match="without incomplete"):
        RepositoryScore((incomplete(),), Decimal("75.00"))
    with pytest.raises(ValueError, match="without incomplete"):
        RepositoryScore(
            (
                assessed(),
                replace(incomplete(), category=Category.SECURITY, unavailable_analyzers=("b",)),
            ),
            Decimal("75.00"),
        )
    with pytest.raises(ValueError, match="assessed scope"):
        RepositoryScore((non_applicable(),), Decimal("75.00"))
    with pytest.raises(ValueError, match="overall value"):
        RepositoryScore((assessed(),), None)
    assert RepositoryScore((non_applicable(),), None).value is None
    assert RepositoryScore((incomplete(),), None).value is None


def test_overall_cannot_lie_outside_assessed_category_bounds() -> None:
    for value in ("74.99", "75.01"):
        with pytest.raises(ValueError, match="category bounds"):
            RepositoryScore((assessed(),), Decimal(value))
    assert RepositoryScore((assessed(),), Decimal("75.00")).value == Decimal("75.00")
    for boundary in (0, 100):
        assert RepositoryScore((assessed(boundary),), Decimal(f"{boundary}.00")).value == boundary


def test_constructor_validation_does_not_recalculate_policy_arithmetic() -> None:
    # The category has no policy, so it cannot know the intended penalty table.
    lower, upper = (
        assessed(40),
        replace(
            assessed(80),
            category=Category.SECURITY,
            completed_analyzers=("b",),
            deductions=(replace(deduction(), rule_id="OTHER001", finding_ids=("f2",)),),
        ),
    )
    assert RepositoryScore((lower, upper), Decimal("61.25")).value == Decimal("61.25")


def test_repository_rejects_shared_analyzers_rules_and_findings_across_categories() -> None:
    first = assessed()
    second = replace(
        assessed(),
        category=Category.SECURITY,
        deductions=(replace(deduction(), rule_id="OTHER001", finding_ids=("f2",)),),
    )
    with pytest.raises(ValueError, match="repository analyzer IDs"):
        RepositoryScore((first, second), Decimal("75.00"))
    with pytest.raises(ValueError, match="repository rule IDs"):
        RepositoryScore(
            (
                first,
                replace(
                    second,
                    completed_analyzers=("b",),
                    deductions=(replace(deduction(), finding_ids=("f2",)),),
                ),
            ),
            Decimal("75.00"),
        )
    with pytest.raises(ValueError, match="repository finding IDs"):
        RepositoryScore(
            (
                first,
                replace(
                    second,
                    completed_analyzers=("b",),
                    deductions=(replace(deduction(), rule_id="OTHER001"),),
                ),
            ),
            Decimal("75.00"),
        )


def test_caller_owned_collections_cannot_mutate_frozen_score_values() -> None:
    finding_ids = ["f1"]
    rule = replace(deduction(), finding_ids=cast(tuple[str, ...], finding_ids))
    completed = ["a"]
    deductions = [rule]
    category = replace(
        assessed(),
        completed_analyzers=cast(tuple[str, ...], completed),
        deductions=cast(tuple[RuleDeduction, ...], deductions),
    )
    categories = [category]
    score = RepositoryScore(cast(tuple[CategoryScore, ...], categories), Decimal("75.00"))
    finding_ids.clear()
    completed.clear()
    deductions.clear()
    categories.clear()
    assert score.categories[0].completed_analyzers == ("a",)
    assert score.categories[0].deductions[0].finding_ids == ("f1",)
