"""No-overwrite publication and resource failures touch only controlled siblings."""

import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens.infrastructure import report_output as output
from repolens.infrastructure.report_output import OutputError, prepare_output, publish_report


def test_new_utf8_file_has_lf_and_no_leftover_temporary_sibling(tmp_path: Path) -> None:
    destination = prepare_output(tmp_path / "report.json")
    publish_report(destination, "Unicode \u03bb\nsecond line\n")
    assert destination.read_bytes() == "Unicode \u03bb\nsecond line\n".encode("utf-8")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["report.json"]


@pytest.mark.parametrize(
    "kind", ["file", "directory", "missing-parent", "file-parent", "empty-name"]
)
def test_invalid_destinations_do_not_create_or_overwrite(tmp_path: Path, kind: str) -> None:
    destination = tmp_path / "report"
    if kind == "file":
        destination.write_bytes(b"existing")
    elif kind == "directory":
        destination.mkdir()
    elif kind == "missing-parent":
        destination = tmp_path / "missing/report"
    elif kind == "file-parent":
        (tmp_path / "parent").write_bytes(b"existing")
        destination = tmp_path / "parent/report"
    else:
        destination = Path("")
    with pytest.raises(OutputError):
        prepare_output(destination)
    if kind == "file":
        assert destination.read_bytes() == b"existing"
    assert not tuple(tmp_path.glob(".repolens-report-*"))


def test_dangling_destination_is_checked_with_lstat_not_followed_existence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A link/reparse destination's lstat succeeds even when its referent is absent.
    destination = tmp_path / "dangling"
    peer = tmp_path / "metadata"
    peer.touch()
    metadata = peer.lstat()
    original = Path.lstat

    def lstat(path: Path) -> os.stat_result:
        return metadata if path == destination else original(path)

    monkeypatch.setattr(Path, "lstat", lstat)
    with pytest.raises(OutputError, match="already exists"):
        prepare_output(destination)


def test_destination_created_after_preflight_is_not_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = prepare_output(tmp_path / "report")
    original = os.link

    def race(source: Path, target: Path) -> None:
        target.write_bytes(b"concurrent user file")
        original(source, target)

    monkeypatch.setattr(output, "_link", race)
    with pytest.raises(OutputError):
        publish_report(destination, "new report\n")
    assert destination.read_bytes() == b"concurrent user file"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["report"]


def test_destination_appearing_before_allocation_creates_no_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = prepare_output(tmp_path / "report")
    destination.write_bytes(b"concurrent user file")
    allocation = MagicMock(side_effect=AssertionError("Do not allocate for existing output"))
    monkeypatch.setattr(output, "mkstemp", allocation)
    with pytest.raises(OutputError, match="already exists"):
        publish_report(destination, "new report\n")
    allocation.assert_not_called()
    assert destination.read_bytes() == b"concurrent user file"


@pytest.mark.parametrize(
    "failure", ["allocation", "open", "write", "flush", "fsync", "close", "link"]
)
def test_creation_write_close_and_publish_errors_are_sanitized_and_cleaned(
    tmp_path: Path, failure: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = prepare_output(tmp_path / "report")
    error = OSError("secret OS diagnostic/path")
    original_open = os.fdopen

    if failure == "allocation":
        monkeypatch.setattr(output, "mkstemp", MagicMock(side_effect=error))
    elif failure == "link":
        monkeypatch.setattr(output, "_link", MagicMock(side_effect=error))
    elif failure == "fsync":
        monkeypatch.setattr(output, "_fsync", MagicMock(side_effect=error))
    elif failure == "open":
        monkeypatch.setattr(output, "_fdopen", MagicMock(side_effect=error))
    else:

        def fdopen(descriptor: int, mode: str, *, encoding: str, newline: str) -> MagicMock:
            # Wrap a real descriptor; always close it before simulated close failure.
            stream = original_open(descriptor, mode, encoding=encoding, newline=newline)
            wrapper = MagicMock(wraps=stream)
            wrapper.__enter__.return_value = wrapper

            def close_stream(*args: object) -> None:
                stream.close()
                if failure == "close":
                    raise error

            wrapper.__exit__.side_effect = close_stream
            if failure in {"write", "flush"}:
                getattr(wrapper, failure).side_effect = error
            return wrapper

        monkeypatch.setattr(output, "_fdopen", fdopen)
    with pytest.raises(OutputError) as raised:
        publish_report(destination, "new report\n")
    assert "secret" not in str(raised.value)
    assert not destination.exists()
    assert not tuple(tmp_path.glob(".repolens-report-*"))


def test_cleanup_failure_is_sanitized_after_complete_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = prepare_output(tmp_path / "report")
    original = Path.unlink

    def unlink(path: Path, missing_ok: bool = False) -> None:
        original(path, missing_ok=missing_ok)
        raise OSError("secret cleanup path")

    with monkeypatch.context() as scope:
        scope.setattr(Path, "unlink", unlink)
        with pytest.raises(OutputError, match="cleanup failed") as raised:
            publish_report(destination, "complete report\n")
    assert "secret" not in str(raised.value)
    assert destination.read_bytes() == b"complete report\n"
    assert not tuple(tmp_path.glob(".repolens-report-*"))


def test_descriptor_cleanup_failure_still_attempts_temporary_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = prepare_output(tmp_path / "report")
    original_close = os.close

    def close(descriptor: int) -> None:
        original_close(descriptor)
        raise OSError("secret descriptor cleanup")

    with monkeypatch.context() as scope:
        scope.setattr(output, "_fdopen", MagicMock(side_effect=OSError("secret open")))
        scope.setattr(output, "_close", close)
        with pytest.raises(OutputError):
            publish_report(destination, "report\n")
    assert not tuple(tmp_path.glob(".repolens-report-*"))


def test_preflight_os_errors_do_not_leak_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Path, "resolve", MagicMock(side_effect=OSError("secret absolute path")))
    with pytest.raises(OutputError) as raised:
        prepare_output(tmp_path / "report")
    assert "secret" not in str(raised.value)
