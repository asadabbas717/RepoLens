"""Conservative discovery, fixed grammar and safe deterministic evidence."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from typing import cast
from unittest.mock import MagicMock

import pytest

from repolens.analyzers.testing_static import RULES, TestingStaticAnalyzer, is_test_source
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerState,
    Category,
    FileInventory,
    Repository,
    Severity,
)
from repolens.domain.python_source import PythonSourceFile, PythonSourceSnapshot


def context(files: dict[str, str]) -> AnalysisContext:
    return AnalysisContext(
        Repository("fixture"),
        FileInventory(files),
        PythonSourceSnapshot(PythonSourceFile(path, text) for path, text in files.items()),
    )


@pytest.mark.parametrize(
    "path,expected",
    [
        ("test_example.py", True),
        ("example_test.py", True),
        ("tests/unit/test_api.py", True),
        ("pkg/api_test.py", True),
        ("tests/api.py", False),
        ("contest.py", False),
        ("test_api.py.old", False),
        ("test_api.pyi", False),
        ("conftest.py", False),
        ("test_.py", False),
        ("_test.py", False),
        ("TEST_api.py", False),
        ("examples/test_demo.py", False),
        ("fixtures/test_data.py", False),
        ("testdata/api_test.py", False),
        ("tests/fixtures/test_nested.py", False),
        ("myexamples/test_real.py", True),
        ("tests/test_é.py", True),
    ],
)
def test_exact_discovery(path: str, expected: bool) -> None:
    assert is_test_source(path) is expected


@pytest.mark.parametrize(
    "text,present",
    [
        ("def test_api(): pass", True),
        ("async def test_api(): pass", True),
        ("class TestAPI:\n def test_api(self): pass", True),
        ("class TestAPI:\n async def test_api(self): pass", True),
        ("class API(unittest.TestCase):\n def test_api(self): pass", True),
        ("class API(TestCase):\n def test_api(self): pass", True),
        ("class API(other.TestCase):\n def test_api(self): pass", False),
        ("class API:\n def test_api(self): pass", False),
        ("class TestAPI: pass", False),
        ("def test_(): pass", False),
        ("# def test_api(): pass\n'def test_api(): pass'", False),
        ("def helper():\n def test_hidden(): pass", False),
        ("if True:\n def test_dynamic(): pass", False),
        ("import pytest\nimport unittest", False),
        ("", False),
        ("@custom\ndef test_api(): pass", True),
    ],
)
def test_direct_ast_shapes(text: str, present: bool) -> None:
    result = TestingStaticAnalyzer().analyze(context({"test_api.py": text}))
    assert result.state == AnalyzerState.COMPLETED
    assert bool(result.findings) is not present
    if result.findings:
        assert result.findings[0].rule_id == "TEST002"
        assert result.findings[0].evidence[0].line_number is None


@pytest.mark.parametrize(
    "files",
    [
        {"app.py": "broken source is irrelevant to filename observation"},
        {"checks.py": "def test_api(): pass"},
        {"test_api.pyi": "def test_api(): ..."},
        {"conftest.py": "raise RuntimeError('secret')"},
        {"examples/test_demo.py": "def test_api(): pass"},
    ],
)
def test_absence_is_repository_observation(files: dict[str, str]) -> None:
    result = TestingStaticAnalyzer().analyze(context(files))
    assert result.state == AnalyzerState.COMPLETED
    (finding,) = result.findings
    assert finding.identifier == "testing-static:TEST001"
    assert finding.severity == Severity.INFO
    assert finding.evidence[0].file_path is None
    assert "secret" not in repr(result)


def test_missing_and_empty_data_are_distinct() -> None:
    analyzer = TestingStaticAnalyzer()
    assert analyzer.analyze(AnalysisContext(Repository("fixture"))).state == AnalyzerState.FAILED
    assert analyzer.analyze(context({})).state == AnalyzerState.NOT_APPLICABLE


@pytest.mark.parametrize("text", ["def broken(: secret", "x = t'secret'", "\x00"])
def test_syntax_failure_discards_partial_findings(text: str) -> None:
    result = TestingStaticAnalyzer().analyze(context({"test_a.py": "", "test_z.py": text}))
    assert result.state == AnalyzerState.UNSUPPORTED and result.findings == ()
    assert "secret" not in repr(result)


@pytest.mark.parametrize("error", [MemoryError, RecursionError])
def test_resource_failure_is_sanitized(
    error: type[Exception], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "repolens.analyzers.testing_static.parse_source", MagicMock(side_effect=error("secret"))
    )
    result = TestingStaticAnalyzer().analyze(context({"test_a.py": ""}))
    assert result.state == AnalyzerState.FAILED and result.findings == ()
    assert "secret" not in repr(result)


def test_each_candidate_parsed_once_order_and_ids_stable(monkeypatch: pytest.MonkeyPatch) -> None:
    from repolens.analyzers.python_ast import parse_source

    parser = MagicMock(wraps=parse_source)
    monkeypatch.setattr("repolens.analyzers.testing_static.parse_source", parser)
    files = {"test_z.py": "secret='credential'", "test_a.py": "", "app.py": "invalid!"}
    first = TestingStaticAnalyzer().analyze(context(files))
    assert parser.call_count == 2
    second = TestingStaticAnalyzer().analyze(context(dict(reversed(tuple(files.items())))))
    assert first == second
    assert [f.identifier for f in first.findings] == sorted(f.identifier for f in first.findings)
    assert "credential" not in repr(first)
    assert any(
        f.identifier
        == (
            "testing-static:TEST002:"
            "e1887a762452627a702619a44aae020941941a7fc069b43465d70a6807e26504"
        )
        for f in first.findings
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("identifier", "bad"),
        ("category", Category.SECURITY),
        ("severity", "info"),
        ("title", " "),
        ("description", ""),
        ("recommendation", ""),
    ],
)
def test_catalog_validation(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        cast(Callable[..., object], replace)(RULES[0], **{field: value})


def test_catalog_is_immutable() -> None:
    assert tuple(r.identifier for r in RULES) == ("TEST001", "TEST002")
    assert all(r.category == Category.TESTING and r.severity == Severity.INFO for r in RULES)
    field = "title"
    with pytest.raises(FrozenInstanceError):
        setattr(RULES[0], field, "changed")


def test_supported_grammar_and_target_warnings() -> None:
    result = TestingStaticAnalyzer().analyze(
        context({"test_api.py": "def test_api[T = int]():\n x = 'bad\\q'\n return x"})
    )
    assert result.state == AnalyzerState.COMPLETED and result.findings == ()
