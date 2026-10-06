"""Inert local and simulated-remote shell composition; no live GitHub access."""

import shutil
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import pytest

from repolens import cli
from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.domain.models import AnalysisContext, AnalyzerResult, Severity
from repolens.domain.python_source import PythonSourceSnapshot
from repolens.domain.report import AnalysisReport
from repolens.domain.security import BanditObservation, SecurityToolFailed
from repolens.infrastructure import bandit, python_source
from repolens.infrastructure.analysis_context import snapshot_analysis_context
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.git import GitOutput, GitRunner
from repolens.infrastructure.repository_source import RepositoryLease, RepositorySource


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "inert-secret-name"
    root.mkdir()
    assert GitRunner().run(("init", "--quiet"), root, 10).returncode == 0
    (root / "app.py").write_text(
        "from module import *\nfrom pathlib import Path\n"
        "Path(__file__).with_name('executed-marker').touch()\n"
        "try:\n    raise RuntimeError('source-secret')\nexcept:\n    pass\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    (root / "tests/test_app.py").write_text("def test_app():\n    pass\n", encoding="utf-8")
    (root / "conftest.py").write_text("raise RuntimeError('must-not-collect')", encoding="utf-8")
    (root / "setup.py").write_text("raise RuntimeError('must-not-build')", encoding="utf-8")
    (root / ".github/workflows").mkdir(parents=True)
    (root / ".github/workflows/check.yml").write_text(
        "on: push\npermissions: write-all\njobs:\n  checks:\n"
        "    runs-on: ubuntu-latest\n    steps:\n"
        "      - uses: owner/action@v1\n      - run: touch executed-marker\n",
        encoding="utf-8",
    )
    (root / "requirements.txt").write_text("secret malformed manifest", encoding="utf-8")
    return root


class Scanner:
    def __init__(self, lease: RepositoryLease, remote_root: Path | None = None) -> None:
        self.lease = lease
        self.remote_root = remote_root
        self.calls = 0

    def scan(self, snapshot: PythonSourceSnapshot) -> tuple[BanditObservation, ...]:
        self.calls += 1
        with pytest.raises(AcquisitionError, match="closed"):
            _ = self.lease.root
        if self.remote_root is not None:
            assert not self.remote_root.exists()
        assert "source-secret" in next(f.text for f in snapshot.files if f.path == "app.py")
        return (BanditObservation("B602", Severity.HIGH, "app.py", 1, 0),)


def test_real_local_subdirectory_pipeline_is_detached_inert_and_deterministic(
    repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    leases: list[RepositoryLease] = []
    scanners: list[Scanner] = []
    reports: list[AnalysisReport] = []
    original_status = cli._status

    def snapshot(lease: RepositoryLease) -> AnalysisContext:
        leases.append(lease)
        return snapshot_analysis_context(lease)

    def scanner(*, origin_root: Path | None) -> Scanner:
        assert origin_root == repository.resolve()
        instance = Scanner(leases[-1])
        scanners.append(instance)
        return instance

    def status(report: AnalysisReport, threshold: object) -> int:
        reports.append(report)
        assert threshold is None
        return original_status(report, None)

    monkeypatch.setattr(cli, "snapshot_analysis_context", snapshot)
    monkeypatch.setattr(cli, "BanditRunner", scanner)
    monkeypatch.setattr(cli, "_status", status)
    outputs = []
    for _ in range(2):
        assert cli.run(["scan", str(repository / "tests")]) == 0
        output = capsys.readouterr()
        assert not output.err
        outputs.append(output.out)
    assert outputs[0] == outputs[1]
    assert reports[0] == reports[1]
    assert str(reports[0].score.value) == "85.00"
    assert {f.rule_id for f in reports[0].findings} == {
        "RH001",
        "PY001",
        "PY002",
        "BANDIT-B602",
        "CI002",
        "CI003",
    }
    assert len(reports[0].plan) == 5
    assert all(scanner.calls == 1 for scanner in scanners)
    assert "secret" not in outputs[0]
    assert str(repository) not in outputs[0]
    assert not (repository / "executed-marker").exists()


class SimulatedClone:
    def __init__(self, fixture: Path, failure: bool = False) -> None:
        self.fixture = fixture
        self.failure = failure
        self.workspace: Path | None = None
        self.destination: Path | None = None
        self.url: str | None = None

    def run(self, arguments: tuple[str, ...], cwd: Path, timeout: int) -> GitOutput:
        if arguments[0] == "clone":
            self.workspace = cwd
            self.destination = Path(arguments[-1])
            self.url = arguments[-2]
            assert arguments[5] == "--" and timeout == 120
            if self.failure:
                return GitOutput(1, b"secret Git diagnostic")
            shutil.copytree(self.fixture, self.destination)
            return GitOutput(0, b"")
        return GitRunner().run(arguments, cwd, timeout)


@pytest.mark.parametrize("failure", ["none", "snapshot", "clone", "internal", "cleanup"])
def test_remote_cli_uses_canonical_url_and_cleans_before_execution_on_all_exits(
    repository: Path,
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = SimulatedClone(repository, failure == "clone")
    acquisition = RepositorySource(fake)
    monkeypatch.setattr(cli, "RepositorySource", MagicMock(return_value=acquisition))
    captured: list[RepositoryLease] = []

    def snapshot(lease: RepositoryLease) -> AnalysisContext:
        captured.append(lease)
        if failure == "snapshot":
            raise AcquisitionError("secret source/OS failure")
        return snapshot_analysis_context(lease)

    def scanner(*, origin_root: Path | None) -> Scanner:
        assert origin_root is not None and origin_root.is_dir()
        if failure == "internal":
            raise RuntimeError("secret composition failure")
        return Scanner(captured[-1], origin_root)

    def execute(plan: AnalyzerPlan, data: AnalysisContext) -> tuple[AnalyzerResult, ...]:
        assert fake.workspace is not None and not fake.workspace.exists()
        with pytest.raises(AcquisitionError, match="closed"):
            _ = captured[-1].root
        return execute_analyzers(plan, data)

    if failure == "cleanup":
        # Patch only RepoLens's workspace owner; always perform actual cleanup.
        from repolens.infrastructure import repository_source

        workspace = TemporaryDirectory(prefix="repolens-test-source-")
        cleanup = workspace.cleanup

        def cleanup_then_fail() -> None:
            cleanup()
            raise OSError("secret cleanup failure")

        monkeypatch.setattr(workspace, "cleanup", cleanup_then_fail)
        monkeypatch.setattr(
            repository_source, "TemporaryDirectory", MagicMock(return_value=workspace)
        )
    monkeypatch.setattr(cli, "snapshot_analysis_context", snapshot)
    monkeypatch.setattr(cli, "BanditRunner", scanner)
    monkeypatch.setattr(cli, "execute_analyzers", execute)
    expected = 0 if failure == "none" else 3 if failure == "internal" else 2
    assert cli.run(["scan", "https://github.com/owner/example/"]) == expected
    output = capsys.readouterr()
    assert fake.url == "https://github.com/owner/example.git"
    assert fake.workspace is not None and not fake.workspace.exists()
    assert "secret" not in output.out + output.err
    assert str(fake.workspace) not in output.out + output.err
    assert not (repository / "executed-marker").exists()
    if failure == "none":
        assert not output.err and "Assessment: complete" in output.out
    else:
        assert not output.out


def test_missing_production_bandit_yields_unsupported_without_crash(
    repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def absent(name: str) -> str:
        assert name == "bandit"
        raise PackageNotFoundError(name)

    monkeypatch.setattr(bandit, "version", absent)
    assert cli.run(["scan", str(repository), "--fail-under", "0"]) == 1
    output = capsys.readouterr()
    assert not output.err
    assert "python-security (unsupported)" in output.out
    assert "Overall score: unavailable" in output.out
    assert "Score gate: unavailable" in output.out
    assert not (repository / "executed-marker").exists()


@pytest.mark.parametrize(
    "failure", [RuntimeError("secret analyzer failure"), SecurityToolFailed("secret tool failure")]
)
def test_analyzer_failure_is_structured_incomplete_not_internal_error(
    repository: Path,
    failure: Exception,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    scanner = MagicMock()
    scanner.scan.side_effect = failure
    monkeypatch.setattr(cli, "BanditRunner", MagicMock(return_value=scanner))
    assert cli.run(["scan", str(repository)]) == 1
    output = capsys.readouterr()
    assert not output.err
    assert "python-security (failed)" in output.out
    assert "secret" not in output.out


@pytest.mark.parametrize(
    "failure",
    [
        "nonexistent",
        "not-git",
        "python-decode",
        "workflow-decode",
        "source-size",
        "read",
        "origin-validation",
    ],
)
def test_real_input_processing_failures_return_two_with_sanitized_stderr(
    repository: Path,
    failure: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = repository
    if failure == "nonexistent":
        source = repository / "secret-nonexistent"
    elif failure == "not-git":
        source = repository.parent / "secret-not-git"
        source.mkdir()
    elif failure == "python-decode":
        (repository / "bad.py").write_bytes(b"\xff-secret")
    elif failure == "workflow-decode":
        (repository / ".github/workflows/check.yml").write_bytes(b"\xff-secret")
    elif failure == "source-size":
        (repository / "large.py").write_bytes(b"x" * (256 * 1024 + 1))
    elif failure == "read":
        monkeypatch.setattr(
            python_source, "_read_source", MagicMock(side_effect=OSError("secret OS path"))
        )
    elif failure == "origin-validation":
        monkeypatch.setattr(
            cli, "BanditRunner", MagicMock(side_effect=SecurityToolFailed("secret origin path"))
        )
    assert cli.run(["scan", str(source)]) == 2
    output = capsys.readouterr()
    assert not output.out
    assert output.err == "repolens: source acquisition or input processing failed safely.\n"


@pytest.mark.parametrize(
    "content", ["!!python/object/apply:os.system ['touch executed-marker']", "secret: ["]
)
def test_unsupported_yaml_remains_incomplete_and_never_executes(
    repository: Path,
    content: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (repository / ".github/workflows/check.yml").write_text(content, encoding="utf-8")
    scanner = MagicMock()
    scanner.scan.return_value = ()
    monkeypatch.setattr(cli, "BanditRunner", MagicMock(return_value=scanner))
    assert cli.run(["scan", str(repository)]) == 1
    output = capsys.readouterr()
    assert not output.err and "ci-static (unsupported)" in output.out
    assert "secret" not in output.out
    assert not (repository / "executed-marker").exists()


def test_non_python_source_does_not_require_bandit_or_invent_unavailable_work(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert GitRunner().run(("init", "--quiet"), tmp_path, 10).returncode == 0
    (tmp_path / "README.txt").write_text("inert", encoding="utf-8")
    assert cli.run(["scan", str(tmp_path)]) == 0
    output = capsys.readouterr()
    assert not output.err and "Overall score: 100.00" in output.out
    assert "Findings: 2" in output.out
