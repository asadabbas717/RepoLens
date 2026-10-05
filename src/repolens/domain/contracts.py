"""Extensibility boundary, without registration or execution orchestration."""

from typing import Protocol

from repolens.domain.models import AnalysisContext, AnalyzerResult, AnalyzerSpec


class Analyzer(Protocol):
    """Analyze immutable context and return an explicit result.

    Implementations must not render reports or execute target code. Expected
    inability to analyze is represented by result states. Unexpected exceptions
    propagate for the future application layer to isolate; this protocol does
    not implement failure handling or perform I/O.
    """

    @property
    def spec(self) -> AnalyzerSpec: ...

    def analyze(self, context: AnalysisContext) -> AnalyzerResult: ...
