"""Shared immutable presentation facts and bounded deterministic serialization."""

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from repolens.domain.models import AnalyzerSpec, Category
from repolens.domain.report import AnalysisReport

SCHEMA_VERSION: Final = "1"
MAX_REPORT_BYTES: Final = 64 * 1024 * 1024
LIMITATIONS: Final = (
    "Scores reflect completed supported observations only; "
    "100 means no deductive findings, not a certification.",
    "INFO observations remain visible; repeated occurrences do not multiply rule deductions.",
    "Unavailable work blocks numeric assessment; non-applicable work is excluded from weighting.",
    "Testing observations do not measure execution, coverage or effectiveness.",
    "Dependency vulnerability auditing is unavailable and not included in the default assessment.",
    "Categories outside policy scope are unassessed; "
    "static observations do not guarantee correctness or security.",
)


class ReportingError(Exception):
    """Controlled report eligibility or serialization-limit failure."""


@dataclass(frozen=True, slots=True)
class AnalyzerView:
    spec: AnalyzerSpec
    state: str | None
    reason: str | None
    finding_count: int


@dataclass(frozen=True, slots=True)
class ReportView:
    report: AnalysisReport
    repository_name: str
    analyzers: tuple[AnalyzerView, ...]
    outside_scope: tuple[Category, ...]


def project(report: AnalysisReport) -> ReportView:
    """Copy presentation facts, retaining scores and producer-redacted evidence.

    Repository is a permissive display value, not a path/privacy validator.
    A public report requires a basename rather than a transport or host path.
    Programmatic producers remain responsible for redaction of all free text.
    """
    name = report.repository.name
    if name in {".", ".."} or any(c in name for c in "/\\:@"):
        raise ReportingError("Repository identity is not suitable for public reporting")
    outcomes = {result.analyzer.identifier: result for result in report.results}
    analyzers: list[AnalyzerView] = []
    for spec in report.plan:
        result = outcomes.get(spec.identifier)
        analyzers.append(
            AnalyzerView(
                spec,
                result.state.value if result is not None else None,
                result.reason if result is not None else "Planned analyzer result is missing",
                len(result.findings) if result is not None else 0,
            )
        )
    scope = {entry.category for entry in report.policy.weights}
    return ReportView(report, name, tuple(analyzers), tuple(c for c in Category if c not in scope))


def visible_text(value: str) -> str:
    """Show controls/surrogates literally so terminal/HTML text cannot hide them."""
    return "".join(
        character.encode("unicode_escape").decode("ascii")
        if unicodedata.category(character).startswith("C")
        else character
        for character in value
    )


def bounded_text(chunks: Iterable[str]) -> str:
    """Bound UTF-8 serialized size without silently omitting any evidence."""
    parts: list[str] = []
    size = 0
    for chunk in chunks:
        size += len(chunk.encode("utf-8"))
        if size > MAX_REPORT_BYTES:
            raise ReportingError("Serialized report exceeds its byte limit")
        parts.append(chunk)
    return "".join(parts)
