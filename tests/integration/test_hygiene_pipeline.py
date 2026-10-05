"""Real acquired inert fixtures compose inventory, hygiene, orchestration and report."""

import shutil
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.analyzers.hygiene import RepositoryHygieneAnalyzer
from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.domain.models import AnalysisContext, AnalyzerState, Category, FileInventory, Severity
from repolens.domain.report import AnalysisReport
from repolens.domain.scoring import CategoryWeight, ScoringPolicy, SeverityPenalty
from repolens.infrastructure.errors import AcquisitionError, TraversalLimitExceeded
from repolens.infrastructure.git import GitOutput, GitRunner
from repolens.infrastructure.inventory import snapshot_context
from repolens.infrastructure.repository_source import RepositorySource
from repolens.infrastructure.traversal import TraversalLimits, repository_files


def policy() -> ScoringPolicy:
    return ScoringPolicy(
        "synthetic-hygiene-test-policy",
        tuple(SeverityPenalty(severity, index * 5) for index, severity in enumerate(Severity)),
        (CategoryWeight(Category.REPOSITORY_HYGIENE, 1),),
    )


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    assert GitRunner().run(("init", "--quiet"), tmp_path, 10).returncode == 0
    return tmp_path


@pytest.mark.parametrize("clean", [False, True])
def test_acquisition_context_hygiene_orchestration_and_explicit_report(
    repository: Path, monkeypatch: pytest.MonkeyPatch, clean: bool
) -> None:
    marker = repository / "executed"
    (repository / "target.py").write_text(
        "from pathlib import Path\nPath(__file__).with_name('executed').touch()\n", encoding="utf-8"
    )
    (repository / "setup.py").write_text(
        "raise RuntimeError('must never import')", encoding="utf-8"
    )
    (repository / "pyproject.toml").write_text("invalid target configuration", encoding="utf-8")
    if clean:
        (repository / ".gitignore").write_text("secret content is not read", encoding="utf-8")
    with RepositorySource().local(repository) as lease:
        context = snapshot_context(lease)
        assert context.inventory is not None
        assert all(not Path(path).is_absolute() for path in context.inventory.paths)
        assert ".git" not in context.inventory.paths
        assert str(repository) not in repr(context)
        analyzer = RepositoryHygieneAnalyzer()
        direct = analyzer.analyze(context)
        plan = AnalyzerPlan([analyzer])
        forbidden = MagicMock(
            side_effect=AssertionError("Target access is forbidden during analysis")
        )
        with monkeypatch.context() as scope:
            scope.setattr(GitRunner, "run", forbidden)
            scope.setattr(RepositorySource, "local", forbidden)
            scope.setattr(RepositorySource, "github", forbidden)
            scope.setattr("repolens.infrastructure.inventory.repository_files", forbidden)
            scope.setattr("subprocess.Popen", forbidden)
            scope.setattr(Path, "open", forbidden)
            scope.setattr(Path, "read_bytes", forbidden)
            scope.setattr(Path, "read_text", forbidden)
            results = execute_analyzers(plan, context)
            report = AnalysisReport(lease.identity, plan.specs, results, policy())
        forbidden.assert_not_called()
        assert results == (direct,)
        assert results[0].state == AnalyzerState.COMPLETED
        assert tuple(finding.rule_id for finding in report.findings) == (
            () if clean else ("RH001",)
        )
        assert "secret content" not in repr(report)
        assert report.score.categories[0].value == 100  # INFO is zero, not a product policy.
        assert not marker.exists()
    assert context.inventory is not None
    assert analyzer.analyze(context) == direct  # Detached data retains no lease access.
    with pytest.raises(AcquisitionError, match="closed"):
        snapshot_context(lease)


def test_case_collision_from_actual_filesystem_is_observed_only_when_distinct(
    repository: Path,
) -> None:
    (repository / ".gitignore").touch()
    upper = repository / "Example"
    lower = repository / "example"
    upper.touch()
    distinct = not lower.exists()
    lower.touch()
    with RepositorySource().local(repository) as lease:
        context = snapshot_context(lease)
        analyzer = RepositoryHygieneAnalyzer()
        plan = AnalyzerPlan([analyzer])
        results = execute_analyzers(plan, context)
        report = AnalysisReport(lease.identity, plan.specs, results, policy())
    assert tuple(finding.rule_id for finding in report.findings) == (("RH002",) if distinct else ())
    assert report.score.categories[0].value == (95 if distinct else 100)


