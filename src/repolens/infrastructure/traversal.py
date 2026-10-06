"""Bounded path inventory only; no content reading or Git ignore emulation."""

import os
import stat
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from repolens.infrastructure.errors import AcquisitionError, TraversalLimitExceeded
from repolens.infrastructure.repository_source import RepositoryLease

EXCLUDED_DIRECTORIES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "build",
        "dist",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".uv-cache",
        "htmlcov",
    }
)


@dataclass(frozen=True, slots=True)
class TraversalLimits:
    max_entries: int = 20_000
    max_depth: int = 32
    max_file_bytes: int = 2 * 1024 * 1024

    def __post_init__(self) -> None:
        if any(
            type(value) is not int or value < 1
            for value in (
                self.max_entries,
                self.max_depth,
                self.max_file_bytes,
            )
        ):
            raise ValueError("Traversal limits must be positive integers")


def _link_or_reparse(path: Path) -> bool:
    metadata = path.lstat()
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _excluded_directory(path: Path) -> bool:
    return (
        path.name in EXCLUDED_DIRECTORIES
        or path.name.startswith(".venv-")
        or (path / "pyvenv.cfg").exists(follow_symlinks=False)
    )


def repository_file_sizes(
    lease: RepositoryLease,
    limits: TraversalLimits | None = None,
) -> Iterator[tuple[Path, int]]:
    """Yield bounded relative regular-file metadata; no content reads.

    Inventory is not an atomic snapshot and must not be used as authorization
    for later unchecked reads. No .gitignore parsing or binary content sniffing.
    """
    limits = limits or TraversalLimits()
    root = lease.root
    stack = [(root, 0)]
    visited = 0
    try:
        while stack:
            _ = lease.root  # Recheck resource lifetime between directories.
            directory, depth = stack.pop()
            if _link_or_reparse(directory) or not directory.resolve().is_relative_to(root):
                raise AcquisitionError("Repository directory changed during inventory")
            with os.scandir(directory) as entries:
                children = []
                for entry in entries:
                    visited += 1
                    if visited > limits.max_entries:
                        raise TraversalLimitExceeded("Repository entry limit exceeded")
                    children.append(Path(entry.path))
            for path in sorted(children, reverse=True):
                _ = lease.root
                if path.name == ".git" or _link_or_reparse(path):
                    continue
                metadata = path.lstat()
                if stat.S_ISDIR(metadata.st_mode):
                    if _excluded_directory(path):
                        continue
                    if depth + 1 > limits.max_depth:
                        raise TraversalLimitExceeded("Repository depth limit exceeded")
                    stack.append((path, depth + 1))
                elif stat.S_ISREG(metadata.st_mode):
                    yield path.relative_to(root), metadata.st_size
    except OSError:
        raise AcquisitionError("Repository inventory became inaccessible") from None


def repository_files(
    lease: RepositoryLease, limits: TraversalLimits | None = None
) -> Iterator[Path]:
    """Yield eligible relative files, retaining Phase 2's oversized-file omission."""
    limits = limits or TraversalLimits()
    for path, size in repository_file_sizes(lease, limits):
        if size <= limits.max_file_bytes:
            yield path
