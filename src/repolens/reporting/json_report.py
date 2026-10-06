"""Intentional JSON schema 1; exact score strings, domain state and traceability."""

import json
from itertools import chain

from repolens import __version__
from repolens.domain.models import Category, Severity
from repolens.domain.report import AnalysisReport
from repolens.reporting.view import LIMITATIONS, SCHEMA_VERSION, bounded_text, project

type JSONValue = str | int | bool | list[JSONValue] | dict[str, JSONValue] | None


def report_document(report: AnalysisReport) -> dict[str, JSONValue]:
    """Build public fields explicitly; never dump internal dataclasses."""
    view = project(report)
    penalties = {entry.severity: entry.points for entry in report.policy.penalties}
    weights = {entry.category: entry.weight for entry in report.policy.weights}
    document: dict[str, JSONValue] = {
        "schema_version": SCHEMA_VERSION,
        "tool": {"name": "RepoLens", "version": __version__},
        "repository": {"name": view.repository_name},
        "policy": {
            "identifier": report.policy.identifier,
            "scope": [category.value for category in Category if category in weights],
            "penalties": [
                {"severity": severity.value, "points": penalties[severity]} for severity in Severity
            ],
            "weights": [
                {"category": category.value, "weight": weights[category]}
                for category in Category
                if category in weights
            ],
        },
        "assessment": {
            "state": "available" if report.score.value is not None else "unavailable",
            "overall_score": str(report.score.value) if report.score.value is not None else None,
            "finding_count": len(report.findings),
            "outside_scope": [category.value for category in view.outside_scope],
            "limitations": list(LIMITATIONS),
        },
        "categories": [
            {
                "category": score.category.value,
                "state": score.state.value,
                "value": score.value,
                "deductions": [
                    {
                        "rule_id": deduction.rule_id,
                        "severity": deduction.severity.value,
                        "points": deduction.points,
                        "finding_ids": list(deduction.finding_ids),
                    }
                    for deduction in score.deductions
                ],
                "completed_analyzers": list(score.completed_analyzers),
                "unavailable_analyzers": list(score.unavailable_analyzers),
                "non_applicable_analyzers": list(score.non_applicable_analyzers),
            }
            for score in report.score.categories
        ],
        "analyzers": [
            {
                "identifier": analyzer.spec.identifier,
                "category": analyzer.spec.category.value,
                "state": analyzer.state,
                "reason": analyzer.reason,
                "finding_count": analyzer.finding_count,
            }
            for analyzer in view.analyzers
        ],
        "findings": [
            {
                "identifier": finding.identifier,
                "rule_id": finding.rule_id,
                "category": finding.category.value,
                "severity": finding.severity.value,
                "title": finding.title,
                "description": finding.description,
                "evidence": [
                    {
                        "description": evidence.description,
                        "file_path": evidence.file_path,
                        "line_number": evidence.line_number,
                    }
                    for evidence in finding.evidence
                ],
                "recommendation": finding.recommendation,
                "source_analyzer": finding.source_analyzer,
            }
            for finding in report.findings
        ],
    }
    if report.configuration is not None:
        applied = report.configuration
        document["configuration"] = {
            "schema_version": applied.schema_version,
            "exclusions": list(applied.exclusions.entries),
            "disabled_rules": list(applied.disabled_rules),
            "gates": {
                "fail_under": str(applied.gates.fail_under)
                if applied.gates.fail_under is not None
                else None,
                "fail_on_severity": applied.gates.fail_on_severity.value
                if applied.gates.fail_on_severity is not None
                else None,
            },
        }
    return document


def render_json(report: AnalysisReport) -> str:
    encoder = json.JSONEncoder(ensure_ascii=True, allow_nan=False, indent=2)
    return bounded_text(chain(encoder.iterencode(report_document(report)), ("\n",)))
