"""Inert repositories, verified manifests and optional real detached Bandit."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.analyzers.dependency_audit import DependencyAuditAnalyzer
from repolens.analyzers.python_security import PythonSecurityAnalyzer
from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.domain.models import AnalyzerState, Category, Severity
from repolens.domain.report import AnalysisReport
from repolens.domain.scoring import CategoryWeight, ScoringPolicy, SeverityPenalty
from repolens.domain.security import BanditObservation, SecurityToolFailed
from repolens.infrastructure import dependency_manifest as manifests
from repolens.infrastructure.bandit import BanditRunner
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.git import GitRunner
from repolens.infrastructure.python_source import snapshot_python_context
from repolens.infrastructure.repository_source import RepositoryLease, RepositorySource


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    assert GitRunner().run(("init", "--quiet"), tmp_path, 10).returncode == 0
    return tmp_path


def policy() -> ScoringPolicy:
    return ScoringPolicy(
        "synthetic-security",
        tuple(SeverityPenalty(s, i * 5) for i, s in enumerate(Severity)),
        (CategoryWeight(Category.SECURITY, 1),),
    )


def test_combined_pipeline_detached_and_failure_aware(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = repository / "executed"
    (repository / "app.py").write_text(
        "password='source-secret'\nfrom pathlib import Path\n"
        "Path(__file__).with_name('executed').touch()\n"
        "raise RuntimeError('must-not-execute')",
        encoding="utf-8",
    )
    (repository / "setup.py").write_text("raise RuntimeError('must-not-build')", encoding="utf-8")
    (repository / "requirements.txt").write_text("example==1.0", encoding="utf-8")
    (repository / "pyproject.toml").write_text(
        '[project]\ndependencies=["example==1.0"]\n[build-system]\nbuild-backend="malicious"',
        encoding="utf-8",
    )
    with RepositorySource().local(repository) as lease:
        context = snapshot_python_context(lease, include_dependency_manifests=True)
        identity = lease.identity
    scanner = MagicMock()
    scanner.scan.return_value = (BanditObservation("B105", Severity.LOW, "app.py", 1, 9),)
    plan = AnalyzerPlan([PythonSecurityAnalyzer(scanner), DependencyAuditAnalyzer()])
    forbidden = MagicMock(
        side_effect=AssertionError("Detached analyzers must not perform direct I/O")
    )
    with monkeypatch.context() as scope:
        scope.setattr(Path, "open", forbidden)
        scope.setattr(GitRunner, "run", forbidden)
        scope.setattr("subprocess.Popen", forbidden)
        scope.setattr("importlib.import_module", forbidden)
        results = execute_analyzers(plan, context)
        report = AnalysisReport(identity, plan.specs, results, policy())
    forbidden.assert_not_called()
    assert results[0].state == AnalyzerState.UNSUPPORTED
    assert results[1].state == AnalyzerState.COMPLETED
    assert report.score.value is None
    assert len(report.findings) == 1
    assert "source-secret" not in repr(context) + repr(results) + repr(report)
    assert str(repository) not in repr(report)
    assert not marker.exists()


def test_real_pinned_bandit_uses_detached_sources_and_no_target_config(repository: Path) -> None:
    # Bandit is already a locked dev dependency; no installation/network needed.
    (repository / "app.py").write_text(
        "password='secret-token' # nosec\nfrom pathlib import Path\n"
        "Path(__file__).with_name('executed').touch()",
        encoding="utf-8",
    )
    (repository / ".bandit").write_text("[bandit]\nskips=B105", encoding="utf-8")
    (repository / "pyproject.toml").write_text("[tool.bandit]\nskips=['B105']", encoding="utf-8")
    with RepositorySource().local(repository) as lease:
        context = snapshot_python_context(lease)
        scanner = BanditRunner(origin_root=lease.root)
    result = PythonSecurityAnalyzer(scanner).analyze(context)
    assert result.state == AnalyzerState.COMPLETED
    assert any(f.rule_id == "BANDIT-B105" for f in result.findings)
    assert "secret-token" not in repr(result)
    assert not (repository / "executed").exists()


@pytest.mark.parametrize("name", ["requirements.txt", "pyproject.toml"])
def test_manifest_raw_limit_and_no_partial_snapshot(repository: Path, name: str) -> None:
    (repository / name).write_bytes(b"x" * (64 * 1024 + 1))
    with (
        RepositorySource().local(repository) as lease,
        pytest.raises(AcquisitionError, match="limit"),
    ):
        snapshot_python_context(lease, include_dependency_manifests=True)
    with (
        RepositorySource().local(repository) as lease,
        pytest.raises(AcquisitionError, match="limit"),
    ):
        manifests.snapshot_dependency_context(lease)


@pytest.mark.parametrize("raw", [b"a==1", b"\xef\xbb\xbfa==1"])
def test_manifest_utf8_bom_and_only_whitelisted_reads(repository: Path, raw: bytes) -> None:
    (repository / "requirements.txt").write_bytes(raw)
    (repository / "requirements-dev.txt").write_text("secret unrelated content", encoding="utf-8")
    (repository / "requirements.txt.example").write_text("secret", encoding="utf-8")
    with RepositorySource().local(repository) as lease:
        context = manifests.snapshot_dependency_context(lease)
    assert context.dependency_manifests is not None
    assert len(context.dependency_manifests.files) == 1
    assert context.dependency_manifests.files[0].text == "a==1"
    assert context.python_sources is None


def test_manifest_decode_and_closed_lease_fail(repository: Path) -> None:
    (repository / "requirements.txt").write_bytes(b"\xff-secret")
    with RepositorySource().local(repository) as lease, pytest.raises(AcquisitionError):
        manifests.snapshot_dependency_context(lease)
    with pytest.raises(AcquisitionError, match="closed"):
        manifests.snapshot_dependency_context(lease)


@pytest.mark.parametrize("mode", ["failure", "change", "reparse"])
def test_manifest_read_failure_change_and_reparse(
    repository: Path, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / "requirements.txt").write_text("a==1", encoding="utf-8")
    from repolens.infrastructure.verified_read import _read_verified

    original = _read_verified

    def read(lease: RepositoryLease, path: str, limit: int) -> bytes:
        if mode == "failure":
            raise OSError("secret-path")
        if mode == "change":
            return b"a==123"
        from repolens.infrastructure import verified_read

        with monkeypatch.context() as scope:
            scope.setattr(
                verified_read,
                "_link_or_reparse",
                lambda checked: checked.name == "requirements.txt",
            )
            return original(lease, path, limit)

    monkeypatch.setattr(manifests, "_read_verified", read)
    with RepositorySource().local(repository) as lease, pytest.raises(AcquisitionError) as error:
        manifests.snapshot_dependency_context(lease)
    assert "secret-path" not in str(error.value)


def test_scanner_failure_cannot_produce_perfect_score(repository: Path) -> None:
    (repository / "app.py").write_text("pass", encoding="utf-8")
    with RepositorySource().local(repository) as lease:
        context = snapshot_python_context(lease)
    scanner = MagicMock()
    scanner.scan.side_effect = SecurityToolFailed("secret")
    plan = AnalyzerPlan([PythonSecurityAnalyzer(scanner)])
    results = execute_analyzers(plan, context)
    report = AnalysisReport(context.repository, plan.specs, results, policy())
    assert results[0].state == AnalyzerState.FAILED and report.score.value is None


@pytest.mark.parametrize("paths", [("setup.py",), ("requirements.txt", "requirements.txt")])
def test_manifest_admission_precedes_reads(
    paths: tuple[str, ...], repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    forbidden = MagicMock(side_effect=AssertionError("Unadmitted manifests must not be read"))
    monkeypatch.setattr(manifests, "_read_verified", forbidden)
    with (
        RepositorySource().local(repository) as lease,
        pytest.raises(AcquisitionError, match="admission"),
    ):
        manifests._snapshot_manifests(lease, [(path, 1) for path in paths])
    forbidden.assert_not_called()
