"""Lexical repository-relative locations, without filesystem capabilities."""

from pathlib import PurePosixPath, PureWindowsPath


def require_relative_file_path(value: str) -> None:
    """Validate a canonical relative POSIX location without performing I/O."""
    if not isinstance(value, str):
        raise ValueError("file_path must be a normalized relative POSIX file path")
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or PureWindowsPath(value).drive
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or value == "."
    ):
        raise ValueError("file_path must be a normalized relative POSIX file path")
