"""Real static analyzer outputs from inert snapshots under the shipped policy."""

from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.analyzers.ci_static import RULES as CI_RULES
from repolens.analyzers.ci_static import GitHubActionsAnalyzer
from repolens.analyzers.dependency_audit import DependencyAuditAnalyzer
from repolens.analyzers.hygiene import RULES as HYGIENE_RULES
from repolens.analyzers.hygiene import RepositoryHygieneAnalyzer
from repolens.analyzers.python_security import PythonSecurityAnalyzer
from repolens.analyzers.python_static import RULES as PYTHON_RULES
from repolens.analyzers.python_static import PythonStaticAnalyzer
from repolens.analyzers.testing_static import RULES as TESTING_RULES
from repolens.analyzers.testing_static import TestingStaticAnalyzer
from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.application.scoring_policy import PYTHON_STATIC_V1
from repolens.domain.contracts import Analyzer
from repolens.domain.dependency_manifest import DependencyManifest, DependencyManifestSnapshot
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerState,
    FileInventory,
    Repository,
    Severity,
)
from repolens.domain.python_source import PythonSourceFile, PythonSourceSnapshot
from repolens.domain.report import AnalysisReport
from repolens.domain.scoring import ScoreState
from repolens.domain.security import BanditObservation, SecurityToolUnavailable
from repolens.domain.workflow import WorkflowFile, WorkflowSnapshot


@dataclass(frozen=True)
class ControlledScanner:
    """Normalized vendor fixture, not a claim about actual Bandit detection."""

    observations: tuple[BanditObservation, ...] = ()
    unavailable: bool = False

    def scan(self, snapshot: PythonSourceSnapshot) -> tuple[BanditObservation, ...]:
        if self.unavailable:
            raise SecurityToolUnavailable("Controlled missing tool")
        assert snapshot.files
        return self.observations


def context(*, mixed: bool = False, info: bool = False) -> AnalysisContext:
    sources = [PythonSourceFile("app.py", "value = 1\n")]
    workflow = WorkflowFile(
        ".github/workflows/check.yml",
        "on: push\n"
        + ("permissions: write-all\n" if mixed else "")
        + "jobs:\n  checks:\n    runs-on: ubuntu-latest\n    steps:\n"
        + ("      - uses: owner/action@v1\n" if mixed else "      - run: echo inert\n"),
    )
    paths = ["app.py"]
    if mixed:
        sources[0] = PythonSourceFile(
            "app.py", "from module import *\ntry:\n    pass\nexcept:\n    pass\n"
        )
        paths.extend(("Docs/readme.txt", "docs/readme.txt"))
    elif not info:
        sources.append(PythonSourceFile("tests/test_api.py", "def test_api():\n    pass\n"))
        paths.append("tests/test_api.py")
    if not info:
        paths.extend((".gitignore", workflow.path))
    return AnalysisContext(
        Repository("inert-reference"),
        FileInventory(paths),
        PythonSourceSnapshot(sources),
        workflows=WorkflowSnapshot(()) if info else WorkflowSnapshot((workflow,)),
    )


def plan(scanner: ControlledScanner, *, dependencies: bool = False) -> AnalyzerPlan:
    # Explicit test composition; product values never choose or trim this plan.
    analyzers: list[Analyzer] = [
        RepositoryHygieneAnalyzer(),
        PythonStaticAnalyzer(),
        TestingStaticAnalyzer(),
        PythonSecurityAnalyzer(scanner),
        GitHubActionsAnalyzer(),
    ]
    if dependencies:
        return AnalyzerPlan((*analyzers, DependencyAuditAnalyzer()))
    return AnalyzerPlan(analyzers)


def test_shipped_rule_severity_inventory_is_unchanged() -> None:
    rules = (*HYGIENE_RULES, *PYTHON_RULES, *TESTING_RULES, *CI_RULES)
    assert {rule.identifier: rule.severity for rule in rules} == {
        "RH001": Severity.INFO,
        "RH002": Severity.LOW,
        "PY001": Severity.LOW,
        "PY002": Severity.LOW,
        "TEST001": Severity.INFO,
        "TEST002": Severity.INFO,
        "CI001": Severity.INFO,
        "CI002": Severity.LOW,
        "CI003": Severity.LOW,
    }


