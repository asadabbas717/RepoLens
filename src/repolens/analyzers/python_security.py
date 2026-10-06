"""Normalize safe vendor observations into security findings; no live target access."""

import hashlib

from repolens.analyzers.python_ast import parse_source
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerResult,
    AnalyzerSpec,
    AnalyzerState,
    Category,
    Evidence,
    Finding,
)
from repolens.domain.python_source import PythonSourceSnapshot
from repolens.domain.security import (
    BanditScan,
    SecurityFailure,
    SecurityToolFailed,
    SecurityToolUnavailable,
)

_FAILURE_REASONS = {
    SecurityFailure.EXECUTION: "Bandit scan could not be completed safely",
    SecurityFailure.TIMED_OUT: "Bandit scan timed out",
    SecurityFailure.OUTPUT_LIMIT: "Bandit output exceeded its limit",
    SecurityFailure.INVALID_OUTPUT: "Bandit output could not be validated",
    SecurityFailure.DIAGNOSTICS: "Bandit emitted diagnostics; completeness is unavailable",
}


class PythonSecurityAnalyzer:
    SPEC = AnalyzerSpec(
        "python-security",
        Category.SECURITY,
        "Detached optional Bandit static Python security observations",
    )

    def __init__(self, scanner: BanditScan) -> None:
        self._scanner = scanner

    @property
    def spec(self) -> AnalyzerSpec:
        return self.SPEC

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        snapshot = context.python_sources
        if snapshot is None:
            return AnalyzerResult(
                self.spec, AnalyzerState.FAILED, reason="Python source data is unavailable"
            )
        selected = PythonSourceSnapshot(
            source for source in snapshot.files if source.path.endswith(".py")
        )
        if not selected.files:
            return AnalyzerResult(
                self.spec, AnalyzerState.NOT_APPLICABLE, reason="No executable Python source files"
            )
        try:
            for source in selected.files:
                parse_source(source.text)
        except (SyntaxError, ValueError):
            return AnalyzerResult(
                self.spec,
                AnalyzerState.UNSUPPORTED,
                reason="Source is not parseable with the Python 3.13 grammar",
            )
        except (MemoryError, RecursionError):
            return AnalyzerResult(
                self.spec,
                AnalyzerState.FAILED,
                reason="Python AST parsing exceeded available resources",
            )
        try:
            observations = self._scanner.scan(selected)
        except SecurityToolUnavailable:
            return AnalyzerResult(
                self.spec, AnalyzerState.UNSUPPORTED, reason="Supported Bandit tool is unavailable"
            )
        except SecurityToolFailed as error:
            return AnalyzerResult(
                self.spec, AnalyzerState.FAILED, reason=_FAILURE_REASONS[error.kind]
            )
        findings: list[Finding] = []
        for issue in observations:
            key = f"{issue.rule}\0{issue.path}\0{issue.line}:{issue.column}"
            digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
            rule = "BANDIT-" + issue.rule
            findings.append(
                Finding(
                    f"python-security:{rule}:{digest}",
                    rule,
                    Category.SECURITY,
                    issue.severity,
                    f"Bandit {issue.rule} structural security observation",
                    "Bandit reported a static security pattern. Review its context; "
                    "this is not proof of exploitability.",
                    (
                        Evidence(
                            f"Bandit {issue.rule} observation; source text omitted",
                            issue.path,
                            issue.line,
                        ),
                    ),
                    f"Review the documented Bandit {issue.rule} check and the intended behavior "
                    "at this location.",
                    self.spec.identifier,
                )
            )
        return AnalyzerResult(
            self.spec,
            AnalyzerState.COMPLETED,
            tuple(sorted(findings, key=lambda finding: finding.identifier)),
        )
