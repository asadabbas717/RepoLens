"""Fixed-grammar structural observations, never target imports or execution."""

import ast
import hashlib
import re
import warnings
from dataclasses import dataclass

from repolens.domain.models import (
    AnalysisContext,
    AnalyzerResult,
    AnalyzerSpec,
    AnalyzerState,
    Category,
    Evidence,
    Finding,
    Severity,
    require_enum,
    require_text,
)

TARGET_GRAMMAR = (3, 13)


@dataclass(frozen=True, slots=True)
class PythonRule:
    identifier: str
    severity: Severity
    title: str
    description: str
    recommendation: str
    category: Category = Category.CODE_QUALITY

    def __post_init__(self) -> None:
        if (
            not isinstance(self.identifier, str)
            or re.fullmatch(r"PY[0-9]{3}", self.identifier) is None
        ):
            raise ValueError("Python rule IDs must use PY followed by three digits")
        require_enum(self.severity, Severity, "severity")
        if not isinstance(self.category, Category) or self.category != Category.CODE_QUALITY:
            raise ValueError("Python static rules must belong to code quality")
        for field in ("title", "description", "recommendation"):
            require_text(getattr(self, field), field)


BARE_EXCEPT = PythonRule(
    "PY001",
    Severity.LOW,
    "Bare except handler",
    "An except handler specifies no exception type; it can intercept process-control "
    "exceptions as well as ordinary errors.",
    "Prefer the specific exception types intended here; if catching every exception "
    "is deliberate, retain that behavior knowingly.",
)
WILDCARD_IMPORT = PythonRule(
    "PY002",
    Severity.LOW,
    "Wildcard import",
    "A source module imports every exported name from another module, obscuring "
    "the local origins of names.",
    "Prefer explicit imports where practical; deliberate module re-exports may "
    "justify a wildcard import.",
)
RULES = (BARE_EXCEPT, WILDCARD_IMPORT)


def _finding(rule: PythonRule, path: str, line: int, column: int) -> Finding:
    key = f"{rule.identifier}\0{path}\0{line}:{column}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return Finding(
        f"python-static:{rule.identifier}:{digest}",
        rule.identifier,
        rule.category,
        rule.severity,
        rule.title,
        rule.description,
        (Evidence(rule.title + " observed in the AST", path, line),),
        rule.recommendation,
        PythonStaticAnalyzer.SPEC.identifier,
    )


class PythonStaticAnalyzer:
    SPEC = AnalyzerSpec(
        "python-static", Category.CODE_QUALITY, "Python 3.13-grammar structural AST observations"
    )

    @property
    def spec(self) -> AnalyzerSpec:
        return self.SPEC

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        snapshot = context.python_sources
        if snapshot is None:
            return AnalyzerResult(
                self.spec, AnalyzerState.FAILED, reason="Python source data is unavailable"
            )
        if not snapshot.files:
            return AnalyzerResult(
                self.spec, AnalyzerState.NOT_APPLICABLE, reason="No selected Python source files"
            )
        findings: list[Finding] = []
        for source in snapshot.files:
            try:
                # Target syntax warnings can include literals. They are neither
                # findings nor diagnostics; only this parse scopes their suppression.
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", SyntaxWarning)
                    warnings.simplefilter("ignore", DeprecationWarning)
                    tree = ast.parse(
                        source.text,
                        filename="<repolens-source>",
                        feature_version=TARGET_GRAMMAR,
                        optimize=0,
                    )
            except (SyntaxError, ValueError):
                return AnalyzerResult(
                    self.spec,
                    AnalyzerState.UNSUPPORTED,
                    reason="Source is not parseable with the Python 3.13 grammar",
                )
            except (RecursionError, MemoryError):
                return AnalyzerResult(
                    self.spec,
                    AnalyzerState.FAILED,
                    reason="Python AST parsing exceeded available resources",
                )
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler) and node.type is None:
                    findings.append(
                        _finding(BARE_EXCEPT, source.path, node.lineno, node.col_offset)
                    )
                elif (
                    isinstance(node, ast.ImportFrom)
                    and not source.path.endswith(".pyi")
                    and any(alias.name == "*" for alias in node.names)
                ):
                    findings.append(
                        _finding(WILDCARD_IMPORT, source.path, node.lineno, node.col_offset)
                    )
        return AnalyzerResult(
            self.spec,
            AnalyzerState.COMPLETED,
            tuple(sorted(findings, key=lambda finding: finding.identifier)),
        )
