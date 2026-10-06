"""Standalone semantic HTML: every value escaped, no active/network resources."""

from collections.abc import Iterator
from html import escape

from repolens import __version__
from repolens.domain.models import Category, Severity
from repolens.domain.report import AnalysisReport
from repolens.reporting.view import LIMITATIONS, SCHEMA_VERSION, bounded_text, project, visible_text

_STYLE = """
body { margin: 0; color: #20242a; background: #fff; font: 1rem/1.6 system-ui, sans-serif; }
main { max-width: 72rem; margin: auto; padding: 1.5rem; }
h1, h2, h3 { line-height: 1.25; }
section { margin-top: 2rem; }
article { border: 1px solid #707780; border-radius: .3rem; padding: 1rem; margin: 1rem 0; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; vertical-align: top; padding: .5rem; border: 1px solid #707780; }
caption { text-align: left; font-weight: bold; margin-bottom: .5rem; }
th { background: #edf0f3; }
.table-wrap { overflow-x: auto; }
.table-wrap:focus-visible { outline: 3px solid #174ca4; outline-offset: 3px; }
td, p, li, dd { overflow-wrap: anywhere; }
dt { font-weight: bold; }
dd { margin: 0 0 .5rem; }
@media (max-width: 40rem) { main { padding: .75rem; } th, td { padding: .3rem; } }
@media print { main { max-width: none; padding: 0; } article { break-inside: avoid; }
  .table-wrap { overflow: visible; } th { background: #fff; } }
""".strip()


def _e(value: str | int) -> str:
    return escape(visible_text(str(value)), quote=True)


def _parts(report: AnalysisReport) -> Iterator[str]:
    view = project(report)
    yield '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    yield '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
    yield f"<title>RepoLens assessment: {_e(view.repository_name)}</title>\n"
    yield f"<style>\n{_STYLE}\n</style>\n</head>\n<body>\n<main>\n<header>\n"
    yield "<h1>RepoLens assessment</h1>\n<dl>\n"
    for label, value in (
        ("Repository", view.repository_name),
        ("Tool version", __version__),
        ("Report schema", SCHEMA_VERSION),
        ("Policy", report.policy.identifier),
        ("Assessment", "available" if report.score.value is not None else "unavailable"),
        (
            "Overall score",
            str(report.score.value) if report.score.value is not None else "unavailable",
        ),
        ("Findings", str(len(report.findings))),
    ):
        yield f"<dt>{_e(label)}</dt><dd>{_e(value)}</dd>\n"
    yield "</dl>\n</header>\n<section>\n<h2>Policy and scope</h2>\n"
    weights = {entry.category: entry.weight for entry in report.policy.weights}
    penalties = {entry.severity: entry.points for entry in report.policy.penalties}
    yield (
        "<p>Weights: "
        + _e(", ".join(f"{c.value}={weights[c]}" for c in Category if c in weights))
        + "</p>\n"
    )
    yield (
        "<p>Severity penalties: "
        + _e(", ".join(f"{s.value}={penalties[s]}" for s in Severity))
        + "</p>\n"
    )
    yield (
        "<p>Outside scope (unassessed): "
        + _e(", ".join(c.value for c in view.outside_scope) or "none")
        + "</p>\n</section>\n"
    )
    yield (
        '<section>\n<h2 id="categories-title">Categories</h2>\n'
        '<div class="table-wrap" role="region" '
        'aria-labelledby="categories-title" tabindex="0">\n'
    )
    yield "<table>\n<caption>Declared category assessment</caption>\n<thead><tr>"
    for title in (
        "Category",
        "State",
        "Value",
        "Completed analyzers",
        "Unavailable analyzers",
        "Non-applicable analyzers",
    ):
        yield f'<th scope="col">{_e(title)}</th>'
    yield "</tr></thead>\n<tbody>\n"
    for score in report.score.categories:
        yield f'<tr><th scope="row">{_e(score.category.value)}</th>'
        for value in (
            score.state.value,
            str(score.value) if score.value is not None else "unavailable",
            ", ".join(score.completed_analyzers) or "none",
            ", ".join(score.unavailable_analyzers) or "none",
            ", ".join(score.non_applicable_analyzers) or "none",
        ):
            yield f"<td>{_e(value)}</td>"
        yield "</tr>\n"
    yield "</tbody>\n</table>\n</div>\n</section>\n<section>\n<h2>Deductions</h2>\n"
    for score in report.score.categories:
        for deduction in score.deductions:
            yield (
                f"<p>{_e(score.category.value)} / {_e(deduction.rule_id)}: "
                f"{_e(deduction.severity.value)}, {_e(deduction.points)} points.<br>"
                f"Finding IDs: {_e(', '.join(deduction.finding_ids))}</p>\n"
            )
    yield (
        "<p>Raw rule deductions remain visible even at the category floor "
        "or while assessment is incomplete.</p>\n</section>\n"
    )
    yield "<section>\n<h2>Analyzers</h2>\n<ul>\n"
    for analyzer in view.analyzers:
        yield (
            f"<li>{_e(analyzer.spec.identifier)} ({_e(analyzer.spec.category.value)}): "
            f"{_e(analyzer.state or 'missing')}; findings {_e(analyzer.finding_count)}. "
            f"Reason: {_e(analyzer.reason or 'none')}</li>\n"
        )
    yield "</ul>\n</section>\n<section>\n<h2>Findings</h2>\n"
    if not report.findings:
        yield "<p>No findings observed in the completed supported scope.</p>\n"
    for index, finding in enumerate(report.findings):
        yield (
            f'<article id="finding-{index}">\n<h3>[{_e(finding.severity.value.upper())}] '
            f"{_e(finding.rule_id)}: {_e(finding.title)}</h3>\n"
        )
        yield "<dl>\n"
        for label, value in (
            ("Identifier", finding.identifier),
            ("Category", finding.category.value),
            ("Severity", finding.severity.value),
            ("Source analyzer", finding.source_analyzer),
            ("Observation", finding.description),
            ("Recommendation", finding.recommendation),
        ):
            yield f"<dt>{_e(label)}</dt><dd>{_e(value)}</dd>\n"
        yield "</dl>\n<h4>Evidence</h4>\n<ul>\n"
        for evidence in finding.evidence:
            location = evidence.file_path or "repository"
            if evidence.line_number is not None:
                location += f":{evidence.line_number}"
            yield f"<li>{_e(location)}: {_e(evidence.description)}</li>\n"
        yield "</ul>\n</article>\n"
    yield "</section>\n<section>\n<h2>Limitations</h2>\n<ul>\n"
    for limitation in LIMITATIONS:
        yield f"<li>{_e(limitation)}</li>\n"
    yield "</ul>\n</section>\n</main>\n</body>\n</html>\n"


def render_html(report: AnalysisReport) -> str:
    return bounded_text(_parts(report))
