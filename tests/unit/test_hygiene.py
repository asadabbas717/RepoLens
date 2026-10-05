"""Actual hygiene rules use inert path data and make narrowly scoped observations."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest

from repolens.analyzers.hygiene import RULES, HygieneRule, RepositoryHygieneAnalyzer
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerState,
    Category,
    FileInventory,
    Repository,
    Severity,
)


def analyze(paths: tuple[str, ...]) -> tuple[str, ...]:
    result = RepositoryHygieneAnalyzer().analyze(
        AnalysisContext(Repository("fixture"), FileInventory(paths))
    )
    assert result.state == AnalyzerState.COMPLETED
    return tuple(finding.rule_id for finding in result.findings)


def test_catalog_ids_ownership_severity_and_required_metadata_are_deliberate() -> None:
    assert tuple(rule.identifier for rule in RULES) == ("RH001", "RH002")
    assert tuple(rule.severity for rule in RULES) == (Severity.INFO, Severity.LOW)
    assert all(rule.category == Category.REPOSITORY_HYGIENE for rule in RULES)
    assert all(
        rule.title.strip() and rule.description.strip() and rule.recommendation.strip()
        for rule in RULES
    )
    with pytest.raises(FrozenInstanceError):
        RULES[0].__setattr__("identifier", "changed")


@pytest.mark.parametrize(
    "field,value",
    [
        ("identifier", "RH1"),
        ("identifier", "XX001"),
        ("identifier", None),
        ("severity", "info"),
        ("category", Category.SECURITY),
        ("category", "repository_hygiene"),
        ("title", " "),
        ("description", ""),
        ("recommendation", ""),
    ],
)
def test_catalog_rejects_invalid_metadata(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        cast(Callable[..., HygieneRule], replace)(RULES[0], **{field: value})


@pytest.mark.parametrize(
    "paths",
    [
        (),
        ("src/main.py",),
        ("nested/.gitignore",),
        ("something.gitignore",),
        (".gitignore.example",),
        (".GITIGNORE",),
    ],
)
def test_rh001_requires_exact_root_ignore_path(paths: tuple[str, ...]) -> None:
    assert analyze(paths) == ("RH001",)


@pytest.mark.parametrize(
    "paths", [(".gitignore",), (".gitignore", "nested/file"), (".gitignore", ".gitignore.example")]
)
def test_root_ignore_path_satisfies_presence_signal_without_content_claims(
    paths: tuple[str, ...],
) -> None:
    assert analyze(paths) == ()


@pytest.mark.parametrize(
    "paths",
    [
        ("README", "readme"),
        ("src/File", "src/file"),
        ("Src/file", "src/file"),
        ("x", "X", "other", "OTHER"),
    ],
)
def test_ascii_case_collisions_have_one_finding_per_group(paths: tuple[str, ...]) -> None:
    expected_groups = len(paths) // 2
    assert analyze((".gitignore", *paths)) == ("RH002",) * expected_groups


@pytest.mark.parametrize(
    "paths",
    [
        ("README.md", "README-old.md"),
        ("file", "file.txt"),
        ("one/File", "two/file"),
        ("Src/a", "src/b"),
        ("Stra\u00dfe", "STRASSE"),
        ("caf\u00e9/File", "caf\u00e9/file"),
    ],
)
def test_near_matches_and_unicode_case_assumptions_do_not_raise_collisions(
    paths: tuple[str, ...],
) -> None:
    assert analyze((".gitignore", *paths)) == ()


def test_opposite_inventory_order_produces_identical_safe_findings_without_mutation() -> None:
    paths = ("z", "Z", "x", "X")
    first = AnalysisContext(Repository("fixture"), FileInventory(paths))
    second = AnalysisContext(Repository("fixture"), FileInventory(reversed(paths)))
    analyzer = RepositoryHygieneAnalyzer()
    result = analyzer.analyze(first)
    assert result == analyzer.analyze(second) == analyzer.analyze(first)
    assert first.inventory is not None and first.inventory.paths == tuple(sorted(paths))
    assert result.findings[0].identifier == "repository-hygiene:RH001"
    assert result.findings[0].evidence[0].file_path is None
    assert result.findings[0].evidence[0].line_number is None
    for finding in result.findings:
        assert finding.source_analyzer == analyzer.spec.identifier
        assert finding.category == Category.REPOSITORY_HYGIENE
        assert finding.identifier.startswith("repository-hygiene:" + finding.rule_id)
        assert all(evidence.line_number is None for evidence in finding.evidence)
    collision = result.findings[1]
    assert len(collision.identifier.rsplit(":", 1)[1]) == 64
    assert tuple(evidence.file_path for evidence in collision.evidence) in (("X", "x"), ("Z", "z"))


def test_missing_inventory_is_failed_not_completed_empty() -> None:
    result = RepositoryHygieneAnalyzer().analyze(AnalysisContext(Repository("fixture")))
    assert result.state == AnalyzerState.FAILED
    assert result.findings == ()
    assert result.reason == "File inventory is unavailable"


def test_collision_finding_identity_has_a_stable_golden_value() -> None:
    context = AnalysisContext(Repository("fixture"), FileInventory((".gitignore", "X", "x")))
    result = RepositoryHygieneAnalyzer().analyze(context)
    assert result.findings[0].identifier == (
        "repository-hygiene:RH002:2d711642b726b04401627ca9fbac32f5c8530fb1903cc4db02258717921a4881"
    )
    assert tuple(evidence.file_path for evidence in result.findings[0].evidence) == ("X", "x")
