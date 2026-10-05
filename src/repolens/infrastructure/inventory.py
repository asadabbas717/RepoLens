"""Compose bounded relative data from an open acquisition lease, without reads."""

from repolens.domain.models import AnalysisContext, FileInventory
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.repository_source import RepositoryLease
from repolens.infrastructure.traversal import TraversalLimits, repository_files


def snapshot_context(
    lease: RepositoryLease, limits: TraversalLimits | None = None
) -> AnalysisContext:
    """Publish context only after traversal completes; never retain lease access."""
    _ = lease.root
    try:
        inventory = FileInventory(path.as_posix() for path in repository_files(lease, limits))
    except ValueError:
        raise AcquisitionError("Repository inventory cannot form a safe snapshot") from None
    _ = lease.root
    return AnalysisContext(lease.identity, inventory)
