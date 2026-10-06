"""Requested reports survive incomplete/gate-failed scans without stdout noise."""

import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens import cli
from repolens.domain.models import AnalyzerResult, AnalyzerState
from repolens.domain.report import AnalysisReport
from repolens.infrastructure.report_output import OutputError
from repolens.reporting import view


@pytest.mark.parametrize("format_name", ["console", "json", "html"])
@pytest.mark.parametrize("mode", ["complete", "incomplete", "gate-failed"])
def test_every_format_is_emitted_before_assessment_exit(
    clean_report: AnalysisReport,
    format_name: str,
    mode: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = clean_report
    if mode == "incomplete":
        report = replace(
            report,
            results=(
                AnalyzerResult(
                    report.plan[0], AnalyzerState.UNSUPPORTED, reason="Controlled unavailable work"
                ),
            ),
        )
    elif mode == "gate-failed":
        from repolens.domain.models import Evidence, Finding, Severity

        owner = report.plan[0]
        finding = Finding(
            "f",
            "RULE",
            owner.category,
            Severity.LOW,
            "Observation",
            "Controlled",
            (Evidence("Evidence"),),
            "Review",
            owner.identifier,
        )
        report = replace(
            report, results=(AnalyzerResult(owner, AnalyzerState.COMPLETED, (finding,)),)
        )
    monkeypatch.setattr(cli, "_scan", MagicMock(return_value=report))
    argv = ["scan", ".", "--format", format_name, "--fail-under", "100"]
    destination = tmp_path / "report"
    if format_name == "html":
        argv += ["--output", str(destination)]
    assert cli.run(argv) == (0 if mode == "complete" else 1)
    output = capsys.readouterr()
    assert not output.err
    if format_name == "json":
        data = json.loads(output.out)
        assert data["assessment"]["overall_score"] == (
            None if mode == "incomplete" else "95.00" if mode == "gate-failed" else "100.00"
        )
        assert "Score gate" not in output.out
    elif format_name == "html":
        assert not output.out
        assert destination.read_bytes().startswith(b"<!doctype html>\n")
    else:
        assert "Overall score" in output.out and "Score gate:" in output.out


@pytest.mark.parametrize("format_name", ["console", "json", "html"])
def test_explicit_output_writes_only_file_with_utf8_lf(
    clean_report: AnalysisReport,
    format_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_scan", MagicMock(return_value=clean_report))
    destination = tmp_path / "report"
    assert cli.run(["scan", ".", "--format", format_name, "--output", str(destination)]) == 0
    assert capsys.readouterr() == ("", "")
    assert destination.read_bytes().endswith(b"\n")
    assert b"\r" not in destination.read_bytes()


@pytest.mark.parametrize("mode", ["html-without-output", "existing", "directory", "missing-parent"])
def test_output_arguments_fail_before_acquisition(
    mode: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scan = MagicMock()
    monkeypatch.setattr(cli, "_scan", scan)
    path = tmp_path / "report"
    argv = ["scan", ".", "--format", "html"]
    if mode == "existing":
        path.write_bytes(b"user file")
    elif mode == "directory":
        path.mkdir()
    elif mode == "missing-parent":
        path = tmp_path / "missing/report"
    if mode != "html-without-output":
        argv += ["--output", str(path)]
    assert cli.run(argv) == 2
    output = capsys.readouterr()
    assert (
        not output.out and output.err == "repolens: report output could not be completed safely.\n"
    )
    scan.assert_not_called()


@pytest.mark.parametrize("failure", ["publication", "serialization-limit", "programming"])
def test_rendering_or_publication_failure_supersedes_assessment_exit(
    clean_report: AnalysisReport,
    failure: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "_scan", MagicMock(return_value=clean_report))
    if failure == "publication":
        monkeypatch.setattr(
            cli, "publish_report", MagicMock(side_effect=OutputError("secret OS diagnostics"))
        )
    elif failure == "serialization-limit":
        monkeypatch.setattr(view, "MAX_REPORT_BYTES", 1)
    else:
        monkeypatch.setattr(
            cli, "render_json", MagicMock(side_effect=RuntimeError("secret programming failure"))
        )
    destination = tmp_path / "report"
    assert cli.run(["scan", ".", "--format", "json", "--output", str(destination)]) == (
        3 if failure == "programming" else 2
    )
    output = capsys.readouterr()
    assert not output.out and "secret" not in output.err
    assert not destination.exists()


@pytest.mark.parametrize("failure", ["write", "short-write", "flush"])
def test_stdout_io_errors_are_sanitized(
    clean_report: AnalysisReport, failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "_scan", MagicMock(return_value=clean_report))
    stream = MagicMock()
    stream.buffer.write.return_value = 1 if failure == "short-write" else None
    if failure == "write":
        stream.buffer.write.side_effect = OSError("secret stdout")
    elif failure == "flush":
        stream.buffer.write.side_effect = lambda raw: len(raw)
        stream.buffer.flush.side_effect = OSError("secret flush")
    monkeypatch.setattr(sys, "stdout", stream)
    error = MagicMock()
    monkeypatch.setattr(sys, "stderr", error)
    assert cli.run(["scan", ".", "--format", "json"]) == 2
    assert "secret" not in "".join(str(call) for call in error.write.call_args_list)


def test_unknown_format_is_sanitized_before_acquisition(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scan = MagicMock()
    monkeypatch.setattr(cli, "_scan", scan)
    with pytest.raises(SystemExit) as raised:
        cli.run(["scan", ".", "--format", "secret-invalid-format"])
    assert raised.value.code == 2
    output = capsys.readouterr()
    assert not output.out and "secret" not in output.err
    scan.assert_not_called()
