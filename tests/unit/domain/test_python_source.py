"""Detached source values are bounded, canonical and complete for selected paths."""

from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from repolens.domain.models import AnalysisContext, FileInventory, Repository
from repolens.domain.python_source import (
    MAX_SOURCE_FILE_BYTES,
    MAX_SOURCE_FILES,
    MAX_SOURCE_TOTAL_BYTES,
    PythonSourceFile,
    PythonSourceSnapshot,
    is_python_path,
)


@pytest.mark.parametrize(
    "path,selected",
    [
        ("a.py", True),
        ("a.pyi", True),
        (".py", True),
        ("a.PY", False),
        ("a.PYI", False),
        ("a.py.old", False),
        ("a.txt", False),
    ],
)
def test_selection_is_exact_and_case_sensitive(path: str, selected: bool) -> None:
    assert is_python_path(path) is selected


@pytest.mark.parametrize(
    "path", ["/absolute.py", "../escape.py", "C:/host.py", "a\\b.py", "a.txt", "\ud800.py"]
)
def test_source_paths_are_validated(path: str) -> None:
    with pytest.raises(ValueError):
        PythonSourceFile(path, "")


@pytest.mark.parametrize(
    "text",
    [None, "x" * (MAX_SOURCE_FILE_BYTES + 1), "\u00e9" * MAX_SOURCE_FILE_BYTES, "\ud800"],
    ids=["not-string", "characters-limit", "utf8-limit", "surrogate"],
)
def test_invalid_or_oversized_text_is_rejected_without_leaking_it(text: object) -> None:
    with pytest.raises(ValueError) as failure:
        PythonSourceFile("file.py", cast(str, text))
    assert "\ud800" not in str(failure.value)


def test_text_is_not_in_snapshot_repr_and_membership_is_immutable() -> None:
    supplied = [PythonSourceFile("z.py", "secret-value"), PythonSourceFile("a.py", "")]
    snapshot = PythonSourceSnapshot(supplied)
    supplied.clear()
    assert tuple(source.path for source in snapshot.files) == ("a.py", "z.py")
    assert "secret-value" not in repr(snapshot)
    with pytest.raises(FrozenInstanceError):
        snapshot.__setattr__("files", ())


@pytest.mark.parametrize("invalid", [None, PythonSourceFile("a.py", "")])
def test_invalid_or_duplicate_entries_are_rejected(invalid: object) -> None:
    with pytest.raises(ValueError, match="valid and unique"):
        PythonSourceSnapshot([PythonSourceFile("a.py", ""), cast(PythonSourceFile, invalid)])


def test_source_count_is_bounded_even_for_direct_construction() -> None:
    valid = [PythonSourceFile(f"{index}.py", "") for index in range(MAX_SOURCE_FILES)]
    assert len(PythonSourceSnapshot(valid).files) == MAX_SOURCE_FILES
    with pytest.raises(ValueError, match="file count"):
        PythonSourceSnapshot([*valid, PythonSourceFile("extra.py", "")])


def test_aggregate_limit_accepts_boundary_and_rejects_excess() -> None:
    files = [
        PythonSourceFile(f"{index}.py", "x" * MAX_SOURCE_FILE_BYTES)
        for index in range(MAX_SOURCE_TOTAL_BYTES // MAX_SOURCE_FILE_BYTES)
    ]
    assert len(PythonSourceSnapshot(files).files) == len(files)
    with pytest.raises(ValueError, match="aggregate"):
        PythonSourceSnapshot([*files, PythonSourceFile("extra.py", "x")])


@pytest.mark.parametrize("mismatch", ["missing", "extra", "unavailable", "type"])
def test_context_cannot_publish_incomplete_or_unavailable_source_as_complete(mismatch: str) -> None:
    inventory = FileInventory(("a.py",)) if mismatch != "unavailable" else None
    sources = (
        PythonSourceSnapshot(())
        if mismatch == "missing"
        else PythonSourceSnapshot((PythonSourceFile("b.py", ""),))
    )
    if mismatch == "type":
        sources = cast(PythonSourceSnapshot, ())
    with pytest.raises(ValueError):
        AnalysisContext(Repository("fixture"), inventory, sources)
