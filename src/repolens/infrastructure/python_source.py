"""Read selected Python files under an active lease with bounded verified reads."""

import io
import os
import stat
import tokenize
from dataclasses import dataclass
from pathlib import Path

from repolens.domain.models import AnalysisContext, FileInventory
from repolens.domain.paths import require_relative_file_path
from repolens.domain.python_source import (
    MAX_SOURCE_FILE_BYTES,
    MAX_SOURCE_FILES,
    MAX_SOURCE_TOTAL_BYTES,
    PythonSourceFile,
    PythonSourceSnapshot,
    is_python_path,
)
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.repository_source import RepositoryLease
from repolens.infrastructure.traversal import (
    TraversalLimits,
    _excluded_directory,
    _link_or_reparse,
    repository_file_sizes,
)


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


def _checked_path(lease: RepositoryLease, relative: str) -> tuple[Path, os.stat_result]:
    require_relative_file_path(relative)
    root = lease.root
    path = root
    components = ("", *relative.split("/"))
    for index, component in enumerate(components):
        path = path / component
        if _link_or_reparse(path):
            raise AcquisitionError("Python source path became a link or reparse point")
        if index < len(components) - 1:
            if not stat.S_ISDIR(path.lstat().st_mode):
                raise AcquisitionError("Python source parent is no longer a directory")
            if index and _excluded_directory(path):
                raise AcquisitionError("Python source parent became excluded")
    if not path.resolve(strict=True).is_relative_to(root):
        raise AcquisitionError("Python source path escaped the repository")
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise AcquisitionError("Python source is no longer a regular file")
    return path, metadata


def _signature(metadata: os.stat_result) -> tuple[int, int, int, int]:
    # Windows pathname and descriptor ctime can disagree for unchanged files.
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


def _read_source(lease: RepositoryLease, relative: str, limit: int) -> bytes:
    path, before = _checked_path(lease, relative)
    if before.st_size > limit:
        raise AcquisitionError("Python source file byte limit exceeded")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _signature(opened) != _signature(before):
            raise AcquisitionError("Python source changed before reading")
        _checked_path(lease, relative)
        remaining = limit + 1
        chunks: list[bytes] = []
        while remaining:
            block = os.read(descriptor, min(remaining, 65_536))
            if not block:
                break
            chunks.append(block)
            remaining -= len(block)
        raw = b"".join(chunks)
        after = os.fstat(descriptor)
        _, current = _checked_path(lease, relative)
        if (
            len(raw) > limit
            or len(raw) != opened.st_size
            or _signature(after) != _signature(opened)
            or _signature(current) != _signature(opened)
        ):
            raise AcquisitionError("Python source changed or exceeded its byte limit")
        return raw
    finally:
        os.close(descriptor)


def _decode_source(raw: bytes) -> str:
    try:
        encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        return raw.decode(encoding)
    except (UnicodeError, LookupError, SyntaxError):
        raise AcquisitionError("Python source decoding failed") from None


def snapshot_python_context(
    lease: RepositoryLease,
    limits: PythonSourceLimits | None = None,
    traversal_limits: TraversalLimits | None = None,
) -> AnalysisContext:
    """Inventory once, then read selected files; publish no partial data on error."""
    limits = limits or PythonSourceLimits()
    traversal_limits = traversal_limits or TraversalLimits()
    _ = lease.root
    try:
        paths: list[str] = []
        selected: list[tuple[str, int]] = []
        raw_total = 0
        for relative, size in repository_file_sizes(lease, traversal_limits):
            name = relative.as_posix()
            if is_python_path(name):
                if size > min(limits.max_file_bytes, traversal_limits.max_file_bytes):
                    raise AcquisitionError("Python source file byte limit exceeded")
                raw_total += size
                if raw_total > limits.max_total_bytes:
                    raise AcquisitionError("Python source aggregate byte limit exceeded")
                selected.append((name, size))
                if len(selected) > limits.max_files:
                    raise AcquisitionError("Python source file count exceeded")
            if size <= traversal_limits.max_file_bytes:
                paths.append(name)
        inventory = FileInventory(paths)
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
        return AnalysisContext(lease.identity, inventory, PythonSourceSnapshot(files))
    except (OSError, ValueError, RuntimeError):
        raise AcquisitionError("Python source snapshot could not be created") from None
