"""User-owned output publication: UTF-8/LF, complete sibling, no overwrite."""

from os import close as _close
from os import fdopen as _fdopen
from os import fsync as _fsync
from os import link as _link
from pathlib import Path
from tempfile import mkstemp


class OutputError(Exception):
    """Controlled destination or output-processing failure, with no OS diagnostics."""


def _require_absent(path: Path) -> None:
    try:
        path.lstat()
    except FileNotFoundError:
        return
    raise OutputError("Output destination already exists")


def prepare_output(path: Path) -> Path:
    """Validate before acquisition; canonicalize an existing parent without mkdir."""
    try:
        if path.name in {"", ".", ".."}:
            raise OutputError("Output destination must name a new file")
        parent = path.parent.resolve(strict=True)
        if not parent.is_dir():
            raise OutputError("Output parent must be a directory")
        destination = parent / path.name
        _require_absent(destination)
        return destination
    except (OSError, ValueError, RuntimeError):
        raise OutputError("Output destination could not be validated") from None


def publish_report(destination: Path, text: str) -> None:
    """Hard-link a flushed/closed sibling atomically; fail if destination exists.

    Requires a filesystem supporting same-directory hard links. Never use replace,
    which would silently clobber a destination appearing after preflight.
    The parent directory is user-owned and must remain stable during publication.
    """
    temporary: Path | None = None
    descriptor: int | None = None
    try:
        _require_absent(destination)
        descriptor, name = mkstemp(
            prefix=".repolens-report-", suffix=".tmp", dir=destination.parent
        )
        temporary = Path(name)
        stream = _fdopen(descriptor, "w", encoding="utf-8", newline="\n")
        descriptor = None  # The stream now owns closure, including error paths.
        with stream:
            stream.write(text)
            stream.flush()
            _fsync(stream.fileno())
        _link(temporary, destination)
    except (OSError, ValueError, UnicodeError):
        raise OutputError("Report output could not be published") from None
    finally:
        try:
            try:
                if descriptor is not None:
                    _close(descriptor)
            finally:
                if temporary is not None:
                    temporary.unlink()
        except OSError:
            raise OutputError("Report output cleanup failed") from None
