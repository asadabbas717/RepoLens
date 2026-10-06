"""Public shell outcomes, stable declared plan and hostile-argument handling."""

import argparse
import sys
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from repolens import __version__, cli
from repolens.analyzers.python_security import PythonSecurityAnalyzer
from repolens.application.scoring_policy import PYTHON_STATIC_V1
from repolens.domain.models import (
    AnalyzerResult,
    AnalyzerState,
    Category,
    Evidence,
    Finding,
    Repository,
    Severity,
)
from repolens.domain.report import AnalysisReport
from repolens.infrastructure.errors import (
    AcquisitionError,
    GitFailed,
    GitTimedOut,
    GitUnavailable,
    InvalidSource,
    TraversalLimitExceeded,
)
from repolens.infrastructure.repository_source import SourceKind


def assessment(
    state: AnalyzerState = AnalyzerState.COMPLETED, *, missing: bool = False
) -> AnalysisReport:
    plan = cli.default_analyzer_plan(MagicMock())
    results: list[AnalyzerResult] = []
    for spec in plan.specs:
        if spec.identifier == "python-security" and missing:
            continue
        if spec.identifier == "python-security" and state != AnalyzerState.COMPLETED:
            results.append(AnalyzerResult(spec, state, reason="Controlled unavailable work"))
        elif spec.category == Category.CODE_QUALITY:
            finding = Finding(
                "python-static:example",
                "PY001",
                spec.category,
                Severity.LOW,
                "Controlled observation",
                "Controlled AST observation",
                (Evidence("Controlled structural evidence"),),
                "Review",
                spec.identifier,
            )
            results.append(AnalyzerResult(spec, AnalyzerState.COMPLETED, (finding,)))
        else:
            results.append(AnalyzerResult(spec, AnalyzerState.COMPLETED))
    return AnalysisReport(
        Repository("reference-repository"), plan.specs, tuple(results), PYTHON_STATIC_V1
    )


def test_default_plan_is_exact_stable_and_preserves_product_policy() -> None:
    plan = cli.default_analyzer_plan(MagicMock())
    assert tuple((s.identifier, s.category) for s in plan.specs) == (
        ("ci-static", Category.CI_CD),
        ("python-security", Category.SECURITY),
        ("python-static", Category.CODE_QUALITY),
        ("repository-hygiene", Category.REPOSITORY_HYGIENE),
        ("testing-static", Category.TESTING),
    )
    assert PythonSecurityAnalyzer.SPEC in plan.specs
    assert assessment().policy is PYTHON_STATIC_V1


