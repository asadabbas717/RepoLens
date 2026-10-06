"""Process gates over existing active findings/score, never new score policy."""

from dataclasses import dataclass

from repolens.domain.assessment_configuration import GateSettings
from repolens.domain.models import Severity
from repolens.domain.report import AnalysisReport


@dataclass(frozen=True, slots=True)
class GateOutcome:
    score: str | None
    severity: str | None
    failed: bool


def evaluate_gates(report: AnalysisReport, settings: GateSettings) -> GateOutcome:
    value = report.score.value
    score = None
    severity = None
    if settings.fail_under is not None:
        score = (
            "unavailable" if value is None else "not met" if value < settings.fail_under else "met"
        )
    if settings.fail_on_severity is not None:
        rank = tuple(Severity).index(settings.fail_on_severity)
        triggered = any(tuple(Severity).index(f.severity) >= rank for f in report.findings)
        severity = "not met" if triggered else "met"
    return GateOutcome(
        score, severity, value is None or score == "not met" or severity == "not met"
    )
