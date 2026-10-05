"""Two conservative repository-hygiene signals over eligible file paths only."""

import hashlib
import re
from dataclasses import dataclass

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
class HygieneRule:
    """Metadata for shipped hygiene rules, not a generic rule engine."""

    identifier: str
    severity: Severity
    title: str
    description: str
    recommendation: str
    category: Category = Category.REPOSITORY_HYGIENE

    def __post_init__(self) -> None:
        if (
            not isinstance(self.identifier, str)
            or re.fullmatch(r"RH[0-9]{3}", self.identifier) is None
        ):
            raise ValueError("Hygiene rule IDs must use RH followed by three digits")
        require_enum(self.severity, Severity, "severity")
        if self.category != Category.REPOSITORY_HYGIENE or not isinstance(self.category, Category):
            raise ValueError("Hygiene rules must belong to repository hygiene")
        for field in ("title", "description", "recommendation"):
            require_text(getattr(self, field), field)


RULES = (
    HygieneRule(
        "RH001",
        Severity.INFO,
        "No root .gitignore path in analyzed inventory",
        "The eligible file inventory contains no exact root .gitignore path; "
        "this does not establish whether ignore policies exist elsewhere.",
        "Review whether a shared root .gitignore would help collaborators; "
        "nested, local or global ignore policies may be intentional.",
    ),
    HygieneRule(
        "RH002",
        Severity.LOW,
        "File paths differ only by ASCII letter case",
        "Distinct eligible file paths have the same ASCII lowercase spelling. "
        "They may be difficult to check out together on a case-insensitive filesystem.",
        "If cross-platform checkout is intended, rename these paths so their "
        "full spellings differ by more than letter case.",
    ),
)


def _finding(rule: HygieneRule, identifier: str, evidence: tuple[Evidence, ...]) -> Finding:
    return Finding(
        identifier,
        rule.identifier,
        rule.category,
        rule.severity,
        rule.title,
        rule.description,
        evidence,
        rule.recommendation,
        RepositoryHygieneAnalyzer.SPEC.identifier,
    )


class RepositoryHygieneAnalyzer:
    """Read immutable inventory once; no filesystem, Git or subprocess work."""

    SPEC = AnalyzerSpec(
        "repository-hygiene",
        Category.REPOSITORY_HYGIENE,
        "Conservative path-only hygiene observations over eligible file inventory",
    )

    @property
    def spec(self) -> AnalyzerSpec:
        return self.SPEC

    def analyze(self, context: AnalysisContext) -> AnalyzerResult:
        inventory = context.inventory
        if inventory is None:
            return AnalyzerResult(
                self.spec, AnalyzerState.FAILED, reason="File inventory is unavailable"
            )
        findings: list[Finding] = []
        names = set(inventory.paths)
        if ".gitignore" not in names:
            findings.append(
                _finding(
                    RULES[0],
                    "repository-hygiene:RH001",
                    (
                        Evidence(
                            "No exact root .gitignore path was observed in the eligible inventory"
                        ),
                    ),
                )
            )
        groups: dict[str, list[str]] = {}
        for path in inventory.paths:
            if path.isascii():
                groups.setdefault(path.lower(), []).append(path)
        for key, paths in sorted(groups.items()):
            if len(paths) > 1:
                digest = hashlib.sha256(key.encode("ascii")).hexdigest()
                findings.append(
                    _finding(
                        RULES[1],
                        f"repository-hygiene:RH002:{digest}",
                        tuple(
                            Evidence("File path belongs to this ASCII case-collision group", path)
                            for path in paths
                        ),
                    )
                )
        return AnalyzerResult(
            self.spec,
            AnalyzerState.COMPLETED,
            tuple(sorted(findings, key=lambda finding: finding.identifier)),
        )
