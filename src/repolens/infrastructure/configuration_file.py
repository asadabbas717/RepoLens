"""Bounded explicit user-file reads, no discovery or target configuration trust."""

import os
import stat
from os import close as _close
from os import fstat as _fstat
from os import open as _open
from os import read as _read
from pathlib import Path

from repolens.application.configuration import (
    MAX_CONFIG_BYTES,
    ScanConfiguration,
    parse_configuration,
)
from repolens.domain.assessment_configuration import ConfigurationError


def _checked_file(path: Path) -> os.stat_result:
    for candidate in (*reversed(path.parents), path):
        metadata = candidate.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ConfigurationError("Linked or reparse configuration paths are unsupported")
    if not stat.S_ISREG(metadata.st_mode):
        raise ConfigurationError("Configuration must be a regular file")
    return metadata


def _signature(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns


def load_configuration(path: Path) -> ScanConfiguration:
    """Reject links at every component, bounded descriptor reads, then one parse."""
    try:
        if str(path).startswith(("\\\\", "//")):
            raise ConfigurationError("Network/device configuration paths are unsupported")
        if ".." in path.parts:
            raise ConfigurationError("Configuration path must not contain parent segments")
        path = path.absolute()
        before = _checked_file(path)
        if before.st_size > MAX_CONFIG_BYTES:
            raise ConfigurationError("Configuration byte limit exceeded")
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_BINARY", 0)
        )
        descriptor = _open(path, flags)
        try:
            opened = _fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode) or _signature(opened) != _signature(before):
                raise ConfigurationError("Configuration changed before reading")
            _checked_file(path)
            remaining = MAX_CONFIG_BYTES + 1
            chunks: list[bytes] = []
            while remaining:
                block = _read(descriptor, min(remaining, 65_536))
                if not block:
                    break
                chunks.append(block)
                remaining -= len(block)
            raw = b"".join(chunks)
            if (
                len(raw) > MAX_CONFIG_BYTES
                or len(raw) != opened.st_size
                or _signature(_fstat(descriptor)) != _signature(opened)
                or _signature(_checked_file(path)) != _signature(opened)
            ):
                raise ConfigurationError("Configuration changed or exceeded its byte limit")
        finally:
            _close(descriptor)
        return parse_configuration(raw)
    except (OSError, ValueError, RuntimeError, MemoryError):
        raise ConfigurationError("Configuration could not be loaded safely") from None
