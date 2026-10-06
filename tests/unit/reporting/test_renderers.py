"""Escaping, purity, full console text and cross-format semantic consistency."""

import json
from dataclasses import replace
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens import __version__
from repolens.domain.models import (
    AnalyzerResult,
    AnalyzerSpec,
    AnalyzerState,
    Category,
    Evidence,
    Finding,
    Repository,
    Severity,
)
from repolens.domain.report import AnalysisReport
from repolens.reporting import view
from repolens.reporting.console import render_console
from repolens.reporting.html_report import render_html
from repolens.reporting.json_report import render_json
from repolens.reporting.view import LIMITATIONS, ReportingError


class ParsedHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.text: list[str] = []
        self.rows: list[list[str]] = []
        self.cell: list[str] | None = None
        self.row: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag, dict(attrs)))
        if tag == "tr":
            self.row = []
        if tag in {"th", "td"}:
            self.cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"th", "td"}:
            assert self.row is not None and self.cell is not None
            self.row.append("".join(self.cell))
            self.cell = None
        if tag == "tr":
            assert self.row is not None
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data: str) -> None:
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)


def test_clean_console_exact_golden(clean_report: AnalysisReport) -> None:
    expected = (
        f"RepoLens {__version__} assessment\nRepository: fixture\nPolicy: fixture-v1\n"
        "Assessment: available\nOverall score: 100.00\n"
        "Findings: 0 (including INFO observations)\n\n"
        "Categories\n  testing: assessed; value 100\n    Completed: example\n"
        "    Unavailable: none\n    Non-applicable: none\n\nAnalyzers\n"
        "  example (testing): completed; findings 0\n\nFindings (canonical identifier order)\n"
        "  No findings observed in the completed supported scope.\n\nScope and limitations\n"
        "  Outside scope (unassessed): code_quality, security, documentation, "
        "repository_hygiene, ci_cd, maintainability\n"
        + "".join("  " + note + "\n" for note in LIMITATIONS)
    )
    assert render_console(clean_report) == expected
    assert "Perfect" not in expected and "All checks passed" not in expected


def test_console_retains_info_high_evidence_recommendations_and_canonical_order(
    mixed_report: AnalysisReport,
) -> None:
    text = render_console(mixed_report)
    assert "[INFO] TEST001: Test observation" in text
    assert "[HIGH] BANDIT-B602: Security observation" in text
    assert "src/app.py:3 - Controlled evidence" in text
    assert "src/peer.py - Related path" in text
    assert "Recommendation: Review intended behavior" in text
    assert text.index("ID: info;") < text.index("ID: security:a;") < text.index("ID: security:b;")


@pytest.mark.parametrize("mode", ["clean", "mixed", "incomplete", "not-applicable", "missing"])
def test_cross_format_core_semantics_agree(
    clean_report: AnalysisReport, mixed_report: AnalysisReport, mode: str
) -> None:
    report = mixed_report if mode == "mixed" else clean_report
    if mode in {"incomplete", "not-applicable"}:
        state = AnalyzerState.FAILED if mode == "incomplete" else AnalyzerState.NOT_APPLICABLE
        report = replace(
            report, results=(AnalyzerResult(report.plan[0], state, reason="Controlled reason"),)
        )
    elif mode == "missing":
        report = replace(report, results=())
    data = json.loads(render_json(report))
    console = render_console(report)
    html = render_html(report)
    parsed = ParsedHTML()
    parsed.feed(html)
    text = "".join(parsed.text)
    assert data["policy"]["identifier"] in console and data["policy"]["identifier"] in text
    value = data["assessment"]["overall_score"] or "unavailable"
    assert f"Overall score: {value}" in console
    assert "Overall score" in text and value in text
    assert f"Findings: {len(data['findings'])}" in console
    for index, category in enumerate(data["categories"], start=1):
        row = parsed.rows[index]
        expected_value = str(category["value"]) if category["value"] is not None else "unavailable"
        assert row[:3] == [category["category"], category["state"], expected_value]
        assert f"{category['category']}: {category['state']}; value {expected_value}" in console
        for deduction in category["deductions"]:
            assert deduction["rule_id"] in text and deduction["rule_id"] in console
            for identifier in deduction["finding_ids"]:
                assert identifier in text and identifier in console
    for analyzer in data["analyzers"]:
        displayed_state = analyzer["state"] or "missing"
        expected = f"{analyzer['identifier']} ({analyzer['category']}): {displayed_state}"
        assert expected in text and expected in console
        if analyzer["reason"] is not None:
            assert analyzer["reason"] in text and analyzer["reason"] in console
    for finding in data["findings"]:
        for key in ("identifier", "rule_id", "severity", "recommendation"):
            assert finding[key] in text
        assert f"[{finding['severity'].upper()}] {finding['rule_id']}" in console
        assert finding["identifier"] in console
    assert html == render_html(report) and console == render_console(report)
    assert "\r" not in html + console


