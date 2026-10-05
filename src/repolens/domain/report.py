"""A domain report holds inputs and derived scores without rendering them."""

from dataclasses import dataclass, field

from repolens.domain.models import AnalyzerResult, AnalyzerSpec, Finding, Repository
from repolens.domain.scoring import RepositoryScore, ScoringPolicy, score_repository


@dataclass(frozen=True, slots=True)
class AnalysisReport:
    """Consistent immutable snapshot, canonically ordered by identifiers."""

    repository: Repository
    plan: tuple[AnalyzerSpec, ...]
    results: tuple[AnalyzerResult, ...]
    policy: ScoringPolicy
    score: RepositoryScore = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan", tuple(sorted(self.plan, key=lambda spec: spec.identifier)))
        object.__setattr__(
            self,
            "results",
            tuple(sorted(self.results, key=lambda result: result.analyzer.identifier)),
        )
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
