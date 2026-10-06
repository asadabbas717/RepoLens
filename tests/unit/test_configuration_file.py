"""Explicit config resource failures are bounded/sanitized with owned mock bindings."""

import os
import stat
from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest

from repolens.domain.assessment_configuration import ConfigurationError
from repolens.infrastructure import configuration_file as boundary
from repolens.infrastructure.configuration_file import load_configuration


def test_regular_file_is_parsed_once_and_exact_size_ceiling_is_supported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.toml"
    raw = b"schema_version=1\n#" + b"x" * (64 * 1024 - len(b"schema_version=1\n#"))
    path.write_bytes(raw)
    from repolens.application.configuration import parse_configuration

    parse = MagicMock(wraps=parse_configuration)
    monkeypatch.setattr(boundary, "parse_configuration", parse)
    assert load_configuration(path).applied.schema_version == 1
    parse.assert_called_once_with(raw)


@pytest.mark.parametrize(
    "mode", ["missing", "directory", "oversized", "invalid-utf8", "invalid-toml", "parent-segment"]
)
def test_bad_config_resources_are_safe_failures(tmp_path: Path, mode: str) -> None:
    path = tmp_path / "secret-config.toml"
    if mode == "directory":
        path.mkdir()
    elif mode == "oversized":
        path.write_bytes(b"x" * (64 * 1024 + 1))
    elif mode == "invalid-utf8":
        path.write_bytes(b"\xffsecret")
    elif mode == "invalid-toml":
        path.write_bytes(b"secret=[")
    elif mode == "parent-segment":
        path = tmp_path / "../secret-config.toml"
    with pytest.raises(ConfigurationError) as raised:
        load_configuration(path)
    assert "secret" not in str(raised.value) and str(tmp_path) not in str(raised.value)


def test_network_configuration_path_fails_before_filesystem_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    inspected = MagicMock(side_effect=AssertionError("No remote config access"))
    monkeypatch.setattr(boundary, "_checked_file", inspected)
    with pytest.raises(ConfigurationError):
        load_configuration(Path("//server/share/secret-config.toml"))
    inspected.assert_not_called()


@pytest.mark.parametrize("location", ["file", "parent"])
@pytest.mark.parametrize("kind", ["link", "reparse"])
def test_link_and_reparse_config_components_are_rejected_before_open(
    tmp_path: Path, location: str, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.toml"
    path.write_bytes(b"schema_version=1")
    selected = path if location == "file" else tmp_path
    original = Path.lstat

    def lstat(candidate: Path) -> os.stat_result:
        if candidate == selected:
            return cast(
                os.stat_result,
                SimpleNamespace(
                    st_mode=stat.S_IFLNK if kind == "link" else stat.S_IFREG,
                    st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT
                    if kind == "reparse"
                    else 0,
                ),
            )
        return original(candidate)

    opened = MagicMock(side_effect=AssertionError("No linked config open"))
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(boundary, "_open", opened)
    with pytest.raises(ConfigurationError):
        load_configuration(path)
    opened.assert_not_called()


@pytest.mark.parametrize("mode", ["open", "read", "close", "identity", "growth", "changed-mtime"])
def test_read_change_and_descriptor_errors_do_not_leak_or_leave_open_file(
    tmp_path: Path, mode: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config.toml"
    path.write_bytes(b"schema_version=1")
    original_close = os.close
    original_check = boundary._checked_file
    if mode == "open":
        monkeypatch.setattr(boundary, "_open", MagicMock(side_effect=OSError("secret open path")))
    elif mode == "read":
        monkeypatch.setattr(boundary, "_read", MagicMock(side_effect=OSError("secret read path")))
    elif mode == "close":

        def close(descriptor: int) -> None:
            original_close(descriptor)
            raise OSError("secret cleanup path")

        monkeypatch.setattr(boundary, "_close", close)
    elif mode == "identity":
        peer = tmp_path / "peer.toml"
        peer.write_bytes(b"schema_version=1")
        monkeypatch.setattr(boundary, "_fstat", MagicMock(return_value=peer.stat()))
    elif mode == "growth":
        monkeypatch.setattr(boundary, "_read", MagicMock(return_value=b"x" * (64 * 1024 + 1)))
    else:
        checks = 0

        def checked(candidate: Path) -> os.stat_result:
            nonlocal checks
            checks += 1
            if checks == 3:
                candidate.write_bytes(b"schema_version=2")
                timestamp = candidate.stat().st_mtime_ns + 1_000_000_000
                os.utime(candidate, ns=(timestamp, timestamp))
            return original_check(candidate)

        monkeypatch.setattr(boundary, "_checked_file", checked)
    with pytest.raises(ConfigurationError) as raised:
        load_configuration(path)
    assert "secret" not in str(raised.value)
    path.unlink()  # Also proves Windows descriptor closure after failures.
