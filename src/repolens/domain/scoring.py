"""Deterministic scoring using caller-supplied, explicit policy values."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from repolens.domain.models import (
    AnalyzerResult,
    AnalyzerSpec,
    AnalyzerState,
    Category,
    Severity,
    require_enum,
    require_text,
)


@dataclass(frozen=True, slots=True)
class SeverityPenalty:
    severity: Severity
    points: int

    def __post_init__(self) -> None:
        require_enum(self.severity, Severity, "severity")
        if type(self.points) is not int or not 0 <= self.points <= 100:
            raise ValueError("penalty points must be integers between 0 and 100")


@dataclass(frozen=True, slots=True)
class CategoryWeight:
    category: Category
    weight: int

    def __post_init__(self) -> None:
        require_enum(self.category, Category, "category")
        if type(self.weight) is not int or self.weight < 1:
            raise ValueError("category weights must be positive integers")


@dataclass(frozen=True, slots=True)
class ScoringPolicy:
    """Weights declare assessment scope; penalties have no calibrated defaults."""

    identifier: str
    penalties: tuple[SeverityPenalty, ...]
    weights: tuple[CategoryWeight, ...]

    def __post_init__(self) -> None:
        require_text(self.identifier, "policy identifier")
        object.__setattr__(self, "penalties", tuple(self.penalties))
        object.__setattr__(self, "weights", tuple(self.weights))
        points = {entry.severity: entry.points for entry in self.penalties}
        if len(points) != len(self.penalties) or set(points) != set(Severity):
            raise ValueError("policy requires exactly one penalty for every severity")
        ordered = [points[severity] for severity in Severity]
        if ordered[0] != 0 or ordered != sorted(ordered) or ordered[-1] == 0:
            raise ValueError("INFO must be zero; penalties must increase monotonically with impact")
        categories = {entry.category for entry in self.weights}
        if not categories or len(categories) != len(self.weights):
            raise ValueError("policy requires nonempty, unique category weights")


class ScoreState(StrEnum):
    ASSESSED = "assessed"
    INCOMPLETE = "incomplete"
    NOT_APPLICABLE = "not_applicable"


def _unique_identifiers(values: tuple[str, ...], field: str) -> tuple[str, ...]:
    identifiers = tuple(values)
    for identifier in identifiers:
        require_text(identifier, field)
    if len(set(identifiers)) != len(identifiers):
        raise ValueError(f"{field} must be unique")
    return identifiers


@dataclass(frozen=True, slots=True)
class RuleDeduction:
    rule_id: str
    severity: Severity
    points: int
    finding_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require_text(self.rule_id, "rule_id")
        require_enum(self.severity, Severity, "severity")
        if type(self.points) is not int or not 0 <= self.points <= 100:
            raise ValueError("deduction points must be integers between 0 and 100")
        if self.severity == Severity.INFO and self.points != 0:
            raise ValueError("INFO deductions must have zero points")
        object.__setattr__(
            self, "finding_ids", _unique_identifiers(self.finding_ids, "finding IDs")
        )
        if not self.finding_ids:
            raise ValueError("a deduction requires finding IDs")


@dataclass(frozen=True, slots=True)
class CategoryScore:
    category: Category
    state: ScoreState
    value: int | None
    deductions: tuple[RuleDeduction, ...]
    completed_analyzers: tuple[str, ...]
    unavailable_analyzers: tuple[str, ...]
    non_applicable_analyzers: tuple[str, ...]

    def __post_init__(self) -> None:
        require_enum(self.category, Category, "category")
        require_enum(self.state, ScoreState, "state")
        object.__setattr__(self, "deductions", tuple(self.deductions))
        groups = (
            ("completed_analyzers", self.completed_analyzers),
            ("unavailable_analyzers", self.unavailable_analyzers),
            ("non_applicable_analyzers", self.non_applicable_analyzers),
        )
        memberships: set[str] = set()
        for field, identifiers in groups:
            identifiers = _unique_identifiers(identifiers, field)
            if memberships.intersection(identifiers):
                raise ValueError("analyzer memberships must be disjoint")
            memberships.update(identifiers)
            object.__setattr__(self, field, identifiers)
        if self.state == ScoreState.ASSESSED:
            if type(self.value) is not int or not 0 <= self.value <= 100:
                raise ValueError("assessed values must be integers between 0 and 100")
            if not self.completed_analyzers or self.unavailable_analyzers:
                raise ValueError(
                    "assessed categories require completed work and no unavailable work"
                )
        else:
            if self.value is not None:
                raise ValueError("unassessed categories must not have numeric values")
            if self.state == ScoreState.NOT_APPLICABLE:
                if (
                    self.completed_analyzers
                    or self.unavailable_analyzers
                    or not self.non_applicable_analyzers
                ):
                    raise ValueError("non-applicable categories require only non-applicable work")
            elif memberships and not self.unavailable_analyzers:
                raise ValueError("incomplete categories require unavailable work or an empty plan")
        if self.deductions and not self.completed_analyzers:
            raise ValueError("deductions require completed analyzer work")
        _unique_identifiers(tuple(item.rule_id for item in self.deductions), "deduction rule IDs")
        _unique_identifiers(
            tuple(identifier for item in self.deductions for identifier in item.finding_ids),
            "deduction finding IDs",
        )


@dataclass(frozen=True, slots=True)
class RepositoryScore:
    categories: tuple[CategoryScore, ...]
    value: Decimal | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "categories", tuple(self.categories))
        if not self.categories:
            raise ValueError("repository scores require a declared category scope")
        if len({item.category for item in self.categories}) != len(self.categories):
            raise ValueError("score categories must be unique")
        _unique_identifiers(
            tuple(
                identifier
                for item in self.categories
                for identifier in (
                    *item.completed_analyzers,
                    *item.unavailable_analyzers,
                    *item.non_applicable_analyzers,
                )
            ),
            "repository analyzer IDs",
        )
        _unique_identifiers(
            tuple(rule.rule_id for item in self.categories for rule in item.deductions),
            "repository rule IDs",
        )
        _unique_identifiers(
            tuple(
                identifier
                for item in self.categories
                for rule in item.deductions
                for identifier in rule.finding_ids
            ),
            "repository finding IDs",
        )
        assessed = [item.value for item in self.categories if item.value is not None]
        incomplete = any(item.state == ScoreState.INCOMPLETE for item in self.categories)
        if self.value is None:
            if assessed and not incomplete:
                raise ValueError("complete assessed scope requires an overall value")
        else:
            if (
                not isinstance(self.value, Decimal)
                or not self.value.is_finite()
                or not 0 <= self.value <= 100
                or self.value.as_tuple().exponent != -2
            ):
                raise ValueError(
                    "overall value must be a finite Decimal in 0..100 with two decimals"
                )
            if incomplete or not assessed:
                raise ValueError(
                    "numeric overall values require assessed scope without incomplete work"
                )
            if not min(assessed) <= self.value <= max(assessed):
                raise ValueError("overall value must lie within assessed category bounds")


def score_repository(
    plan: tuple[AnalyzerSpec, ...],
    results: tuple[AnalyzerResult, ...],
    policy: ScoringPolicy,
) -> RepositoryScore:
    """Score declared scope; unavailable work blocks category and overall values.

    Constructors validate structural integrity; only this function evaluates
    policy arithmetic. Use this function or AnalysisReport for derived scores.
    """
    planned = {spec.identifier: spec for spec in plan}
    if len(planned) != len(plan):
        raise ValueError("planned analyzer identifiers must be unique")
    scope = {entry.category for entry in policy.weights}
    if any(spec.category not in scope for spec in plan):
        raise ValueError("planned analyzers must belong to the policy scope")
    outcomes: dict[str, AnalyzerResult] = {}
    finding_ids: set[str] = set()
    rule_categories: dict[str, Category] = {}
    for result in results:
        identifier = result.analyzer.identifier
        if planned.get(identifier) != result.analyzer:
            raise ValueError("result must match a planned analyzer's metadata")
        if identifier in outcomes:
            raise ValueError("each analyzer must have at most one result")
        outcomes[identifier] = result
        for finding in result.findings:
            if finding.identifier in finding_ids:
                raise ValueError("finding identifiers must be globally unique")
            finding_ids.add(finding.identifier)
            if rule_categories.setdefault(finding.rule_id, finding.category) != finding.category:
                raise ValueError("a rule must belong to exactly one category")
    penalties = {entry.severity: entry.points for entry in policy.penalties}
    scores = tuple(
        _score_category(category, planned, outcomes, penalties)
        for category in Category
        if category in scope
    )
    assessed = [score for score in scores if score.state == ScoreState.ASSESSED]
    overall: Decimal | None = None
    if assessed and all(score.state != ScoreState.INCOMPLETE for score in scores):
        weights = {entry.category: entry.weight for entry in policy.weights}
        numerator = sum(
            (score.value if score.value is not None else 0) * weights[score.category]
            for score in assessed
        )
        denominator = sum(weights[score.category] for score in assessed)
        hundredths, remainder = divmod(numerator * 100, denominator)
        if remainder * 2 >= denominator:
            hundredths += 1
        overall = Decimal(f"{hundredths // 100}.{hundredths % 100:02d}")
    return RepositoryScore(scores, overall)


def _score_category(
    category: Category,
    planned: dict[str, AnalyzerSpec],
    outcomes: dict[str, AnalyzerResult],
    penalties: dict[Severity, int],
) -> CategoryScore:
    identifiers = sorted(key for key, spec in planned.items() if spec.category == category)
    completed: list[str] = []
    unavailable: list[str] = []
    non_applicable: list[str] = []
    rules: dict[str, list[tuple[Severity, str]]] = {}
    for identifier in identifiers:
        result = outcomes.get(identifier)
        if result is None or result.state in (
            AnalyzerState.FAILED,
            AnalyzerState.SKIPPED,
            AnalyzerState.UNSUPPORTED,
        ):
            unavailable.append(identifier)
        elif result.state == AnalyzerState.NOT_APPLICABLE:
            non_applicable.append(identifier)
        else:
            completed.append(identifier)
            for finding in result.findings:
                rules.setdefault(finding.rule_id, []).append((finding.severity, finding.identifier))
    deductions: list[RuleDeduction] = []
    for rule_id, observations in sorted(rules.items()):
        severity = max((item[0] for item in observations), key=list(Severity).index)
        deductions.append(
            RuleDeduction(
                rule_id,
                severity,
                penalties[severity],
                tuple(sorted(item[1] for item in observations)),
            )
        )
    state = ScoreState.INCOMPLETE
    value: int | None = None
    if identifiers and not unavailable:
        if completed:
            state = ScoreState.ASSESSED
            value = max(0, 100 - sum(item.points for item in deductions))
        else:
            state = ScoreState.NOT_APPLICABLE
    return CategoryScore(
        category,
        state,
        value,
        tuple(deductions),
        tuple(completed),
        tuple(unavailable),
        tuple(non_applicable),
    )