@pytest.mark.parametrize(
    "mode, overall", [("clean", "100.00"), ("info", "100.00"), ("mixed", "78.75")]
)
def test_real_analyzer_reference_outputs_are_inert_and_exact(
    mode: str, overall: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = context(mixed=mode == "mixed", info=mode == "info")
    scanner = ControlledScanner(
        (
            BanditObservation("B301", Severity.MEDIUM, "app.py", 1, 0),
            BanditObservation("B602", Severity.HIGH, "app.py", 2, 0),
        )
        if mode == "mixed"
        else ()
    )
    registered = plan(scanner)
    forbidden = MagicMock(side_effect=AssertionError("Calibration must consume detached data"))
    with monkeypatch.context() as scope:
        scope.setattr(Path, "open", forbidden)
        scope.setattr("subprocess.Popen", forbidden)
        scope.setattr("importlib.import_module", forbidden)
        outcomes = execute_analyzers(registered, data)
        assessment = AnalysisReport(data.repository, registered.specs, outcomes, PYTHON_STATIC_V1)
    forbidden.assert_not_called()
    assert all(r.state == AnalyzerState.COMPLETED for r in outcomes)
    assert str(assessment.score.value) == overall
    if mode == "clean":
        assert not assessment.findings
    elif mode == "info":
        assert {f.rule_id for f in assessment.findings} == {"RH001", "TEST001", "CI001"}
        assert all(f.severity == Severity.INFO for f in assessment.findings)
    else:
        assert tuple(c.value for c in assessment.score.categories) == (90, 100, 55, 95, 90)
        assert len(assessment.findings) == 8


def test_missing_bandit_blocks_numeric_product_score() -> None:
    registered = plan(ControlledScanner(unavailable=True))
    data = context()
    outcomes = execute_analyzers(registered, data)
    assessment = AnalysisReport(data.repository, registered.specs, outcomes, PYTHON_STATIC_V1)
    assert next(r for r in outcomes if r.analyzer.identifier == "python-security").state == (
        AnalyzerState.UNSUPPORTED
    )
    assert assessment.score.categories[2].value is None
    assert assessment.score.value is None


@pytest.mark.parametrize("manifest", [None, "", "example==1.0\n", "example>=1.0\n"])
def test_declared_dependency_audit_cannot_be_dropped_to_salvage_product_score(
    manifest: str | None,
) -> None:
    data = context()
    entries = () if manifest is None else (DependencyManifest("requirements.txt", manifest),)
    assert data.inventory is not None
    data = AnalysisContext(
        data.repository,
        FileInventory((*data.inventory.paths, *(entry.path for entry in entries))),
        data.python_sources,
        DependencyManifestSnapshot(entries),
        data.workflows,
    )
    registered = plan(ControlledScanner(), dependencies=True)
    outcomes = execute_analyzers(registered, data)
    assessment = AnalysisReport(data.repository, registered.specs, outcomes, PYTHON_STATIC_V1)
    assert next(r for r in outcomes if r.analyzer.identifier == "dependency-audit").state == (
        AnalyzerState.UNSUPPORTED
    )
    security = assessment.score.categories[2]
    assert security.state == ScoreState.INCOMPLETE
    assert security.value is None
    assert security.completed_analyzers == ("python-security",)
    assert security.unavailable_analyzers == ("dependency-audit",)
    assert assessment.score.value is None


@pytest.mark.parametrize(
    "severity, value", [(Severity.LOW, 95), (Severity.MEDIUM, 85), (Severity.HIGH, 70)]
)
def test_real_vendor_normalization_retains_impact_under_product_policy(
    severity: Severity, value: int
) -> None:
    registered = plan(ControlledScanner((BanditObservation("B602", severity, "app.py", 1, 0),)))
    data = context()
    assessment = AnalysisReport(
        data.repository,
        registered.specs,
        execute_analyzers(registered, data),
        PYTHON_STATIC_V1,
    )
    assert assessment.findings[0].rule_id == "BANDIT-B602"
    assert assessment.findings[0].severity == severity
    assert assessment.score.categories[2].value == value
