"""Bounded detached Python text; no source handles or filesystem capability."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from repolens.domain.paths import require_relative_file_path

MAX_SOURCE_FILE_BYTES = 256 * 1024
MAX_SOURCE_FILES = 512
MAX_SOURCE_TOTAL_BYTES = 4 * 1024 * 1024


def is_python_path(path: str) -> bool:
    """Select exact lowercase .py and .pyi suffixes, including hidden names."""
    return path.endswith((".py", ".pyi"))


@dataclass(frozen=True, slots=True)
class PythonSourceFile:
    path: str
    text: str = field(repr=False)

    def __post_init__(self) -> None:
        require_relative_file_path(self.path)
        try:
            self.path.encode("utf-8")
        except UnicodeError:
            raise ValueError("Python source paths must be valid Unicode") from None
        if not is_python_path(self.path):
            raise ValueError("Python source requires an exact .py or .pyi suffix")
        if not isinstance(self.text, str) or len(self.text) > MAX_SOURCE_FILE_BYTES:
            raise ValueError("Python source text must be a bounded string")
        try:
            size = len(self.text.encode("utf-8"))
        except UnicodeError:
            raise ValueError("Python source text must be valid Unicode") from None
        if size > MAX_SOURCE_FILE_BYTES:
            raise ValueError("Python source text exceeds the file byte limit")


@dataclass(frozen=True, slots=True, init=False)
class PythonSourceSnapshot:
    files: tuple[PythonSourceFile, ...]

    def __init__(self, files: Iterable[PythonSourceFile]) -> None:
        entries: dict[str, PythonSourceFile] = {}
        total = 0
        for source in files:
            if len(entries) >= MAX_SOURCE_FILES:
                raise ValueError("Python source file count exceeded")
            if not isinstance(source, PythonSourceFile) or source.path in entries:
                raise ValueError("Python source entries must be valid and unique")
            total += len(source.text.encode("utf-8"))
            if total > MAX_SOURCE_TOTAL_BYTES:
                raise ValueError("Python source aggregate byte limit exceeded")
            entries[source.path] = source
        object.__setattr__(self, "files", tuple(entries[path] for path in sorted(entries)))
