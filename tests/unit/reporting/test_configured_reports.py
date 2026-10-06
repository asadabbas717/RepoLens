"""Schema-1 additive metadata keeps every old field and shares escaped scope facts."""

import json
from dataclasses import replace
from decimal import Decimal
from html.parser import HTMLParser

from repolens.domain.assessment_configuration import (
    AppliedConfiguration,
    ExclusionPolicy,
    GateSettings,
)
from repolens.domain.models import Severity
from repolens.domain.report import AnalysisReport
from repolens.reporting.console import render_console
from repolens.reporting.html_report import render_html
from repolens.reporting.json_report import render_json


class Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: set[str] = set()
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.add(tag)
        assert "onerror" not in dict(attrs)

    def handle_data(self, data: str) -> None:
        self.text.append(data)


def test_metadata_is_additive_and_all_old_fields_types_and_semantics_stay_intact(
    clean_report: AnalysisReport,
) -> None:
    metadata = AppliedConfiguration(
        1,
        ExclusionPolicy(("generated/", "src/<img src=x onerror=alert(1)>.py")),
        ("PY002",),
        GateSettings(Decimal("85.5"), Severity.HIGH),
    )
    configured = replace(clean_report, configuration=metadata)
    old = json.loads(render_json(clean_report))
    new = json.loads(render_json(configured))
    assert new["schema_version"] == "1"
    assert tuple(new) == (*old.keys(), "configuration")
    assert new.pop("configuration") == {
        "schema_version": 1,
        "exclusions": ["generated/", "src/<img src=x onerror=alert(1)>.py"],
        "disabled_rules": ["PY002"],
        "gates": {"fail_under": "85.50", "fail_on_severity": "high"},
    }
    assert new == old
    console = render_console(configured)
    parsed = Collector()
    parsed.feed(render_html(configured))
    html_text = "".join(parsed.text)
    for value in (*metadata.exclusions.entries, "PY002", "85.50", "high"):
        assert value in console and value in html_text
    assert "img" not in parsed.tags
    assert "Configuration schema: 1" in console
    assert render_json(configured) == render_json(
        replace(
            configured,
            configuration=AppliedConfiguration(
                1,
                ExclusionPolicy(tuple(reversed(metadata.exclusions.entries))),
                metadata.disabled_rules,
                metadata.gates,
            ),
        )
    )


def test_cli_only_gate_metadata_has_null_config_schema_and_unset_fields(
    clean_report: AnalysisReport,
) -> None:
    report = replace(
        clean_report, configuration=AppliedConfiguration(gates=GateSettings(Decimal("0")))
    )
    metadata = json.loads(render_json(report))["configuration"]
    assert metadata == {
        "schema_version": None,
        "exclusions": [],
        "disabled_rules": [],
        "gates": {"fail_under": "0.00", "fail_on_severity": None},
    }
    assert "Configuration schema: CLI only" in render_console(report)
    assert "configuration" not in json.loads(render_json(clean_report))
