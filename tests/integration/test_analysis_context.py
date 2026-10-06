"""Combined admission is one bounded traversal, with shared verified reads."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.domain.python_source import (
    MAX_SOURCE_FILE_BYTES,
    MAX_SOURCE_FILES,
    MAX_SOURCE_TOTAL_BYTES,
)
from repolens.domain.workflow import (
    MAX_WORKFLOW_BYTES,
    MAX_WORKFLOW_FILES,
    MAX_WORKFLOW_TOTAL_BYTES,
)
from repolens.infrastructure import analysis_context as combined
from repolens.infrastructure import python_source, verified_read, workflow
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.git import GitRunner
from repolens.infrastructure.python_source import PythonSourceLimits, snapshot_python_context
from repolens.infrastructure.repository_source import RepositoryLease, RepositorySource
from repolens.infrastructure.traversal import TraversalLimits, repository_file_sizes
from repolens.infrastructure.workflow import snapshot_workflow_context


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    assert GitRunner().run(("init", "--quiet"), tmp_path, 10).returncode == 0
    folder = tmp_path / ".github/workflows"
    folder.mkdir(parents=True)
    return tmp_path


def test_combined_snapshot_has_one_inventory_and_matches_standalone_contracts(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / "app.py").write_bytes(b"# coding: latin-1\nx='\xe9'\n")
    (repository / "api.pyi").write_text("value: int", encoding="utf-8")
    (repository / ".github/workflows/check.yml").write_bytes(b"\xef\xbb\xbfon: push\n")
    (repository / "requirements.txt").write_bytes(b"secret unsupported manifest \xff")
    (repository / "pyproject.toml").write_bytes(b"secret malformed \xff")
    (repository / "data.bin").write_bytes(b"x" * (2 * 1024 * 1024 + 1))
    inventory = MagicMock(wraps=repository_file_sizes)
    monkeypatch.setattr(combined, "repository_file_sizes", inventory)
    with RepositorySource().local(repository) as lease:
        data = combined.snapshot_analysis_context(lease)
        python = snapshot_python_context(lease)
        workflows = snapshot_workflow_context(lease)
    inventory.assert_called_once()
    assert data.inventory == python.inventory == workflows.inventory
    assert data.python_sources == python.python_sources
    assert data.workflows == workflows.workflows
    assert data.dependency_manifests is None
    assert data.inventory is not None and "data.bin" not in data.inventory.paths
    assert "secret" not in repr(data)


@pytest.mark.parametrize(
    "budget",
    [
        "python-file",
        "python-count",
        "python-aggregate",
        "workflow-file",
        "workflow-count",
        "workflow-aggregate",
        "python-traversal",
        "workflow-traversal",
        "duplicate-inventory",
    ],
)
def test_every_admission_failure_happens_before_any_source_or_workflow_read(
    repository: Path, budget: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    entries = [(Path("app.py"), 4), (Path(".github/workflows/check.yml"), 4)]
    if budget == "python-file":
        entries[0] = (Path("app.py"), MAX_SOURCE_FILE_BYTES + 1)
    elif budget == "python-count":
        entries.extend((Path(f"source{i}.py"), 0) for i in range(MAX_SOURCE_FILES))
    elif budget == "python-aggregate":
        entries.extend(
            (Path(f"source{i}.py"), MAX_SOURCE_FILE_BYTES)
            for i in range(MAX_SOURCE_TOTAL_BYTES // MAX_SOURCE_FILE_BYTES + 1)
        )
    elif budget == "workflow-file":
        entries[1] = (Path(".github/workflows/check.yml"), MAX_WORKFLOW_BYTES + 1)
    elif budget == "workflow-count":
        entries.extend((Path(f".github/workflows/{i}.yml"), 0) for i in range(MAX_WORKFLOW_FILES))
    elif budget == "workflow-aggregate":
        entries.extend(
            (Path(f".github/workflows/{i}.yml"), MAX_WORKFLOW_BYTES)
            for i in range(MAX_WORKFLOW_TOTAL_BYTES // MAX_WORKFLOW_BYTES + 1)
        )
    elif budget == "duplicate-inventory":
        entries.append(entries[0])
    elif budget == "workflow-traversal":
        entries[0] = (Path("app.py"), 2)
    monkeypatch.setattr(combined, "repository_file_sizes", MagicMock(return_value=iter(entries)))
    forbidden = MagicMock(side_effect=AssertionError("Complete all admissions first"))
    monkeypatch.setattr(python_source, "_read_source", forbidden)
    monkeypatch.setattr(workflow, "_read_verified", forbidden)
    limits = TraversalLimits(max_file_bytes=3) if budget.endswith("traversal") else None
    with RepositorySource().local(repository) as lease, pytest.raises(AcquisitionError):
        combined.snapshot_analysis_context(lease, traversal_limits=limits)
    forbidden.assert_not_called()


@pytest.mark.parametrize("aggregate", [False, True])
def test_decoded_python_expansion_is_bounded_in_combined_context(
    repository: Path, aggregate: bool
) -> None:
    raw = b"#coding:latin-1\nx='\xe9'"
    (repository / "a.py").write_bytes(raw)
    if aggregate:
        (repository / "b.py").write_bytes(raw)
        limits = PythonSourceLimits(max_total_bytes=len(raw) * 2 + 1)
    else:
        limits = PythonSourceLimits(max_file_bytes=len(raw))
    with RepositorySource().local(repository) as lease, pytest.raises(AcquisitionError):
        combined.snapshot_analysis_context(lease, python_limits=limits)


@pytest.mark.parametrize("kind", ["python", "workflow"])
@pytest.mark.parametrize(
    "mode",
    ["os-error", "decode", "growth", "directory", "reparse", "escape", "closed-lease", "memory"],
)
def test_combined_content_failure_never_publishes_partial_data_or_raw_diagnostics(
    repository: Path, kind: str, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / "app.py").write_bytes(b"pass")
    (repository / ".github/workflows/check.yml").write_bytes(b"on: push")
    target = repository / ("app.py" if kind == "python" else ".github/workflows/check.yml")
    original = verified_read._read_verified

    def read(lease: RepositoryLease, name: str, limit: int) -> bytes:
        if mode == "os-error":
            raise OSError("secret OS path")
        if mode == "memory":
            raise MemoryError("secret resource diagnostics")
        if mode == "decode":
            # Preserve admitted length so decoding, rather than growth, rejects it.
            return b"\xff" * target.stat().st_size
        if mode == "growth":
            target.write_bytes(b"secret grown data")
        elif mode == "directory":
            target.unlink()
            target.mkdir()
        elif mode == "reparse":
            with monkeypatch.context() as scope:
                scope.setattr(verified_read, "_link_or_reparse", lambda path: path == target)
                return original(lease, name, limit)
        elif mode == "escape":
            return original(lease, "../outside-secret", limit)
        elif mode == "closed-lease":
            raw = original(lease, name, limit)
            lease.close()
            return raw
        return original(lease, name, limit)

    monkeypatch.setattr(
        python_source if kind == "python" else workflow,
        "_read_source" if kind == "python" else "_read_verified",
        read,
    )
    with RepositorySource().local(repository) as lease, pytest.raises(AcquisitionError) as raised:
        combined.snapshot_analysis_context(lease)
    assert "secret" not in str(raised.value)
    assert str(repository) not in str(raised.value)


def test_empty_context_is_available_and_closed_lease_cannot_be_reused(repository: Path) -> None:
    with RepositorySource().local(repository) as lease:
        data = combined.snapshot_analysis_context(lease)
    assert data.python_sources is not None and data.python_sources.files == ()
    assert data.workflows is not None and data.workflows.files == ()
    with pytest.raises(AcquisitionError, match="closed"):
        combined.snapshot_analysis_context(lease)


def test_traversal_limit_is_not_weakened_by_combined_builder(repository: Path) -> None:
    (repository / "app.py").write_bytes(b"pass")
    with (
        RepositorySource().local(repository) as lease,
        pytest.raises(AcquisitionError, match="entry limit"),
    ):
        combined.snapshot_analysis_context(lease, traversal_limits=TraversalLimits(max_entries=1))
