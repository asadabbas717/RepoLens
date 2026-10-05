"""Domain invariants and the analyzer structural contract."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest

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


def example_finding() -> Finding:
    return Finding(
        "occurrence-1",
        "EXAMPLE001",
        Category.TESTING,
        Severity.MEDIUM,
        "Example observation",
        "Synthetic unit-test evidence, not an implemented rule",
        (Evidence("Synthetic observation", "tests/example.py", 1),),
        "Review the observation",
        "example",
    )


def example_spec() -> AnalyzerSpec:
    return AnalyzerSpec("example", Category.TESTING, "Synthetic test metadata")


def test_valid_values_are_immutable_and_have_repository_relative_evidence() -> None:
    finding = example_finding()
    assert finding.evidence[0].file_path == "tests/example.py"
    assert Evidence("Repository-level observation").line_number is None
    assert AnalysisContext(Repository("example")).repository.name == "example"
    with pytest.raises(FrozenInstanceError):
        attribute = "title"
        setattr(finding, attribute, "Changed")


@pytest.mark.parametrize(
    "path",
    [
        "",
        ".",
        "..",
        "../file.py",
        "a/../b.py",
        "/etc/file.py",
        "C:/file.py",
        "C:file.py",
        "a\\b.py",
        "//host/share",
        "./a.py",
        "a//b.py",
        "a.py/",
    ],
)
def test_evidence_rejects_unsafe_or_noncanonical_locations(path: str) -> None:
    with pytest.raises(ValueError, match="file_path"):
        Evidence("Observation", path)


@pytest.mark.parametrize("line", [0, -1, True])
def test_evidence_requires_positive_integer_lines(line: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        Evidence("Observation", "file.py", line)


def test_evidence_requires_a_path_for_line_numbers() -> None:
    with pytest.raises(ValueError, match="requires file_path"):
        Evidence("Observation", line_number=1)


@pytest.mark.parametrize(
    "make_invalid",
    [
        lambda: replace(example_finding(), identifier=" "),
        lambda: replace(example_finding(), rule_id=" "),
        lambda: replace(example_finding(), title=" "),
        lambda: replace(example_finding(), description=" "),
        lambda: replace(example_finding(), recommendation=" "),
        lambda: replace(example_finding(), source_analyzer=" "),
    ],
)
def test_finding_requires_meaningful_text(make_invalid: Callable[[], Finding]) -> None:
    with pytest.raises(ValueError, match="blank"):
        make_invalid()


def test_finding_requires_evidence() -> None:
    with pytest.raises(ValueError, match="requires evidence"):
        replace(example_finding(), evidence=())


def test_repository_evidence_and_analyzer_metadata_reject_blank_text() -> None:
    with pytest.raises(ValueError):
        Repository(" ")
    with pytest.raises(ValueError):
        Evidence(" ")
    with pytest.raises(ValueError):
        replace(example_spec(), identifier="")
    with pytest.raises(ValueError):
        replace(example_spec(), description="")


def test_completed_result_can_have_findings_or_no_findings() -> None:
    assert AnalyzerResult(example_spec(), AnalyzerState.COMPLETED).findings == ()
    assert AnalyzerResult(
        example_spec(), AnalyzerState.COMPLETED, (example_finding(),)
    ).findings == (example_finding(),)


@pytest.mark.parametrize(
    "state",
    [
        AnalyzerState.FAILED,
        AnalyzerState.SKIPPED,
        AnalyzerState.UNSUPPORTED,
        AnalyzerState.NOT_APPLICABLE,
    ],
)
def test_noncompleted_results_require_reasons_and_cannot_claim_findings(
    state: AnalyzerState,
) -> None:
    assert AnalyzerResult(example_spec(), state, reason="Specific limitation").reason
    with pytest.raises(ValueError, match="require a reason"):
        AnalyzerResult(example_spec(), state)
    with pytest.raises(ValueError, match="blank"):
        AnalyzerResult(example_spec(), state, reason=" ")
    with pytest.raises(ValueError, match="must not contain findings"):
        AnalyzerResult(example_spec(), state, (example_finding(),), "Specific limitation")


def test_result_rejects_contradictory_completion_and_invalid_finding_ownership() -> None:
    with pytest.raises(ValueError, match="must not have"):
        AnalyzerResult(example_spec(), AnalyzerState.COMPLETED, reason="Failed")
    with pytest.raises(ValueError, match="source"):
        AnalyzerResult(
            example_spec(),
            AnalyzerState.COMPLETED,
            (replace(example_finding(), source_analyzer="other"),),
        )
    with pytest.raises(ValueError, match="category"):
        AnalyzerResult(
            example_spec(),
            AnalyzerState.COMPLETED,
            (replace(example_finding(), category=Category.SECURITY),),
        )
    with pytest.raises(ValueError, match="unique"):
        AnalyzerResult(
            example_spec(),
            AnalyzerState.COMPLETED,
            (
                example_finding(),
                example_finding(),
            ),
        )


def test_protocol_supports_analyzer_without_inheritance() -> None:
    class ContextObserver:
        """Test-only contract example; no product analyzer is introduced."""

        @property
        def spec(self) -> AnalyzerSpec:
            return example_spec()

        def analyze(self, context: AnalysisContext) -> AnalyzerResult:
            return AnalyzerResult(
                self.spec,
                AnalyzerState.NOT_APPLICABLE,
                reason=f"Synthetic test context: {context.repository.name}",
            )

    analyzer: Analyzer = ContextObserver()
    assert analyzer.analyze(AnalysisContext(Repository("fixture"))).reason == (
        "Synthetic test context: fixture"
    )


def test_untyped_callers_cannot_inject_unknown_states_or_domain_enum_values() -> None:
    with pytest.raises(ValueError, match="AnalyzerState"):
        AnalyzerResult(example_spec(), cast(AnalyzerState, "unknown"), reason="Unknown outcome")
    with pytest.raises(ValueError, match="Category"):
        replace(example_spec(), category=cast(Category, "testing"))
    with pytest.raises(ValueError, match="Category"):
        replace(example_finding(), category=cast(Category, "testing"))
    with pytest.raises(ValueError, match="Severity"):
        replace(example_finding(), severity=cast(Severity, "high"))
