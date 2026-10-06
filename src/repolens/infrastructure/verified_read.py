"""Private verified regular-file reads, shared only by bounded snapshot builders."""

import os
import stat
from pathlib import Path

from repolens.domain.paths import require_relative_file_path
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.repository_source import RepositoryLease
from repolens.infrastructure.traversal import _excluded_directory, _link_or_reparse


def _checked_path(lease: RepositoryLease, relative: str) -> tuple[Path, os.stat_result]:
    require_relative_file_path(relative)
    root = lease.root
    path = root
    components = ("", *relative.split("/"))
    for index, component in enumerate(components):
        path = path / component
        if _link_or_reparse(path):
            raise AcquisitionError("Repository content path became a link or reparse point")
        if index < len(components) - 1:
            if not stat.S_ISDIR(path.lstat().st_mode):
                raise AcquisitionError("Repository content parent is no longer a directory")
            if index and _excluded_directory(path):
                raise AcquisitionError("Repository content parent became excluded")
    if not path.resolve(strict=True).is_relative_to(root):
        raise AcquisitionError("Repository content path escaped the repository")
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode):
        raise AcquisitionError("Repository content is no longer a regular file")
    return path, metadata


def _signature(metadata: os.stat_result) -> tuple[int, int, int, int]:
    # Windows pathname and descriptor ctime can disagree for unchanged files.
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


def _read_verified(lease: RepositoryLease, relative: str, limit: int) -> bytes:
    path, before = _checked_path(lease, relative)
    if before.st_size > limit:
        raise AcquisitionError("Repository content file byte limit exceeded")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    flags |= getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or _signature(opened) != _signature(before):
            raise AcquisitionError("Repository content changed before reading")
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
            raise AcquisitionError("Repository content changed or exceeded its byte limit")
        return raw
    finally:
        os.close(descriptor)
