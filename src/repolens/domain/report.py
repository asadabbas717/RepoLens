"""A domain report holds inputs and derived scores without rendering them."""

from dataclasses import dataclass, field

from repolens.domain.assessment_configuration import AppliedConfiguration
from repolens.domain.models import AnalyzerResult, AnalyzerSpec, Finding, Repository
from repolens.domain.scoring import RepositoryScore, ScoringPolicy, score_repository


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """Consistent immutable snapshot, canonically ordered by identifiers."""

    repository: Repository
    plan: tuple[AnalyzerSpec, ...]
    results: tuple[AnalyzerResult, ...]
    policy: ScoringPolicy
    configuration: AppliedConfiguration | None = None
    score: RepositoryScore = field(init=False)

    def __post_init__(self) -> None:
        if self.configuration is not None and not isinstance(
            self.configuration, AppliedConfiguration
        ):
            raise ValueError("Report configuration must be typed applied metadata")
        object.__setattr__(self, "plan", tuple(sorted(self.plan, key=lambda spec: spec.identifier)))
        object.__setattr__(
            self,
            "results",
            tuple(sorted(self.results, key=lambda result: result.analyzer.identifier)),
        )
        if self.configuration is not None and any(
            finding.rule_id in self.configuration.disabled_rules
            for result in self.results
            for finding in result.findings
        ):
            raise ValueError("Active findings cannot contradict applied disabled rules")
        object.__setattr__(self, "score", score_repository(self.plan, self.results, self.policy))

    @property
    def findings(self) -> tuple[Finding, ...]:
        """All evidence retained, including zero-penalty informational findings."""
        return tuple(
            sorted(
                (finding for result in self.results for finding in result.findings),
                key=lambda finding: finding.identifier,
            )
        )
