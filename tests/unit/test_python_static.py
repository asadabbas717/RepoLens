"""AST observations and grammar-boundary goldens run unchanged on 3.13 and 3.14."""

from collections.abc import Callable
from dataclasses import replace
from typing import cast
from unittest.mock import MagicMock

import pytest

from repolens.analyzers.python_static import RULES, TARGET_GRAMMAR, PythonRule, PythonStaticAnalyzer
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerState,
    Category,
    FileInventory,
    Repository,
    Severity,
)
from repolens.domain.python_source import PythonSourceFile, PythonSourceSnapshot


def context(text: str, path: str = "file.py") -> AnalysisContext:
    return AnalysisContext(
        Repository("fixture"),
        FileInventory((path,)),
        PythonSourceSnapshot((PythonSourceFile(path, text),)),
    )


@pytest.mark.parametrize(
    "text,rules",
    [
        ("try:\n    work()\nexcept:\n    pass\n", ("PY001",)),
        ("from module import *\n", ("PY002",)),
        ("try:\n    work()\nexcept Exception:\n    pass\n", ()),
        ("try:\n    work()\nexcept (ValueError, TypeError):\n    pass\n", ()),
        ("from module import value\n", ()),
        ("import module\n", ()),
        ("# from module import *\n", ()),
        ("'from module import *'\n", ()),
        ("", ()),
        ("# comment\n'docstring'\n", ()),
        ("try:\n    work()\nexcept* ValueError:\n    pass\n", ()),
    ],
)
def test_rule_positive_negative_and_false_positive_guards(
    text: str, rules: tuple[str, ...]
) -> None:
    result = PythonStaticAnalyzer().analyze(context(text))
    assert result.state == AnalyzerState.COMPLETED
    assert tuple(finding.rule_id for finding in result.findings) == rules


def test_stub_wildcard_reexports_are_intentionally_not_findings() -> None:
    result = PythonStaticAnalyzer().analyze(context("from module import *\n", "api.pyi"))
    assert result.state == AnalyzerState.COMPLETED and result.findings == ()


@pytest.mark.parametrize(
    "text",
    [
        "def broken(:\nsecret",
        "value = t'secret'",
        "try:\n pass\nexcept ValueError, TypeError:\n pass\n",
        "\x00",
    ],
)
def test_unparseable_or_newer_syntax_is_unsupported_without_raw_diagnostics(text: str) -> None:
    result = PythonStaticAnalyzer().analyze(context(text))
    assert TARGET_GRAMMAR == (3, 13)
    assert result.state == AnalyzerState.UNSUPPORTED
    assert result.findings == ()
    assert "secret" not in repr(result)


def test_selected_313_syntax_is_supported_on_both_host_interpreters() -> None:
    result = PythonStaticAnalyzer().analyze(
        context("type Alias[T = int] = list[T]\nmatch value:\n case 1: pass\n")
    )
    assert result.state == AnalyzerState.COMPLETED and result.findings == ()


def test_syntax_failure_does_not_retain_partial_findings() -> None:
    ctx = AnalysisContext(
        Repository("fixture"),
        FileInventory(("a.py", "b.py")),
        PythonSourceSnapshot(
            (
                PythonSourceFile("a.py", "from module import *"),
                PythonSourceFile("b.py", "def broken(:"),
            )
        ),
    )
    result = PythonStaticAnalyzer().analyze(ctx)
    assert result.state == AnalyzerState.UNSUPPORTED and not result.findings


def test_missing_and_no_python_data_are_distinct() -> None:
    analyzer = PythonStaticAnalyzer()
    assert analyzer.analyze(AnalysisContext(Repository("fixture"))).state == AnalyzerState.FAILED
    empty = AnalysisContext(Repository("fixture"), FileInventory(()), PythonSourceSnapshot(()))
    assert analyzer.analyze(empty).state == AnalyzerState.NOT_APPLICABLE


@pytest.mark.parametrize("error", [RecursionError, MemoryError])
def test_parser_resource_failure_is_explicit_and_sanitized(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception]
) -> None:
    monkeypatch.setattr(
        "repolens.analyzers.python_static.ast.parse", MagicMock(side_effect=error("secret"))
    )
    result = PythonStaticAnalyzer().analyze(context("pass"))
    assert result.state == AnalyzerState.FAILED and not result.findings
    assert "secret" not in repr(result)


def test_source_literals_and_target_syntax_warnings_never_escape() -> None:
    ctx = context("token = 'secret-value'\nvalue = '\\q'\nfrom module import *\n")
    result = PythonStaticAnalyzer().analyze(ctx)
    assert result.state == AnalyzerState.COMPLETED
    assert "secret-value" not in repr(ctx) + repr(result)
    assert result.findings[0].evidence[0].line_number == 3


def test_multiple_occurrences_have_distinct_deterministic_ids_and_safe_locations() -> None:
    text = "from first import *\nfrom second import *\ntry:\n    work()\nexcept:\n    pass\n"
    analyzer = PythonStaticAnalyzer()
    result = analyzer.analyze(context(text))
    assert result == analyzer.analyze(context(text))
    assert len({finding.identifier for finding in result.findings}) == 3
    assert result.findings == tuple(sorted(result.findings, key=lambda finding: finding.identifier))
    assert {finding.evidence[0].line_number for finding in result.findings} == {1, 2, 5}
    assert all(finding.evidence[0].file_path == "file.py" for finding in result.findings)
    assert all(finding.source_analyzer == "python-static" for finding in result.findings)


def test_catalog_has_stable_ids_categories_and_low_severities() -> None:
    assert tuple(rule.identifier for rule in RULES) == ("PY001", "PY002")
    assert all(
        rule.severity == Severity.LOW and rule.category == Category.CODE_QUALITY for rule in RULES
    )


def test_occurrence_identity_has_a_cross_version_golden_value() -> None:
    result = PythonStaticAnalyzer().analyze(context("from module import *\n"))
    assert result.findings[0].identifier == (
        "python-static:PY002:b4d1031b65ece177e80b179279f2d363cd37b5cda0873b293b3ec9ad682cbc46"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("identifier", "BAD"),
        ("identifier", None),
        ("severity", "low"),
        ("category", Category.SECURITY),
        ("title", ""),
        ("description", " "),
        ("recommendation", ""),
    ],
)
def test_invalid_catalog_metadata_is_rejected(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        cast(Callable[..., PythonRule], replace)(RULES[0], **{field: value})
