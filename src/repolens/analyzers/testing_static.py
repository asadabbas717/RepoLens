"""Conservative test structure observations over detached Python text only."""

import ast
import hashlib
import re
from dataclasses import dataclass

from repolens.analyzers.python_ast import parse_source
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


@dataclass(frozen=True, slots=True)
class TestingRule:
    identifier: str
    severity: Severity
    title: str
    description: str
    recommendation: str
    category: Category = Category.TESTING

    def __post_init__(self) -> None:
        if (
            not isinstance(self.identifier, str)
            or re.fullmatch(r"TEST[0-9]{3}", self.identifier) is None
        ):
            raise ValueError("Testing rule IDs must use TEST followed by three digits")
        require_enum(self.severity, Severity, "severity")
        if not isinstance(self.category, Category) or self.category != Category.TESTING:
            raise ValueError("Testing rules must belong to testing")
        for field in ("title", "description", "recommendation"):
            require_text(getattr(self, field), field)


NO_TEST_SOURCES = TestingRule(
    "TEST001",
    Severity.INFO,
    "No conventional Python test sources observed",
    "No conventional Python test sources were observed in the available snapshot. "
    "Custom discovery and excluded example/fixture paths may contain tests.",
    "Review the project's test discovery conventions; this observation does not "
    "establish absence of tests.",
)
NO_DECLARATIONS = TestingRule(
    "TEST002",
    Severity.INFO,
    "No conventional test declarations observed",
    "A conventionally named Python test source has no directly visible test declarations "
    "under RepoLens's documented structural conventions. Generated or custom-loaded "
    "tests may exist.",
    "Review whether this file intentionally uses custom discovery, generation "
    "or helper-only content.",
)
RULES = (NO_TEST_SOURCES, NO_DECLARATIONS)
_NON_SUITE_DIRECTORIES = frozenset(
    {"example", "examples", "fixture", "fixtures", "testdata", "test_data"}
)


def is_test_source(path: str) -> bool:
    parts = path.split("/")
    if any(part in _NON_SUITE_DIRECTORIES for part in parts[:-1]):
        return False
    return re.fullmatch(r"(?:test_.+|.+_test)\.py", parts[-1]) is not None


def _test_name(name: str) -> bool:
    return name.startswith("test_") and len(name) > 5


def _test_class(node: ast.ClassDef) -> bool:
    # Literal shapes only: bindings, aliases and inheritance are not resolved.
    return node.name.startswith("Test") or any(
        (isinstance(base, ast.Name) and base.id == "TestCase")
        or (
            isinstance(base, ast.Attribute)
            and base.attr == "TestCase"
            and isinstance(base.value, ast.Name)
            and base.value.id == "unittest"
        )
        for base in node.bases
    )


def _has_declarations(tree: ast.Module) -> bool:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _test_name(node.name):
            return True
        if (
            isinstance(node, ast.ClassDef)
            and _test_class(node)
            and any(
                isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                and _test_name(method.name)
                for method in node.body
            )
        ):
            return True
    return False


def _finding(rule: TestingRule, path: str | None = None) -> Finding:
    identifier = f"testing-static:{rule.identifier}"
    if path is not None:
        identifier += ":" + hashlib.sha256(path.encode("utf-8")).hexdigest()
    evidence = Evidence(
        "No conventional test declarations observed in this file"
        if path
        else "No conventional test source paths observed in the available snapshot",
        path,
    )
    return Finding(
        identifier,
        rule.identifier,
        rule.category,
        rule.severity,
        rule.title,
        rule.description,
        (evidence,),
        rule.recommendation,
        TestingStaticAnalyzer.SPEC.identifier,
    )


class TestingStaticAnalyzer:
    SPEC = AnalyzerSpec(
        "testing-static",
        Category.TESTING,
        "Static conventional Python test structure; coverage not measured",
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
        candidates = tuple(source for source in snapshot.files if is_test_source(source.path))
        if not candidates:
            return AnalyzerResult(self.spec, AnalyzerState.COMPLETED, (_finding(NO_TEST_SOURCES),))
        findings: list[Finding] = []
        for source in candidates:
            try:
                tree = parse_source(source.text)
            except (SyntaxError, ValueError):
                return AnalyzerResult(
                    self.spec,
                    AnalyzerState.UNSUPPORTED,
                    reason="Candidate test source is not parseable with the Python 3.13 grammar",
                )
            except (RecursionError, MemoryError):
                return AnalyzerResult(
                    self.spec,
                    AnalyzerState.FAILED,
                    reason="Test AST parsing exceeded available resources",
                )
            if not _has_declarations(tree):
                findings.append(_finding(NO_DECLARATIONS, source.path))
        return AnalyzerResult(
            self.spec,
            AnalyzerState.COMPLETED,
            tuple(sorted(findings, key=lambda finding: finding.identifier)),
        )
