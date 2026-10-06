"""Honest unsupported audit outcomes until advisory severity has a safe contract."""

from repolens.domain.dependency_declarations import (
    InvalidManifest,
    UnsupportedDeclarations,
    parse_declarations,
)
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerResult,
    AnalyzerSpec,
    AnalyzerState,
    Category,
)


class DependencyAuditAnalyzer:
    SPEC = AnalyzerSpec(
        "dependency-audit",
        Category.SECURITY,
        "Static direct declarations; vulnerability auditing is unavailable",
    )

    @property
    def spec(self) -> AnalyzerSpec:
        return self.SPEC

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        snapshot = context.dependency_manifests
        if snapshot is None:
            return AnalyzerResult(
                self.spec, AnalyzerState.FAILED, reason="Dependency manifest data is unavailable"
            )
        if not snapshot.files:
            return AnalyzerResult(
                self.spec,
                AnalyzerState.UNSUPPORTED,
                reason="No supported root dependency manifests; dependency scope is unknown",
            )
        try:
            parse_declarations(snapshot)
        except InvalidManifest:
            return AnalyzerResult(
                self.spec, AnalyzerState.FAILED, reason="Dependency manifest parsing failed"
            )
        except UnsupportedDeclarations:
            return AnalyzerResult(
                self.spec,
                AnalyzerState.UNSUPPORTED,
                reason="Dependency declarations are outside the supported static subset",
            )
        return AnalyzerResult(
            self.spec,
            AnalyzerState.UNSUPPORTED,
            reason="Vulnerability auditing is deferred: advisory severity is unavailable",
        )