@pytest.mark.parametrize("argv", [["--help"], ["--version"], ["scan", "--help"]])
def test_help_and_version_have_no_acquisition_or_tool_side_effects(
    argv: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    forbidden = MagicMock(side_effect=AssertionError("Help must not acquire or analyze"))
    for name in ("RepositorySource", "BanditRunner", "snapshot_analysis_context", "_scan"):
        monkeypatch.setattr(cli, name, forbidden)
    with pytest.raises(SystemExit) as raised:
        cli.run(argv)
    assert raised.value.code == 0
    output = capsys.readouterr()
    assert not output.err
    if argv == ["--version"]:
        assert output.out == f"repolens {__version__}\n"
    else:
        assert "repolens-python-static-v1" in output.out
        assert "Dependency vulnerability auditing" in output.out
        assert "no target code" in output.out
        assert "GitHub" in output.out
    forbidden.assert_not_called()


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["unknown-secret"],
        ["scan"],
        ["--secret-option"],
        ["scan", ".", "--secret-token"],
        ["scan", ".", "--fail-u", "50"],
        ["scan", ".", "another-secret-source"],
    ],
)
def test_invalid_invocations_are_sanitized_and_do_not_acquire(
    argv: list[str], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    forbidden = MagicMock(side_effect=AssertionError("Invalid arguments must not acquire"))
    monkeypatch.setattr(cli, "_scan", forbidden)
    with pytest.raises(SystemExit) as raised:
        cli.run(argv)
    assert raised.value.code == 2
    output = capsys.readouterr()
    assert not output.out
    assert "invalid arguments" in output.err
    assert "secret" not in output.err
    forbidden.assert_not_called()


@pytest.mark.parametrize(
    "value",
    [
        "NaN",
        "Infinity",
        "-1",
        "101",
        "abc-secret",
        "90%",
        "90.001",
        "1e2",
        "+90",
        " 90",
        "90.",
        ".5",
        "",
        "\uff19\uff10",
    ],
)
def test_invalid_thresholds_fail_before_acquisition(
    value: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    forbidden = MagicMock()
    monkeypatch.setattr(cli, "_scan", forbidden)
    with pytest.raises(SystemExit) as raised:
        cli.run(["scan", ".", "--fail-under", value])
    assert raised.value.code == 2
    output = capsys.readouterr()
    assert not output.out
    assert "secret" not in output.err
    forbidden.assert_not_called()


@pytest.mark.parametrize("value", ["0", "0.00", "100", "100.00", "85", "85.5", "85.50", "00085.50"])
def test_thresholds_use_exact_decimal_values(value: str) -> None:
    assert cli._threshold(value) == Decimal(value)
    assert isinstance(cli._threshold(value), Decimal)


@pytest.mark.parametrize(
    "threshold, exit_code",
    [(None, 0), ("0", 0), ("98.74", 0), ("98.75", 0), ("98.76", 1), ("100", 1)],
)
def test_score_gate_above_equal_below_and_extremes(
    threshold: str | None,
    exit_code: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scan = MagicMock(return_value=assessment())
    monkeypatch.setattr(cli, "_scan", scan)
    argv = ["scan", "."]
    if threshold is not None:
        argv += ["--fail-under", threshold]
    assert cli.run(argv) == exit_code
    output = capsys.readouterr()
    assert not output.err
    assert "Assessment: available" in output.out
    assert "Overall score: 98.75" in output.out
    assert "Findings: 1" in output.out
    assert "not included" in output.out
    assert "secret" not in output.out
    if threshold is not None:
        assert "Score gate: " + ("met" if exit_code == 0 else "not met") in output.out
    scan.assert_called_once()


@pytest.mark.parametrize(
    "state", [AnalyzerState.FAILED, AnalyzerState.SKIPPED, AnalyzerState.UNSUPPORTED]
)
@pytest.mark.parametrize("threshold", [None, "0", "100"])
def test_unavailable_analysis_is_never_a_successful_gate(
    state: AnalyzerState,
    threshold: str | None,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_scan", MagicMock(return_value=assessment(state)))
    argv = ["scan", "."] + ([] if threshold is None else ["--fail-under", threshold])
    assert cli.run(argv) == 1
    output = capsys.readouterr()
    assert not output.err
    assert "Assessment: unavailable" in output.out
    assert "Overall score: unavailable" in output.out
    assert f"python-security (security): {state.value}" in output.out
    assert "secret" not in output.out
    if threshold is not None:
        assert "Score gate: unavailable" in output.out


def test_missing_planned_result_remains_visible_and_incomplete(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_scan", MagicMock(return_value=assessment(missing=True)))
    assert cli.run(["scan", "."]) == 1
    assert "python-security (security): missing" in capsys.readouterr().out


@pytest.mark.parametrize(
    "value, kind, canonical",
    [
        (".", SourceKind.LOCAL, "."),
        ("folder/repo", SourceKind.LOCAL, "folder/repo"),
        ("C:/projects/example", SourceKind.LOCAL, "C:/projects/example"),
        ("C:\\projects\\example", SourceKind.LOCAL, "C:\\projects\\example"),
        ("/c/projects/example", SourceKind.LOCAL, "/c/projects/example"),
        (
            "https://github.com/owner/project",
            SourceKind.GITHUB,
            "https://github.com/owner/project.git",
        ),
        (
            "https://github.com/owner/project.git/",
            SourceKind.GITHUB,
            "https://github.com/owner/project.git",
        ),
    ],
)
def test_source_classification_preserves_windows_paths_and_canonicalizes_urls(
    value: str, kind: SourceKind, canonical: str
) -> None:
    source = cli._classify_source(value)
    assert source.kind == kind
    assert source.value == canonical


@pytest.mark.parametrize(
    "source",
    [
        "http://github.com/o/r",
        "ssh://github.com/o/r",
        "file:///secret-path",
        "git@github.com:o/r",
        "https://github.com/secret-token@o/r",
        "https://user:secret@github.com/o/r",
        "https://github.com/o/r/tree/main",
        "https://github.com/o/r?secret=token",
        "https://elsewhere.invalid/o/r",
        " https://github.com/o/r",
        "",
        "\nsecret",
        "dir\x00secret",
    ],
)
def test_invalid_url_and_source_spelling_never_reaches_acquisition(
    source: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    forbidden = MagicMock()
    monkeypatch.setattr(cli, "RepositorySource", forbidden)
    assert cli.run(["scan", source]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert "failed safely" in output.err
    assert "secret" not in output.err
    forbidden.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        AcquisitionError,
        InvalidSource,
        GitFailed,
        GitTimedOut,
        GitUnavailable,
        TraversalLimitExceeded,
    ],
)
def test_acquisition_failures_are_sanitized_input_outcomes(
    error: type[AcquisitionError],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_scan", MagicMock(side_effect=error("secret raw diagnostic")))
    assert cli.run(["scan", "."]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert output.err == "repolens: source acquisition or input processing failed safely.\n"


def test_unexpected_composition_failure_is_sanitized_internal_outcome(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli, "_scan", MagicMock(side_effect=RuntimeError("secret programming failure"))
    )
    assert cli.run(["scan", "."]) == 3
    output = capsys.readouterr()
    assert not output.out
    assert output.err == "repolens: unexpected internal failure.\n"


def test_unexpected_parser_failure_is_also_internal_and_sanitized(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        cli, "_parser", MagicMock(side_effect=RuntimeError("secret parser failure"))
    )
    assert cli.run(["scan", "."]) == 3
    assert capsys.readouterr().err == "repolens: unexpected internal failure.\n"


@pytest.mark.parametrize(
    "namespace",
    [
        argparse.Namespace(source=1, fail_under=None, output=None, format="console"),
        argparse.Namespace(source=".", fail_under=85.0, output=None, format="console"),
        argparse.Namespace(source=".", fail_under=None, output=1, format="console"),
        argparse.Namespace(source=".", fail_under=None, output=None, format="unknown"),
    ],
)
def test_invalid_internal_namespace_is_not_accepted_as_user_input(
    namespace: argparse.Namespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    parser = MagicMock()
    parser.parse_args.return_value = namespace
    monkeypatch.setattr(cli, "_parser", MagicMock(return_value=parser))
    assert cli.run(["scan", "."]) == 3
    assert "unexpected internal" in capsys.readouterr().err


@pytest.mark.parametrize("signal", [KeyboardInterrupt(), SystemExit(7)])
def test_cancellation_and_system_exit_are_not_converted_to_internal_errors(
    signal: BaseException, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "_scan", MagicMock(side_effect=signal))
    with pytest.raises(type(signal)):
        cli.run(["scan", "."])
    assert capsys.readouterr() == ("", "")


def test_console_wrapper_uses_real_arguments_and_exit_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = MagicMock(return_value=1)
    monkeypatch.setattr(cli, "run", run)
    monkeypatch.setattr(sys, "argv", ["repolens", "scan", ".", "--fail-under", "85"])
    with pytest.raises(SystemExit) as raised:
        cli.main()
    assert raised.value.code == 1
    run.assert_called_once_with(["scan", ".", "--fail-under", "85"])