def test_html_skeleton_accessibility_and_no_network_resources(clean_report: AnalysisReport) -> None:
    parsed = ParsedHTML()
    html = render_html(clean_report)
    parsed.feed(html)
    tags = [tag for tag, _ in parsed.tags]
    assert html.startswith("<!doctype html>\n") and html.endswith("</html>\n")
    assert ("html", {"lang": "en"}) in parsed.tags
    assert {
        "head",
        "title",
        "main",
        "header",
        "section",
        "table",
        "caption",
        "thead",
        "tbody",
    }.issubset(tags)
    assert (
        "script" not in tags and "img" not in tags and "link" not in tags and "iframe" not in tags
    )
    assert all(not ({"src", "href", "onerror", "onclick"} & set(attrs)) for _, attrs in parsed.tags)
    assert all(attrs.get("scope") in {"col", "row"} for tag, attrs in parsed.tags if tag == "th")
    assert "@media print" in html and "@media (max-width" in html and ":focus-visible" in html
    assert "http://" not in html and "https://" not in html and "url(" not in html


def test_all_html_values_escape_in_their_text_context_and_console_escapes_controls(
    clean_report: AnalysisReport,
) -> None:
    payload = (
        "<script>alert(1)</script><img src=x onerror=alert(1)></style>& <> \" '\n\x1b[31m\u202e"
    )
    owner = AnalyzerSpec(payload + "owner", Category.TESTING, "Controlled")
    finding = Finding(
        payload + "id",
        payload + "rule",
        owner.category,
        Severity.INFO,
        payload,
        payload,
        (Evidence(payload, "src/<img src=x onerror=alert(1)>.py", 1),),
        payload,
        owner.identifier,
    )
    report = replace(
        clean_report,
        repository=Repository("<img src=x onerror=alert(1)>"),
        plan=(owner,),
        results=(AnalyzerResult(owner, AnalyzerState.COMPLETED, (finding,)),),
        policy=replace(clean_report.policy, identifier=payload),
    )
    html = render_html(report)
    parsed = ParsedHTML()
    parsed.feed(html)
    tags = {tag for tag, _ in parsed.tags}
    assert "script" not in tags and "img" not in tags
    assert html.count("<style>") == 1
    assert "&lt;script&gt;" in html and "&quot;" in html and "&#x27;" in html
    assert view.visible_text(payload) in "".join(parsed.text)
    assert "src/<img src=x onerror=alert(1)>.py:1" in "".join(parsed.text)
    console = render_console(report)
    assert "\x1b" not in console and "\u202e" not in console
    assert "\\x1b" in console and "\\u202e" in console
    assert json.loads(render_json(report))["findings"][0]["description"] == payload


def test_analyzer_reason_is_escaped_consistently_without_html_execution(
    clean_report: AnalysisReport,
) -> None:
    payload = '<script>alert(1)</script> & "quoted"'
    report = replace(
        clean_report,
        results=(AnalyzerResult(clean_report.plan[0], AnalyzerState.FAILED, reason=payload),),
    )
    parsed = ParsedHTML()
    parsed.feed(render_html(report))
    assert "script" not in {tag for tag, _ in parsed.tags}
    assert payload in "".join(parsed.text)
    assert payload in render_console(report)
    assert json.loads(render_json(report))["analyzers"][0]["reason"] == payload


@pytest.mark.parametrize(
    "name",
    [
        "/home/user/project",
        "C:\\Users\\user\\project",
        "https://user:secret@github.com/o/r",
        "user:secret@host",
        ".",
        "..",
    ],
)
@pytest.mark.parametrize("renderer", [render_console, render_json, render_html])
def test_public_identity_check_prevents_path_or_credential_leaks(
    clean_report: AnalysisReport, name: str, renderer: object
) -> None:
    assert callable(renderer)
    with pytest.raises(ReportingError) as raised:
        renderer(replace(clean_report, repository=Repository(name)))
    assert name not in str(raised.value)
    assert "secret" not in str(raised.value)


@pytest.mark.parametrize("renderer", [render_console, render_json, render_html])
def test_serialization_limits_are_explicit_and_do_not_truncate(
    clean_report: AnalysisReport, renderer: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert callable(renderer)
    monkeypatch.setattr(view, "MAX_REPORT_BYTES", 8)
    with pytest.raises(ReportingError, match="byte limit"):
        renderer(clean_report)


def test_all_renderers_are_pure_and_never_rescore(
    mixed_report: AnalysisReport, monkeypatch: pytest.MonkeyPatch
) -> None:
    forbidden = MagicMock(side_effect=AssertionError("Rendering may not perform analysis or I/O"))
    with monkeypatch.context() as scope:
        scope.setattr(Path, "open", forbidden)
        scope.setattr("subprocess.Popen", forbidden)
        scope.setattr("socket.create_connection", forbidden)
        scope.setattr("os.getenv", forbidden)
        scope.setattr("repolens.domain.scoring.score_repository", forbidden)
        scope.setattr("repolens.domain.report.score_repository", forbidden)
        for renderer in (render_console, render_json, render_html):
            assert renderer(mixed_report)
    forbidden.assert_not_called()


@pytest.mark.parametrize("renderer", [render_console, render_json, render_html])
def test_semantically_identical_input_orders_have_identical_serialized_bytes(
    mixed_report: AnalysisReport, renderer: object
) -> None:
    assert callable(renderer)
    reordered = replace(
        mixed_report,
        plan=tuple(reversed(mixed_report.plan)),
        results=tuple(
            replace(result, findings=tuple(reversed(result.findings)))
            for result in reversed(mixed_report.results)
        ),
        policy=replace(
            mixed_report.policy,
            penalties=tuple(reversed(mixed_report.policy.penalties)),
            weights=tuple(reversed(mixed_report.policy.weights)),
        ),
    )
    assert renderer(mixed_report).encode("utf-8") == renderer(reordered).encode("utf-8")
