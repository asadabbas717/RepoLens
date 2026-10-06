"""One inventory and complete admission for the default detached product data."""

from repolens.domain.assessment_configuration import ExclusionPolicy
from repolens.domain.models import AnalysisContext, FileInventory
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.python_source import (
    PythonSourceLimits,
    _admit_python_sources,
    _snapshot_sources,
)
from repolens.infrastructure.repository_source import RepositoryLease
from repolens.infrastructure.traversal import TraversalLimits, repository_file_sizes
from repolens.infrastructure.workflow import _admit_workflows, _snapshot_workflows


def snapshot_analysis_context(
    lease: RepositoryLease,
    python_limits: PythonSourceLimits | None = None,
    traversal_limits: TraversalLimits | None = None,
    *,
    exclusions: ExclusionPolicy | None = None,
) -> AnalysisContext:
    """Admit all required data before any read; no partial or atomic-snapshot claim.

    Reuses the standalone builders' admission/decoding and verified-read controls.
    Dependency manifests are outside the default product's declared capability.
    """
    python_limits = python_limits or PythonSourceLimits()
    traversal_limits = traversal_limits or TraversalLimits()
    try:
        entries = [
            (path.as_posix(), size)
            for path, size in repository_file_sizes(lease, traversal_limits, exclusions=exclusions)
        ]
        sources = _admit_python_sources(entries, python_limits, traversal_limits)
        workflows = _admit_workflows(entries, traversal_limits)
        inventory = FileInventory(
            name for name, size in entries if size <= traversal_limits.max_file_bytes
        )
        python_snapshot = _snapshot_sources(lease, sources, python_limits)
        workflow_snapshot = _snapshot_workflows(lease, workflows)
        _ = lease.root
        return AnalysisContext(
            lease.identity,
            inventory,
            python_snapshot,
            workflows=workflow_snapshot,
        )
    except (OSError, ValueError, RuntimeError, MemoryError):
        raise AcquisitionError("Analysis context could not be created safely") from None
