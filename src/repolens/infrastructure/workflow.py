"""Inventory once and read only admitted workflow files under an active lease."""

from repolens.domain.models import AnalysisContext, FileInventory
from repolens.domain.workflow import (
    MAX_WORKFLOW_BYTES,
    MAX_WORKFLOW_FILES,
    MAX_WORKFLOW_TOTAL_BYTES,
    WorkflowFile,
    WorkflowSnapshot,
    is_workflow_path,
)
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.repository_source import RepositoryLease
from repolens.infrastructure.traversal import TraversalLimits, repository_file_sizes
from repolens.infrastructure.verified_read import _read_verified


def _admit_workflows(
    entries: list[tuple[str, int]], limits: TraversalLimits
) -> list[tuple[str, int]]:
    selected: list[tuple[str, int]] = []
    total = 0
    for name, size in entries:
        if is_workflow_path(name):
            if size > min(MAX_WORKFLOW_BYTES, limits.max_file_bytes):
                raise AcquisitionError("Workflow byte limit exceeded")
            selected.append((name, size))
            total += size
            if len(selected) > MAX_WORKFLOW_FILES or total > MAX_WORKFLOW_TOTAL_BYTES:
                raise AcquisitionError("Workflow snapshot resource limit exceeded")
    return selected


def _snapshot_workflows(
    lease: RepositoryLease, selected: list[tuple[str, int]]
) -> WorkflowSnapshot:
    files: list[WorkflowFile] = []
    for name, size in sorted(selected):
        raw = _read_verified(lease, name, MAX_WORKFLOW_BYTES)
        if len(raw) != size:
            raise AcquisitionError("Workflow changed since inventory")
        files.append(WorkflowFile(name, raw.decode("utf-8-sig")))
    _ = lease.root
    return WorkflowSnapshot(files)


def snapshot_workflow_context(
    lease: RepositoryLease, limits: TraversalLimits | None = None
) -> AnalysisContext:
    limits = limits or TraversalLimits()
    try:
        paths: list[str] = []
        entries: list[tuple[str, int]] = []
        for relative, size in repository_file_sizes(lease, limits):
            name = relative.as_posix()
            entries.append((name, size))
            if size <= limits.max_file_bytes:
                paths.append(name)
        selected = _admit_workflows(entries, limits)
        inventory = FileInventory(paths)
        workflows = _snapshot_workflows(lease, selected)
        return AnalysisContext(lease.identity, inventory, workflows=workflows)
    except (OSError, ValueError, RuntimeError):
        raise AcquisitionError("Workflow snapshot could not be created") from None
