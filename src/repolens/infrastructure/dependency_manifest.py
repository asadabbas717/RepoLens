"""Root-only UTF-8 manifest snapshots using the existing verified-read boundary."""

from repolens.domain.dependency_manifest import (
    MANIFEST_PATHS,
    MAX_MANIFEST_BYTES,
    DependencyManifest,
    DependencyManifestSnapshot,
)
from repolens.domain.models import AnalysisContext, FileInventory
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.repository_source import RepositoryLease
from repolens.infrastructure.traversal import TraversalLimits, repository_file_sizes
from repolens.infrastructure.verified_read import _read_verified


def _snapshot_manifests(
    lease: RepositoryLease, entries: list[tuple[str, int]]
) -> DependencyManifestSnapshot:
    paths = [path for path, _ in entries]
    if len(set(paths)) != len(paths) or any(path not in MANIFEST_PATHS for path in paths):
        raise AcquisitionError("Dependency manifest read admission failed")
    files: list[DependencyManifest] = []
    try:
        for path, size in sorted(entries):
            if size > MAX_MANIFEST_BYTES:
                raise AcquisitionError("Dependency manifest byte limit exceeded")
            raw = _read_verified(lease, path, MAX_MANIFEST_BYTES)
            if len(raw) != size:
                raise AcquisitionError("Dependency manifest changed since inventory")
            files.append(DependencyManifest(path, raw.decode("utf-8-sig")))
        _ = lease.root
        return DependencyManifestSnapshot(files)
    except (OSError, ValueError, RuntimeError):
        raise AcquisitionError("Dependency manifest snapshot could not be created") from None


def snapshot_dependency_context(
    lease: RepositoryLease, limits: TraversalLimits | None = None
) -> AnalysisContext:
    limits = limits or TraversalLimits()
    paths: list[str] = []
    manifests: list[tuple[str, int]] = []
    for path, size in repository_file_sizes(lease, limits):
        name = path.as_posix()
        if name in MANIFEST_PATHS:
            if size > min(MAX_MANIFEST_BYTES, limits.max_file_bytes):
                raise AcquisitionError("Dependency manifest byte limit exceeded")
            manifests.append((name, size))
        if size <= limits.max_file_bytes:
            paths.append(name)
    try:
        return AnalysisContext(
            lease.identity,
            FileInventory(paths),
            dependency_manifests=_snapshot_manifests(lease, manifests),
        )
    except ValueError:
        raise AcquisitionError("Dependency context could not be created") from None
