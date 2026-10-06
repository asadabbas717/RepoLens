"""Conservative GitHub Actions observations over immutable workflow snapshots."""

import hashlib
import re
from dataclasses import dataclass

from repolens.analyzers.workflow_yaml import SourceLocation, UnsupportedWorkflow, inspect_workflow
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerResult,
    AnalyzerSpec,
    AnalyzerState,
    Category,
    Evidence,
    Finding,
    Severity,
    require_enum,
    require_text,
)


@dataclass(frozen=True, slots=True)
class CIRule:
    identifier: str
    severity: Severity
    title: str
    description: str
    recommendation: str
    category: Category = Category.CI_CD

    def __post_init__(self) -> None:
        if (
            not isinstance(self.identifier, str)
            or re.fullmatch(r"CI[0-9]{3}", self.identifier) is None
        ):
            raise ValueError("CI rule IDs must use CI followed by three digits")
        require_enum(self.severity, Severity, "severity")
        if not isinstance(self.category, Category) or self.category != Category.CI_CD:
            raise ValueError("CI rules must belong to CI/CD")
        for field in ("title", "description", "recommendation"):
            require_text(getattr(self, field), field)


NO_WORKFLOWS = CIRule(
    "CI001",
    Severity.INFO,
    "No GitHub Actions workflows observed",
    "No GitHub Actions workflow files were observed in the eligible repository "
    "snapshot. Other CI providers may be present.",
    "Review the project's CI provider and workflow locations; this observation does "
    "not establish absence of CI.",
)
UNPINNED_REFERENCE = CIRule(
    "CI002",
    Severity.LOW,
    "Remote reference lacks full commit SHA form",
    "A recognized remote action or reusable workflow reference does not use the full "
    "40-hex commit SHA form. Its version is not fixed by this form.",
    "Consider pinning to a reviewed full commit SHA from the intended repository and "
    "maintain reviewed updates; a SHA does not establish safety.",
)
WRITE_ALL = CIRule(
    "CI003",
    Severity.LOW,
    "Explicit broad writable permissions declared",
    "A workflow or job declares literal write-all permissions. Effective access can "
    "differ due to job overrides and platform settings.",
    "Review whether narrower named permissions express the intended work; writable "
    "permissions may be legitimate.",
)
RULES = (NO_WORKFLOWS, UNPINNED_REFERENCE, WRITE_ALL)


def _finding(
    rule: CIRule, path: str | None = None, location: SourceLocation | None = None
) -> Finding:
    identifier = f"ci-static:{rule.identifier}"
    if path is not None and location is not None:
        key = f"{rule.identifier}\0{path}\0{location.line}:{location.column}"
        identifier += ":" + hashlib.sha256(key.encode("utf-8")).hexdigest()
    evidence = Evidence(
        rule.title + " in the eligible snapshot",
        path,
        location.line if location is not None else None,
    )
    return Finding(
        identifier,
        rule.identifier,
        rule.category,
        rule.severity,
        rule.title,
        rule.description,
        (evidence,),
        rule.recommendation,
        GitHubActionsAnalyzer.SPEC.identifier,
    )


class GitHubActionsAnalyzer:
    SPEC = AnalyzerSpec(
        "ci-static", Category.CI_CD, "Static bounded GitHub Actions configuration observations"
    )

    @property
    def spec(self) -> AnalyzerSpec:
        return self.SPEC

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        snapshot = context.workflows
        if snapshot is None:
            return AnalyzerResult(
                self.spec, AnalyzerState.FAILED, reason="Workflow data is unavailable"
            )
        if not snapshot.files:
            return AnalyzerResult(self.spec, AnalyzerState.COMPLETED, (_finding(NO_WORKFLOWS),))
        findings: list[Finding] = []
        try:
            for source in snapshot.files:
                observations = inspect_workflow(source)
                findings.extend(
                    _finding(UNPINNED_REFERENCE, source.path, location)
                    for location in observations.unpinned
                )
                findings.extend(
                    _finding(WRITE_ALL, source.path, location)
                    for location in observations.write_all
                )
        except UnsupportedWorkflow:
            return AnalyzerResult(
                self.spec,
                AnalyzerState.UNSUPPORTED,
                reason="Workflow configuration is outside the supported safe structural subset",
            )
        except MemoryError:
            return AnalyzerResult(
                self.spec,
                AnalyzerState.FAILED,
                reason="Workflow parsing exceeded available resources",
            )
        return AnalyzerResult(
            self.spec,
            AnalyzerState.COMPLETED,
            tuple(sorted(findings, key=lambda finding: finding.identifier)),
        )
