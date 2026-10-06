"""Versioned product values; generic arithmetic remains in domain.scoring."""

from typing import Final

from repolens.domain.models import Category, Severity
from repolens.domain.scoring import CategoryWeight, ScoringPolicy, SeverityPenalty

# Published penalties, weights or scope must change under a new identifier.
# This profile chooses no analyzer plan and cannot bypass unavailable results.
PYTHON_STATIC_V1: Final = ScoringPolicy(
    identifier="repolens-python-static-v1",
    penalties=(
        SeverityPenalty(Severity.INFO, 0),
        SeverityPenalty(Severity.LOW, 5),
        SeverityPenalty(Severity.MEDIUM, 15),
        SeverityPenalty(Severity.HIGH, 30),
        SeverityPenalty(Severity.CRITICAL, 60),
    ),
    weights=(
        CategoryWeight(Category.CODE_QUALITY, 2),
        CategoryWeight(Category.TESTING, 1),
        CategoryWeight(Category.SECURITY, 3),
        CategoryWeight(Category.REPOSITORY_HYGIENE, 1),
        CategoryWeight(Category.CI_CD, 1),
    ),
)