def test_traversal_limits_do_not_publish_a_partial_context(repository: Path) -> None:
    (repository / "one").touch()
    with RepositorySource().local(repository) as lease, pytest.raises(TraversalLimitExceeded):
        snapshot_context(lease, TraversalLimits(max_entries=1))


@pytest.mark.parametrize("malformed", [False, True])
def test_invalid_or_failing_inventory_never_becomes_fake_empty_snapshot(
    repository: Path, monkeypatch: pytest.MonkeyPatch, malformed: bool
) -> None:
    def entries(*args: object) -> Iterator[Path]:
        yield Path("safe-file")
        if malformed:
            yield Path("../escape")
        else:
            raise AcquisitionError("Inventory unavailable")

    with RepositorySource().local(repository) as lease:
        monkeypatch.setattr("repolens.infrastructure.inventory.repository_files", entries)
        with pytest.raises(AcquisitionError):
            snapshot_context(lease)


def test_lease_closing_during_inventory_prevents_snapshot_publication(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with RepositorySource().local(repository) as lease:

        def entries(*args: object) -> Iterator[Path]:
            yield Path("file")
            lease.close()

        monkeypatch.setattr("repolens.infrastructure.inventory.repository_files", entries)
        with pytest.raises(AcquisitionError, match="closed"):
            snapshot_context(lease)


def test_empty_repository_is_available_and_exclusions_remain_in_force(repository: Path) -> None:
    with RepositorySource().local(repository) as lease:
        assert snapshot_context(lease).inventory == FileInventory(())
        (repository / "node_modules").mkdir()
        (repository / "node_modules" / "something").touch()
        (repository / "large").write_bytes(b"123456")
        (repository / "visible").touch()
        context = snapshot_context(lease, TraversalLimits(max_file_bytes=5))
        assert context.inventory == FileInventory(("visible",))


def test_unavailable_context_yields_failed_and_blocks_numeric_score(repository: Path) -> None:
    with RepositorySource().local(repository) as lease:
        context = AnalysisContext(lease.identity)
        plan = AnalyzerPlan([RepositoryHygieneAnalyzer()])
        results = execute_analyzers(plan, context)
        report = AnalysisReport(lease.identity, plan.specs, results, policy())
    assert results[0].state == AnalyzerState.FAILED
    assert report.score.value is None


def test_snapshot_is_independent_of_traversal_order(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("z", "a", ".gitignore"):
        (repository / name).touch()
    with RepositorySource().local(repository) as lease:
        baseline = snapshot_context(lease)
        observed = tuple(repository_files(lease))
        monkeypatch.setattr(
            "repolens.infrastructure.inventory.repository_files",
            lambda lease, limits: iter(reversed(observed)),
        )
        assert snapshot_context(lease) == baseline


def test_oversized_ignore_path_observation_is_qualified_to_eligible_inventory(
    repository: Path,
) -> None:
    (repository / ".gitignore").write_bytes(b"123456")
    with RepositorySource().local(repository) as lease:
        context = snapshot_context(lease, TraversalLimits(max_file_bytes=5))
    result = execute_analyzers(AnalyzerPlan([RepositoryHygieneAnalyzer()]), context)[0]
    assert (repository / ".gitignore").is_file()
    assert result.findings[0].rule_id == "RH001"
    assert "inventory" in result.findings[0].title
    assert "eligible inventory" in result.findings[0].evidence[0].description
    assert result.findings[0].severity == Severity.INFO


def test_remote_snapshot_has_no_lifetime_capability_after_owned_workspace_cleanup(
    repository: Path,
) -> None:
    (repository / ".gitignore").touch()

    class CopyClone:
        workspace: Path | None = None

        def run(self, arguments: tuple[str, ...], cwd: Path, timeout: int) -> GitOutput:
            if arguments[0] == "clone":
                self.workspace = cwd
                shutil.copytree(repository, arguments[-1])
                return GitOutput(0, b"")
            return GitRunner().run(arguments, cwd, timeout)

    fake = CopyClone()
    with RepositorySource(fake).github("https://github.com/owner/repository") as lease:
        context = snapshot_context(lease)
        assert str(lease.root) not in repr(context)
    assert fake.workspace is not None and not fake.workspace.exists()
    result = execute_analyzers(AnalyzerPlan([RepositoryHygieneAnalyzer()]), context)[0]
    assert result.state == AnalyzerState.COMPLETED
    assert result.findings == ()
