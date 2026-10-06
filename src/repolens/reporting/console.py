"""Full deterministic plain text; no color, terminal probing or truncation."""

from collections.abc import Iterator

from repolens import __version__
from repolens.domain.report import AnalysisReport
from repolens.reporting.view import LIMITATIONS, bounded_text, project, visible_text


def _lines(report: AnalysisReport) -> Iterator[str]:
    view = project(report)
    yield f"RepoLens {__version__} assessment"
    yield f"Repository: {visible_text(view.repository_name)}"
    yield f"Policy: {visible_text(report.policy.identifier)}"
    yield "Assessment: " + ("available" if report.score.value is not None else "unavailable")
    value = str(report.score.value) if report.score.value is not None else "unavailable"
    yield f"Overall score: {value}"
    yield f"Findings: {len(report.findings)} (including INFO observations)"
    yield ""
    if report.configuration is not None:
        applied = report.configuration
        yield "Applied configuration"
        version = str(applied.schema_version) if applied.schema_version is not None else "CLI only"
        yield f"  Configuration schema: {version}"
        yield "  Exclusions: " + (
            ", ".join(visible_text(e) for e in applied.exclusions.entries) or "none"
        )
        yield "  Disabled rules: " + (", ".join(applied.disabled_rules) or "none")
        threshold = (
            str(applied.gates.fail_under) if applied.gates.fail_under is not None else "unset"
        )
        severity = (
            applied.gates.fail_on_severity.value
            if applied.gates.fail_on_severity is not None
            else "unset"
        )
        yield f"  fail_under: {threshold}"
        yield f"  fail_on_severity: {severity}"
        yield "  Findings and scores describe this configured eligible scope only."
        yield ""
    yield "Categories"
    for score in report.score.categories:
        value = str(score.value) if score.value is not None else "unavailable"
        yield f"  {score.category.value}: {score.state.value}; value {value}"
        for label, identifiers in (
            ("Completed", score.completed_analyzers),
            ("Unavailable", score.unavailable_analyzers),
            ("Non-applicable", score.non_applicable_analyzers),
        ):
            yield f"    {label}: " + (", ".join(visible_text(i) for i in identifiers) or "none")
        for deduction in score.deductions:
            yield (
                f"    Deduction {visible_text(deduction.rule_id)}: "
                f"{deduction.severity.value}; {deduction.points} points"
            )
            yield "      Findings: " + ", ".join(visible_text(i) for i in deduction.finding_ids)
    yield ""
    yield "Analyzers"
    for analyzer in view.analyzers:
        yield (
            f"  {visible_text(analyzer.spec.identifier)} ({analyzer.spec.category.value}): "
            f"{analyzer.state or 'missing'}; findings {analyzer.finding_count}"
        )
        if analyzer.reason is not None:
            yield "    Reason: " + visible_text(analyzer.reason)
    yield ""
    yield "Findings (canonical identifier order)"
    if not report.findings:
        yield "  No findings observed in the completed supported scope."
    for finding in report.findings:
        yield (
            f"  [{finding.severity.value.upper()}] {visible_text(finding.rule_id)}: "
            f"{visible_text(finding.title)}"
        )
        yield (
            f"    ID: {visible_text(finding.identifier)}; category: {finding.category.value}; "
            f"source: {visible_text(finding.source_analyzer)}"
        )
        yield "    Observation: " + visible_text(finding.description)
        for evidence in finding.evidence:
            location = evidence.file_path or "repository"
            if evidence.line_number is not None:
                location += f":{evidence.line_number}"
            yield f"    Evidence: {visible_text(location)} - {visible_text(evidence.description)}"
        yield "    Recommendation: " + visible_text(finding.recommendation)
    yield ""
    yield "Scope and limitations"
    yield "  Outside scope (unassessed): " + (
        ", ".join(c.value for c in view.outside_scope) or "none"
    )
    for limitation in LIMITATIONS:
        yield "  " + limitation


def render_console(report: AnalysisReport) -> str:
    return bounded_text(line + "\n" for line in _lines(report))
