"""Read selected Python files under an active lease with bounded verified reads."""

import io
import tokenize
from dataclasses import dataclass

from repolens.domain.dependency_manifest import MANIFEST_PATHS, MAX_MANIFEST_BYTES
from repolens.domain.models import AnalysisContext, FileInventory
from repolens.domain.python_source import (
    MAX_SOURCE_FILE_BYTES,
    MAX_SOURCE_FILES,
    MAX_SOURCE_TOTAL_BYTES,
    PythonSourceFile,
    PythonSourceSnapshot,
    is_python_path,
)
from repolens.infrastructure.dependency_manifest import _snapshot_manifests
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.repository_source import RepositoryLease
from repolens.infrastructure.traversal import (
    TraversalLimits,
    repository_file_sizes,
)
from repolens.infrastructure.verified_read import _read_verified


@dataclass(frozen=True, slots=True)
class PythonSourceLimits:
    max_file_bytes: int = MAX_SOURCE_FILE_BYTES
    max_files: int = MAX_SOURCE_FILES
    max_total_bytes: int = MAX_SOURCE_TOTAL_BYTES

    def __post_init__(self) -> None:
        for value, ceiling in (
            (self.max_file_bytes, MAX_SOURCE_FILE_BYTES),
            (self.max_files, MAX_SOURCE_FILES),
            (self.max_total_bytes, MAX_SOURCE_TOTAL_BYTES),
        ):
            if type(value) is not int or not 1 <= value <= ceiling:
                raise ValueError(
                    "Python source limits must be positive integers within hard ceilings"
                )


def _read_source(lease: RepositoryLease, relative: str, limit: int) -> bytes:
    return _read_verified(lease, relative, limit)


def _decode_source(raw: bytes) -> str:
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        return raw.decode(encoding)
    except (UnicodeError, LookupError, SyntaxError):
        raise AcquisitionError("Python source decoding failed") from None


def _admit_python_sources(
    entries: list[tuple[str, int]], limits: PythonSourceLimits, traversal: TraversalLimits
) -> list[tuple[str, int]]:
    selected: list[tuple[str, int]] = []
    total = 0
    for name, size in entries:
        if is_python_path(name):
            if size > min(limits.max_file_bytes, traversal.max_file_bytes):
                raise AcquisitionError("Python source file byte limit exceeded")
            total += size
            if total > limits.max_total_bytes:
                raise AcquisitionError("Python source aggregate byte limit exceeded")
            selected.append((name, size))
            if len(selected) > limits.max_files:
                raise AcquisitionError("Python source file count exceeded")
    return selected


def _snapshot_sources(
    lease: RepositoryLease, selected: list[tuple[str, int]], limits: PythonSourceLimits
) -> PythonSourceSnapshot:
    files: list[PythonSourceFile] = []
    text_total = 0
    for name, admitted_size in sorted(selected):
        raw = _read_source(lease, name, limits.max_file_bytes)
        if len(raw) != admitted_size:
            raise AcquisitionError("Python source changed since inventory")
        text = _decode_source(raw)
        text_size = len(text.encode("utf-8"))
        if text_size > limits.max_file_bytes:
            raise AcquisitionError("Decoded Python source file byte limit exceeded")
        text_total += text_size
        if text_total > limits.max_total_bytes:
            raise AcquisitionError("Decoded Python source aggregate byte limit exceeded")
        files.append(PythonSourceFile(name, text))
    _ = lease.root
    return PythonSourceSnapshot(files)


def snapshot_python_context(
    lease: RepositoryLease,
    limits: PythonSourceLimits | None = None,
    traversal_limits: TraversalLimits | None = None,
    *,
    include_dependency_manifests: bool = False,
) -> AnalysisContext:
    """Inventory once, then read selected files; publish no partial data on error."""
    limits = limits or PythonSourceLimits()
    traversal_limits = traversal_limits or TraversalLimits()
    _ = lease.root
    try:
        paths: list[str] = []
        entries: list[tuple[str, int]] = []
        manifests: list[tuple[str, int]] = []
        for relative, size in repository_file_sizes(lease, traversal_limits):
            name = relative.as_posix()
            entries.append((name, size))
            if include_dependency_manifests and name in MANIFEST_PATHS:
                if size > min(MAX_MANIFEST_BYTES, traversal_limits.max_file_bytes):
                    raise AcquisitionError("Dependency manifest byte limit exceeded")
                manifests.append((name, size))
            if size <= traversal_limits.max_file_bytes:
                paths.append(name)
        selected = _admit_python_sources(entries, limits, traversal_limits)
        inventory = FileInventory(paths)
        sources = _snapshot_sources(lease, selected, limits)
        manifest_snapshot = (
            _snapshot_manifests(lease, manifests) if include_dependency_manifests else None
        )
        return AnalysisContext(lease.identity, inventory, sources, manifest_snapshot)
    except (OSError, ValueError, RuntimeError):
        raise AcquisitionError("Python source snapshot could not be created") from None
