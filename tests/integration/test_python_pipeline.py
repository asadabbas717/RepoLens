"""Bounded real source reads and AST/report composition over inert acquired fixtures."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.analyzers.python_static import PythonStaticAnalyzer
from repolens.application.orchestration import AnalyzerPlan, execute_analyzers
from repolens.domain.models import AnalyzerState, Category, FileInventory, Severity
from repolens.domain.python_source import PythonSourceSnapshot
from repolens.domain.report import AnalysisReport
from repolens.domain.scoring import CategoryWeight, ScoringPolicy, SeverityPenalty
from repolens.infrastructure import python_source as boundary
from repolens.infrastructure import verified_read as read_boundary
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.git import GitRunner
from repolens.infrastructure.python_source import PythonSourceLimits, snapshot_python_context
from repolens.infrastructure.repository_source import RepositoryLease, RepositorySource


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    assert GitRunner().run(("init", "--quiet"), tmp_path, 10).returncode == 0
    return tmp_path


def policy() -> ScoringPolicy:
    return ScoringPolicy(
        "synthetic-python-fixture",
        tuple(SeverityPenalty(severity, index * 5) for index, severity in enumerate(Severity)),
        (CategoryWeight(Category.CODE_QUALITY, 1),),
    )


def test_real_pipeline_never_executes_source_or_retains_secrets(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = repository / "executed"
    (repository / "inert.py").write_text(
        "from pathlib import Path\nPath(__file__).with_name('executed').touch()\n"
        "secret = 'secret-credential'\nfrom package import *\n"
        "try:\n    raise RuntimeError('must not execute')\nexcept:\n    pass\n",
        encoding="utf-8",
    )
    with RepositorySource().local(repository) as lease:
        context = snapshot_python_context(lease)
        assert str(lease.root) not in repr(context)
        assert "secret-credential" not in repr(context)
        plan = AnalyzerPlan([PythonStaticAnalyzer()])
        forbidden = MagicMock(side_effect=AssertionError("Analyzer must not perform I/O"))
        with monkeypatch.context() as scope:
            scope.setattr(boundary, "_read_source", forbidden)
            scope.setattr(Path, "open", forbidden)
            scope.setattr(GitRunner, "run", forbidden)
            scope.setattr("subprocess.Popen", forbidden)
            results = execute_analyzers(plan, context)
            report = AnalysisReport(lease.identity, plan.specs, results, policy())
        forbidden.assert_not_called()
        assert results[0].state == AnalyzerState.COMPLETED
        assert {finding.rule_id for finding in report.findings} == {"PY001", "PY002"}
        assert report.score.categories[0].value == 90
        assert "secret-credential" not in repr(report)
        assert not marker.exists()
    assert execute_analyzers(plan, context) == results
    with pytest.raises(AcquisitionError, match="closed"):
        snapshot_python_context(lease)


@pytest.mark.parametrize(
    "raw,expected",
    [
        (b"x=1\n", "x=1\n"),
        (b"\xef\xbb\xbfx=1\n", "x=1\n"),
        (b"# coding: latin-1\nx='\xe9'\n", "# coding: latin-1\nx='\u00e9'\n"),
        (
            b"#!/usr/bin/python\n# coding: latin-1\nx='\xe9'\n",
            "#!/usr/bin/python\n# coding: latin-1\nx='\u00e9'\n",
        ),
        (b"x=1\r\n", "x=1\r\n"),
    ],
)
def test_python_encoding_rules_are_used_without_execution(
    repository: Path, raw: bytes, expected: str
) -> None:
    (repository / "file.py").write_bytes(raw)
    with RepositorySource().local(repository) as lease:
        context = snapshot_python_context(lease)
    assert context.python_sources is not None
    assert context.python_sources.files[0].text == expected
    assert (
        execute_analyzers(AnalyzerPlan([PythonStaticAnalyzer()]), context)[0].state
        == AnalyzerState.COMPLETED
    )


@pytest.mark.parametrize(
    "raw",
    [
        b"# coding: secret-unknown-codec\nx=1",
        b"x='\xff'",
        b"\xef\xbb\xbf# coding: latin-1\nx=1",
        b"# coding: ascii\nx='\xff'",
    ],
)
def test_decode_failures_are_sanitized_and_publish_no_partial_snapshot(
    repository: Path, raw: bytes
) -> None:
    (repository / "a.py").write_text("pass", encoding="utf-8")
    (repository / "z.py").write_bytes(raw)
    with (
        RepositorySource().local(repository) as lease,
        pytest.raises(AcquisitionError, match="decoding failed") as failure,
    ):
        snapshot_python_context(lease)
    assert "secret" not in str(failure.value)
    assert str(repository) not in str(failure.value)
    assert failure.value.__suppress_context__


@pytest.mark.parametrize("mode", ["file", "aggregate", "count", "larger-than-inventory"])
def test_bounds_fail_explicitly_instead_of_omitting_python_source(
    repository: Path, mode: str
) -> None:
    limits = PythonSourceLimits(max_file_bytes=5, max_files=2, max_total_bytes=8)
    (repository / "a.py").write_bytes(b"pass")
    if mode == "file":
        (repository / "b.py").write_bytes(b"x" * 6)
    elif mode == "aggregate":
        (repository / "b.py").write_bytes(b"x" * 5)
    elif mode == "count":
        (repository / "b.py").touch()
        (repository / "c.py").touch()
    else:
        (repository / "b.py").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
        limits = PythonSourceLimits()
    with RepositorySource().local(repository) as lease, pytest.raises(AcquisitionError):
        snapshot_python_context(lease, limits)


@pytest.mark.parametrize("aggregate", [False, True])
def test_decoded_utf8_size_is_also_bounded(repository: Path, aggregate: bool) -> None:
    raw = b"#coding: latin-1\nx='\xe9'"
    (repository / "a.py").write_bytes(raw)
    if aggregate:
        (repository / "b.py").write_bytes(raw)
        limits = PythonSourceLimits(max_total_bytes=len(raw) * 2 + 1)
    else:
        limits = PythonSourceLimits(max_file_bytes=len(raw))
    with (
        RepositorySource().local(repository) as lease,
        pytest.raises(AcquisitionError, match="Decoded Python source"),
    ):
        snapshot_python_context(lease, limits)


def test_selection_exclusions_and_available_empty_sources(repository: Path) -> None:
    (repository / "data.PY").touch()
    (repository / "node_modules").mkdir()
    (repository / "node_modules" / "excluded.py").write_bytes(b"\xff")
    (repository / "venv").mkdir()
    (repository / "venv" / "excluded.py").write_bytes(b"\xff")
    with RepositorySource().local(repository) as lease:
        context = snapshot_python_context(lease)
        assert context.python_sources == PythonSourceSnapshot(())
        assert (
            execute_analyzers(AnalyzerPlan([PythonStaticAnalyzer()]), context)[0].state
            == AnalyzerState.NOT_APPLICABLE
        )
        (repository / "nested").mkdir()
        (repository / "nested" / "file.py").touch()
        (repository / "stub.pyi").touch()
        context = snapshot_python_context(lease)
    assert context.inventory == FileInventory(("data.PY", "nested/file.py", "stub.pyi"))
    assert context.python_sources is not None
    assert tuple(source.path for source in context.python_sources.files) == (
        "nested/file.py",
        "stub.pyi",
    )


@pytest.mark.parametrize(
    "replacement",
    ["missing", "directory", "larger", "link", "parent-link", "parent-env", "same-size"],
)
def test_replacements_between_inventory_and_read_fail_safely(
    repository: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    folder = repository / "src"
    folder.mkdir()
    target = folder / "file.py"
    target.write_bytes(b"pass")
    original = boundary._read_source

    def read(lease: RepositoryLease, relative: str, limit: int) -> bytes:
        if replacement == "missing":
            target.unlink()
        elif replacement == "directory":
            target.unlink()
            target.mkdir()
        elif replacement == "larger":
            target.write_bytes(b"x" * (limit + 1))
        elif replacement == "same-size":
            # A new regular file with the same size is safely read as current data;
            # inventory stores size, not historic inode identity. It is not an atomic snapshot.
            target.unlink()
            target.write_bytes(b"x=1\n")
        elif replacement == "parent-env":
            (folder / "pyvenv.cfg").touch()
        else:
            linked = target if replacement == "link" else folder
            monkeypatch.setattr(read_boundary, "_link_or_reparse", lambda path: path == linked)
        return original(lease, relative, limit)

    with RepositorySource().local(repository) as lease:
        monkeypatch.setattr(boundary, "_read_source", read)
        if replacement == "same-size":
            context = snapshot_python_context(lease)
            assert (
                context.python_sources is not None
                and context.python_sources.files[0].text == "x=1\n"
            )
        else:
            with pytest.raises(AcquisitionError):
                snapshot_python_context(lease)


def test_source_change_during_read_is_detected(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = repository / "file.py"
    target.write_bytes(b"pass")
    original = read_boundary._checked_path
    calls = 0

    def checked(lease: RepositoryLease, relative: str) -> tuple[Path, os.stat_result]:
        nonlocal calls
        calls += 1
        if calls == 2:
            target.write_bytes(b"x" * 50)
        return original(lease, relative)

    with RepositorySource().local(repository) as lease:
        monkeypatch.setattr(read_boundary, "_checked_path", checked)
        with pytest.raises(AcquisitionError, match="changed or exceeded"):
            snapshot_python_context(lease, PythonSourceLimits(max_file_bytes=5))


@pytest.mark.parametrize("value", [0, True, -1, 10**9])
def test_source_limits_are_positive_and_cannot_raise_hard_ceilings(value: int) -> None:
    with pytest.raises(ValueError):
        PythonSourceLimits(max_file_bytes=value)


def test_syntax_rejection_cannot_produce_a_numeric_report(repository: Path) -> None:
    (repository / "file.py").write_text("def broken(:", encoding="utf-8")
    with RepositorySource().local(repository) as lease:
        context = snapshot_python_context(lease)
        plan = AnalyzerPlan([PythonStaticAnalyzer()])
        report = AnalysisReport(
            lease.identity, plan.specs, execute_analyzers(plan, context), policy()
        )
    assert report.results[0].state == AnalyzerState.UNSUPPORTED
    assert report.score.value is None


def test_large_non_python_file_is_omitted_but_python_selection_is_not(repository: Path) -> None:
    (repository / "data.bin").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    (repository / "file.py").write_bytes(b"pass")
    with RepositorySource().local(repository) as lease:
        context = snapshot_python_context(lease)
    assert context.inventory == FileInventory(("file.py",))


def test_non_directory_parent_before_read_is_rejected(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = repository / "src"
    parent.mkdir()
    target = parent / "file.py"
    target.write_bytes(b"pass")
    original = boundary._read_source

    def read(lease: RepositoryLease, relative: str, limit: int) -> bytes:
        target.unlink()
        parent.rmdir()
        parent.touch()
        return original(lease, relative, limit)

    with RepositorySource().local(repository) as lease:
        monkeypatch.setattr(boundary, "_read_source", read)
        with pytest.raises(AcquisitionError, match="parent is no longer a directory"):
            snapshot_python_context(lease)


def test_resolved_source_cannot_escape_root(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = repository / "file.py"
    target.write_bytes(b"pass")
    original = Path.resolve

    def resolve(path: Path, strict: bool = False) -> Path:
        if path == target:
            return repository.parent / "outside.py"
        return original(path, strict=strict)

    with RepositorySource().local(repository) as lease:
        monkeypatch.setattr(Path, "resolve", resolve)
        with pytest.raises(AcquisitionError, match="escaped"):
            snapshot_python_context(lease)


def test_open_descriptor_must_match_checked_file_identity(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = repository / "file.py"
    target.write_bytes(b"pass")
    peer = repository / "peer.txt"
    peer.write_bytes(b"pass")
    original = read_boundary._checked_path

    def checked(lease: RepositoryLease, relative: str) -> tuple[Path, os.stat_result]:
        path, _ = original(lease, relative)
        return path, peer.lstat()

    with RepositorySource().local(repository) as lease:
        monkeypatch.setattr(read_boundary, "_checked_path", checked)
        with pytest.raises(AcquisitionError, match="changed before reading"):
            snapshot_python_context(lease)
    target.unlink()  # Windows also verifies that the opened descriptor was closed.


def test_file_growth_between_inventory_and_read_cannot_publish_current_partial_data(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = repository / "file.py"
    target.write_bytes(b"pass")
    original = boundary._read_source

    def read(lease: RepositoryLease, relative: str, limit: int) -> bytes:
        target.write_bytes(b"x=1\npass\n")
        return original(lease, relative, limit)

    with RepositorySource().local(repository) as lease:
        monkeypatch.setattr(boundary, "_read_source", read)
        with pytest.raises(AcquisitionError, match="changed since inventory"):
            snapshot_python_context(lease)


def test_lease_closes_before_source_snapshot_publication(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / "file.py").write_bytes(b"pass")
    original = boundary._read_source

    def read(lease: RepositoryLease, relative: str, limit: int) -> bytes:
        raw = original(lease, relative, limit)
        lease.close()
        return raw

    with RepositorySource().local(repository) as lease:
        monkeypatch.setattr(boundary, "_read_source", read)
        with pytest.raises(AcquisitionError, match="closed"):
            snapshot_python_context(lease)
