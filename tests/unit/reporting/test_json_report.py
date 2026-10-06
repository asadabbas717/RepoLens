"""Complete schema goldens, explicit state and exact deterministic JSON bytes."""

import json
from dataclasses import replace

import pytest

from repolens import __version__
from repolens.domain.models import AnalyzerResult, AnalyzerState, Evidence, Finding, Severity
from repolens.domain.report import AnalysisReport
from repolens.reporting.json_report import render_json, report_document
from repolens.reporting.view import LIMITATIONS


def test_complete_schema_one_golden(clean_report: AnalysisReport) -> None:
    expected = {
        "schema_version": "1",
        "tool": {"name": "RepoLens", "version": __version__},
        "repository": {"name": "fixture"},
        "policy": {
            "identifier": "fixture-v1",
            "scope": ["testing"],
            "penalties": [
                {"severity": s, "points": p}
                for s, p in (
                    ("info", 0),
                    ("low", 5),
                    ("medium", 15),
                    ("high", 30),
                    ("critical", 60),
                )
            ],
            "weights": [{"category": "testing", "weight": 1}],
        },
        "assessment": {
            "state": "available",
            "overall_score": "100.00",
            "finding_count": 0,
            "outside_scope": [
                "code_quality",
                "security",
                "documentation",
                "repository_hygiene",
                "ci_cd",
                "maintainability",
            ],
            "limitations": list(LIMITATIONS),
        },
        "categories": [
            {
                "category": "testing",
                "state": "assessed",
                "value": 100,
                "deductions": [],
                "completed_analyzers": ["example"],
                "unavailable_analyzers": [],
                "non_applicable_analyzers": [],
            }
        ],
        "analyzers": [
            {
                "identifier": "example",
                "category": "testing",
                "state": "completed",
                "reason": None,
                "finding_count": 0,
            }
        ],
        "findings": [],
    }
    encoded = render_json(clean_report)
    assert report_document(clean_report) == expected
    assert json.loads(encoded) == expected
    assert encoded == json.dumps(expected, ensure_ascii=True, allow_nan=False, indent=2) + "\n"
    assert encoded == render_json(clean_report)
    assert "\r" not in encoded


def test_mixed_findings_and_traceable_deductions_have_complete_golden_fields(
    mixed_report: AnalysisReport,
) -> None:
    data = json.loads(render_json(mixed_report))
    assert tuple(data) == (
        "schema_version",
        "tool",
        "repository",
        "policy",
        "assessment",
        "categories",
        "analyzers",
        "findings",
    )
    assert data["assessment"]["overall_score"] == "70.00"
    assert data["assessment"]["finding_count"] == 3
    assert data["categories"][1] == {
        "category": "security",
        "state": "assessed",
        "value": 55,
        "deductions": [
            {
                "rule_id": "BANDIT-B301",
                "severity": "medium",
                "points": 15,
                "finding_ids": ["security:b"],
            },
            {
                "rule_id": "BANDIT-B602",
                "severity": "high",
                "points": 30,
                "finding_ids": ["security:a"],
            },
        ],
        "completed_analyzers": ["security"],
        "unavailable_analyzers": [],
        "non_applicable_analyzers": [],
    }
    assert data["findings"][1] == {
        "identifier": "security:a",
        "rule_id": "BANDIT-B602",
        "category": "security",
        "severity": "high",
        "title": "Security observation",
        "description": "A static pattern",
        "evidence": [
            {"description": "Controlled evidence", "file_path": "src/app.py", "line_number": 3},
            {"description": "Related path", "file_path": "src/peer.py", "line_number": None},
        ],
        "recommendation": "Review intended behavior",
        "source_analyzer": "security",
    }
    assert [f["identifier"] for f in data["findings"]] == ["info", "security:a", "security:b"]
    assert [a["identifier"] for a in data["analyzers"]] == ["example", "security"]


@pytest.mark.parametrize(
    "state",
    [
        AnalyzerState.FAILED,
        AnalyzerState.SKIPPED,
        AnalyzerState.UNSUPPORTED,
        AnalyzerState.NOT_APPLICABLE,
    ],
)
def test_unavailable_and_non_applicable_states_are_not_fake_zero(
    clean_report: AnalysisReport, state: AnalyzerState
) -> None:
    owner = clean_report.plan[0]
    report = replace(
        clean_report, results=(AnalyzerResult(owner, state, reason="Controlled reason"),)
    )
    data = json.loads(render_json(report))
    assert data["assessment"] == {
        **json.loads(render_json(clean_report))["assessment"],
        "state": "unavailable",
        "overall_score": None,
    }
    category = data["categories"][0]
    assert category["value"] is None
    assert category["state"] == (
        "not_applicable" if state == AnalyzerState.NOT_APPLICABLE else "incomplete"
    )
    assert data["analyzers"] == [
        {
            "identifier": "example",
            "category": "testing",
            "state": state.value,
            "reason": "Controlled reason",
            "finding_count": 0,
        }
    ]


def test_missing_planned_result_has_null_state_without_inventing_analyzer_outcome(
    clean_report: AnalysisReport,
) -> None:
    data = json.loads(render_json(replace(clean_report, results=())))
    assert data["analyzers"] == [
        {
            "identifier": "example",
            "category": "testing",
            "state": None,
            "reason": "Planned analyzer result is missing",
            "finding_count": 0,
        }
    ]
    assert data["categories"][0]["unavailable_analyzers"] == ["example"]


@pytest.mark.parametrize(
    "severity,count,expected", [(Severity.INFO, 1, 100), (Severity.CRITICAL, 2, 0)]
)
def test_info_100_and_saturated_zero_preserve_findings_and_raw_deductions(
    clean_report: AnalysisReport, severity: Severity, count: int, expected: int
) -> None:
    owner = clean_report.plan[0]
    findings = tuple(
        Finding(
            f"f{i}",
            f"RULE{i}",
            owner.category,
            severity,
            "Observation",
            "Controlled",
            (Evidence("Evidence"),),
            "Review",
            owner.identifier,
        )
        for i in range(count)
    )
    report = replace(
        clean_report, results=(AnalyzerResult(owner, AnalyzerState.COMPLETED, findings),)
    )
    data = json.loads(render_json(report))
    assert data["categories"][0]["value"] == expected
    assert data["assessment"]["overall_score"] == f"{expected}.00"
    assert len(data["findings"]) == count
    assert sum(d["points"] for d in data["categories"][0]["deductions"]) == (
        0 if severity == Severity.INFO else 120
    )


def test_unicode_quotes_controls_and_html_are_data_not_json_structure(
    clean_report: AnalysisReport,
) -> None:
    payload = 'Unicode \u03bb "quoted" \\ newline\n</script><img src=x onerror=alert(1)>'
    owner = clean_report.plan[0]
    finding = Finding(
        "hostile",
        "RULE",
        owner.category,
        Severity.INFO,
        payload,
        payload,
        (Evidence(payload),),
        payload,
        owner.identifier,
    )
    report = replace(
        clean_report, results=(AnalyzerResult(owner, AnalyzerState.COMPLETED, (finding,)),)
    )
    encoded = render_json(report)
    data = json.loads(encoded)
    assert data["findings"][0]["title"] == payload
    assert data["findings"][0]["description"] == payload
    assert data["findings"][0]["recommendation"] == payload
    assert encoded.isascii()
    assert json.loads(encoded)["schema_version"] == "1"
