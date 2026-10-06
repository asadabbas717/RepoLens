"""Whitelisted, bounded detached manifest text; never an execution capability."""

from collections.abc import Iterable
from dataclasses import dataclass, field

MANIFEST_PATHS = frozenset({"requirements.txt", "pyproject.toml"})
MAX_MANIFEST_BYTES = 64 * 1024
MAX_MANIFEST_TOTAL_BYTES = 128 * 1024


@dataclass(frozen=True, slots=True)
class DependencyManifest:
    path: str
    text: str = field(repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.path, str) or self.path not in MANIFEST_PATHS:
            raise ValueError("Dependency manifests require an exact supported root filename")
        if not isinstance(self.text, str) or len(self.text) > MAX_MANIFEST_BYTES:
            raise ValueError("Manifest text must be bounded")
        try:
            size = len(self.text.encode("utf-8"))
        except UnicodeError:
            raise ValueError("Manifest text must be valid Unicode") from None
        if size > MAX_MANIFEST_BYTES:
            raise ValueError("Manifest byte limit exceeded")


@dataclass(frozen=True, slots=True, init=False)
class DependencyManifestSnapshot:
    files: tuple[DependencyManifest, ...]

    def __init__(self, files: Iterable[DependencyManifest]) -> None:
        # Two unique whitelisted paths, each <=64 KiB, imply <=128 KiB total.
        entries: dict[str, DependencyManifest] = {}
        for entry in files:
            if not isinstance(entry, DependencyManifest) or entry.path in entries:
                raise ValueError("Manifest entries must be valid and unique")
            entries[entry.path] = entry
        object.__setattr__(self, "files", tuple(entries[path] for path in sorted(entries)))
