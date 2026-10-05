"""Controlled analyzer doubles exercise planning, ownership and failure isolation."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from itertools import permutations
from typing import cast

import pytest

from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.domain.contracts import Analyzer
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

CONTEXT = AnalysisContext(Repository("controlled fixture"))


class FakeAnalyzer:
    def __init__(
        self,
        identifier: str,
        category: Category = Category.TESTING,
        action: Callable[[AnalysisContext], AnalyzerResult] | None = None,
    ) -> None:
        self.spec = AnalyzerSpec(identifier, category, "Controlled test analyzer")
        self.action = action
        self.calls: list[AnalysisContext] = []

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        self.calls.append(context)
        if self.action is not None:
            return self.action(context)
        return AnalyzerResult(self.spec, AnalyzerState.COMPLETED)


def finding(owner: AnalyzerSpec, identifier: str, rule: str = "TEST001") -> Finding:
    return Finding(
        identifier,
        rule,
        owner.category,
        Severity.LOW,
        "Controlled observation",
        "Synthetic fixture",
        (Evidence("Redacted evidence"),),
        "Review fixture",
        owner.identifier,
    )


def test_empty_plan_is_explicitly_supported() -> None:
    plan = AnalyzerPlan(())
    assert plan.specs == ()
    assert execute_analyzers(plan, CONTEXT) == ()


def test_registration_snapshots_membership_metadata_and_callable() -> None:
    analyzer = FakeAnalyzer("one")
    registered_spec = analyzer.spec
    supplied = [analyzer]
    plan = AnalyzerPlan(supplied)
    supplied.clear()
    # spec is never accessed again; changed metadata must not redefine the plan.
    analyzer.spec = replace(registered_spec, identifier="changed")
    assert plan.specs == (registered_spec,)
    result = execute_analyzers(plan, CONTEXT)[0]
    assert result.analyzer == registered_spec
    assert result.state == AnalyzerState.FAILED
    with pytest.raises(FrozenInstanceError):
        plan.__setattr__("_entries", ())


def test_duplicate_ids_are_rejected_before_execution() -> None:
    analyzers = [FakeAnalyzer("same"), FakeAnalyzer("same", Category.SECURITY)]
    with pytest.raises(ValueError, match="unique"):
        AnalyzerPlan(analyzers)
    assert all(not analyzer.calls for analyzer in analyzers)


@pytest.mark.parametrize("defect", ["raises", "wrong-type", "missing-method", "not-callable"])
def test_unusable_registration_is_rejected_without_raw_diagnostics(defect: str) -> None:
    class Unusable:
        @property
        def spec(self) -> object:
            if defect == "raises":
                raise OSError("secret registration path")
            if defect == "wrong-type":
                return "secret metadata"
            return AnalyzerSpec("bad", Category.TESTING, "Test metadata")

        def __getattr__(self, name: str) -> object:
            if defect == "not-callable":
                return None
            raise AttributeError("secret missing method")

    with pytest.raises(ValueError, match="registration") as failure:
        AnalyzerPlan([cast(Analyzer, Unusable())])
    assert "secret" not in str(failure.value)
    assert failure.value.__suppress_context__


@pytest.mark.parametrize("state", list(AnalyzerState))
def test_all_valid_outcome_states_are_preserved(state: AnalyzerState) -> None:
    analyzer = FakeAnalyzer("one")
    expected = AnalyzerResult(
        analyzer.spec, state, reason=None if state == AnalyzerState.COMPLETED else "Safe reason"
    )
    analyzer.action = lambda context: expected
    assert execute_analyzers(AnalyzerPlan([analyzer]), CONTEXT) == (expected,)
    assert analyzer.calls == [CONTEXT]


@pytest.mark.parametrize("error_type", [OSError, ValueError, TypeError, RuntimeError])
def test_failure_is_sanitized_and_does_not_prevent_later_execution(
    error_type: type[Exception],
) -> None:
    def fail(context: AnalysisContext) -> AnalyzerResult:
        raise error_type("secret token and target path")

    broken = FakeAnalyzer("a", action=fail)
    later = FakeAnalyzer("b")
    results = execute_analyzers(AnalyzerPlan([later, broken]), CONTEXT)
    assert results[0] == AnalyzerResult(
        broken.spec, AnalyzerState.FAILED, reason="Analyzer execution failed"
    )
    assert results[1].state == AnalyzerState.COMPLETED
    assert broken.calls == later.calls == [CONTEXT]
    assert "secret" not in repr(results)


@pytest.mark.parametrize("mismatch", ["identifier", "category", "description", "type", "multiple"])
def test_wrong_result_ownership_or_shape_becomes_failed(mismatch: str) -> None:
    analyzer = FakeAnalyzer("a")
    spec = analyzer.spec
    if mismatch == "identifier":
        spec = replace(spec, identifier="other")
    elif mismatch == "category":
        spec = replace(spec, category=Category.SECURITY)
    elif mismatch == "description":
        spec = replace(spec, description="Other metadata")
    output: object = AnalyzerResult(spec, AnalyzerState.COMPLETED)
    if mismatch == "type":
        output = None
    elif mismatch == "multiple":
        output = [output, output]
    analyzer.action = lambda context: cast(AnalyzerResult, output)
    later = FakeAnalyzer("b")
    results = execute_analyzers(AnalyzerPlan([analyzer, later]), CONTEXT)
    assert results[0] == AnalyzerResult(
        analyzer.spec, AnalyzerState.FAILED, reason="Analyzer returned an invalid result"
    )
    assert results[1].state == AnalyzerState.COMPLETED


def test_execution_and_finding_order_are_independent_of_registration_and_output_order() -> None:
    traces: list[str] = []
    analyzers = [FakeAnalyzer(identifier) for identifier in ("z", "B", "a")]
    for analyzer in analyzers:

        def complete(
            context: AnalysisContext, owner: AnalyzerSpec = analyzer.spec
        ) -> AnalyzerResult:
            traces.append(owner.identifier)
            return AnalyzerResult(
                owner,
                AnalyzerState.COMPLETED,
                (finding(owner, owner.identifier + "-2"), finding(owner, owner.identifier + "-1")),
            )

        analyzer.action = complete
    expected: tuple[AnalyzerResult, ...] | None = None
    for supplied in permutations(analyzers):
        traces.clear()
        plan = AnalyzerPlan(iter(supplied))
        results = execute_analyzers(plan, CONTEXT)
        assert traces == ["B", "a", "z"]
        assert tuple(result.analyzer for result in results) == plan.specs
        assert all(
            result.findings[0].identifier < result.findings[1].identifier for result in results
        )
        if expected is None:
            expected = results
        assert results == expected


@pytest.mark.parametrize("conflict", ["finding-id", "rule-category"])
def test_cross_analyzer_conflicts_fail_only_later_conflicting_result(conflict: str) -> None:
    first = FakeAnalyzer("a")
    conflicting = FakeAnalyzer("b", Category.SECURITY)
    first.action = lambda context: AnalyzerResult(
        first.spec, AnalyzerState.COMPLETED, (finding(first.spec, "id-a"),)
    )
    conflicting.action = lambda context: AnalyzerResult(
        conflicting.spec,
        AnalyzerState.COMPLETED,
        (
            finding(conflicting.spec, "unused", "UNUSED"),
            finding(
                conflicting.spec,
                "id-a" if conflict == "finding-id" else "id-b",
                "OTHER" if conflict == "finding-id" else "TEST001",
            ),
        ),
    )
    last = FakeAnalyzer("c")
    last.action = lambda context: AnalyzerResult(
        last.spec, AnalyzerState.COMPLETED, (finding(last.spec, "unused", "UNUSED"),)
    )
    results = execute_analyzers(AnalyzerPlan([last, conflicting, first]), CONTEXT)
    assert [result.state for result in results] == [
        AnalyzerState.COMPLETED,
        AnalyzerState.FAILED,
        AnalyzerState.COMPLETED,
    ]
    assert results[1].findings == ()
    # Rejected partial results must not reserve their identifiers or rules.
    assert results[2].findings[0].identifier == "unused"


@pytest.mark.parametrize("signal", [KeyboardInterrupt, SystemExit])
def test_cancellation_signals_propagate(signal: type[BaseException]) -> None:
    def cancel(context: AnalysisContext) -> AnalyzerResult:
        raise signal()

    first = FakeAnalyzer("a", action=cancel)
    later = FakeAnalyzer("b")
    with pytest.raises(signal):
        execute_analyzers(AnalyzerPlan([later, first]), CONTEXT)
    assert later.calls == []


def test_metadata_and_callable_are_captured_once(monkeypatch: pytest.MonkeyPatch) -> None:
    class ReadOnce:
        def __init__(self) -> None:
            self.metadata_reads = 0
            self.owner = AnalyzerSpec("one", Category.TESTING, "Controlled metadata")

        @property
        def spec(self) -> AnalyzerSpec:
            self.metadata_reads += 1
            if self.metadata_reads > 1:
                raise OSError("secret late metadata failure")
            return self.owner

        def analyze(self, context: AnalysisContext) -> AnalyzerResult:
            return AnalyzerResult(self.owner, AnalyzerState.COMPLETED)

    analyzer = ReadOnce()
    plan = AnalyzerPlan([analyzer])
    monkeypatch.setattr(analyzer, "analyze", lambda context: None)
    assert execute_analyzers(plan, CONTEXT)[0].state == AnalyzerState.COMPLETED
    assert analyzer.metadata_reads == 1


def test_findings_are_canonical_across_opposite_producer_orders() -> None:
    analyzer = FakeAnalyzer("one")
    observations = (finding(analyzer.spec, "a"), finding(analyzer.spec, "b"))
    plan = AnalyzerPlan([analyzer])
    analyzer.action = lambda context: AnalyzerResult(
        analyzer.spec, AnalyzerState.COMPLETED, observations
    )
    forward = execute_analyzers(plan, CONTEXT)
    analyzer.action = lambda context: AnalyzerResult(
        analyzer.spec, AnalyzerState.COMPLETED, tuple(reversed(observations))
    )
    assert execute_analyzers(plan, CONTEXT) == forward
