"""Deterministic analyzer execution without acquisition, rendering or scoring."""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from repolens.domain.contracts import Analyzer
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerResult,
    AnalyzerSpec,
    AnalyzerState,
    Category,
)


@dataclass(frozen=True, slots=True, init=False)
class AnalyzerPlan:
    """Snapshot metadata and bound callables in exact identifier order.

    The plan freezes membership, not the internal state of analyzer instances.
    Metadata is read once at registration; result ownership uses that snapshot.
    """

    _entries: tuple[tuple[AnalyzerSpec, Callable[[AnalysisContext], AnalyzerResult]], ...] = field(
        repr=False
    )

    def __init__(self, analyzers: Iterable[Analyzer]) -> None:
        entries = []
        identifiers: set[str] = set()
        for analyzer in analyzers:
            try:
                spec = analyzer.spec
                execute = analyzer.analyze
                if not isinstance(spec, AnalyzerSpec) or not callable(execute):
                    raise ValueError("Unusable analyzer")
            except Exception:
                raise ValueError(
                    "Analyzer registration requires valid metadata and a callable"
                ) from None
            if spec.identifier in identifiers:
                raise ValueError("Analyzer identifiers must be unique")
            identifiers.add(spec.identifier)
            entries.append((spec, execute))
        object.__setattr__(
            self, "_entries", tuple(sorted(entries, key=lambda entry: entry[0].identifier))
        )

    @property
    def specs(self) -> tuple[AnalyzerSpec, ...]:
        """The declared plan for later explicit-policy report construction."""
        return tuple(spec for spec, _ in self._entries)


def _validate_result(
    result: AnalyzerResult,
    spec: AnalyzerSpec,
    finding_ids: set[str],
    rule_categories: dict[str, Category],
) -> AnalyzerResult:
    if not isinstance(result, AnalyzerResult) or result.analyzer != spec:
        raise ValueError("Result must belong to its registered analyzer")
    # Canonicalize finding order using the existing domain constructor for
    # state/source/category validation rather than duplicating its rules.
    ordered = AnalyzerResult(
        spec,
        result.state,
        tuple(sorted(result.findings, key=lambda finding: finding.identifier)),
        result.reason,
    )
    for finding in ordered.findings:
        if finding.identifier in finding_ids:
            raise ValueError("Finding identifiers must be globally unique")
        if rule_categories.get(finding.rule_id, finding.category) != finding.category:
            raise ValueError("Rules must belong to exactly one category")
    return ordered


def execute_analyzers(plan: AnalyzerPlan, context: AnalysisContext) -> tuple[AnalyzerResult, ...]:
    """Invoke each registered callable once; isolate ordinary analyzer failures.

    No exception diagnostics are retained. BaseException cancellation signals
    propagate. This is an in-process boundary for trusted analyzers, not a sandbox.
    """
    results: list[AnalyzerResult] = []
    finding_ids: set[str] = set()
    rule_categories: dict[str, Category] = {}
    for spec, execute in plan._entries:
        try:
            result = execute(context)
        except Exception:
            result = AnalyzerResult(spec, AnalyzerState.FAILED, reason="Analyzer execution failed")
        else:
            try:
                result = _validate_result(result, spec, finding_ids, rule_categories)
            except Exception:
                result = AnalyzerResult(
                    spec, AnalyzerState.FAILED, reason="Analyzer returned an invalid result"
                )
        for finding in result.findings:
            finding_ids.add(finding.identifier)
            rule_categories[finding.rule_id] = finding.category
        results.append(result)
    return tuple(results)
