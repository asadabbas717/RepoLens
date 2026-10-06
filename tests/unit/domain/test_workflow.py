"""Exact workflow selection and bounded immutable detached data."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError, replace
from typing import cast

import pytest

from repolens.domain.models import AnalysisContext, FileInventory, Repository
from repolens.domain.workflow import (
    MAX_WORKFLOW_BYTES,
    MAX_WORKFLOW_FILES,
    MAX_WORKFLOW_TOTAL_BYTES,
    WorkflowFile,
    WorkflowSnapshot,
    is_workflow_path,
)


@pytest.mark.parametrize(
    "path,expected",
    [
        (".github/workflows/build.yml", True),
        (".github/workflows/build.yaml", True),
        (".github/workflows/.hidden.yml", True),
        (".github/workflows/café.yml", True),
        (".github/workflows/build.yml.example", False),
        (".github/workflows/nested/build.yml", False),
        (".github/WORKFLOWS/build.yml", False),
        (".github/workflow/build.yml", False),
        ("docs/.github/workflows/example.yml", False),
        (".github/workflows/build.YML", False),
        (".github/workflows/.yml", False),
        (".github/workflows/.yaml", False),
    ],
)
def test_exact_selection(path: str, expected: bool) -> None:
    assert is_workflow_path(path) is expected
    if not expected:
        with pytest.raises(ValueError):
            WorkflowFile(path, "secret")


@pytest.mark.parametrize(
    "path",
    [
        "../.github/workflows/a.yml",
        "/.github/workflows/a.yml",
        ".github/workflows/./a.yml",
        ".github/workflows/secret\x00.yml",
        ".github/workflows/\udcff.yml",
    ],
    ids=["parent", "absolute", "noncanonical", "nul", "invalid-unicode"],
)
def test_invalid_paths(path: str) -> None:
    with pytest.raises(ValueError):
        WorkflowFile(path, "secret")


@pytest.mark.parametrize(
    "text",
    ["x" * (MAX_WORKFLOW_BYTES + 1), "é" * (MAX_WORKFLOW_BYTES // 2 + 1), "\udcff"],
    ids=["characters", "utf8-bytes", "invalid-unicode"],
)
def test_text_limits(text: str) -> None:
    with pytest.raises(ValueError):
        WorkflowFile(".github/workflows/a.yml", text)


def test_exact_bound_hidden_text_and_immutable_order() -> None:
    first = WorkflowFile(".github/workflows/a.yml", "x" * MAX_WORKFLOW_BYTES)
    second = WorkflowFile(".github/workflows/b.yaml", "secret-token")
    snapshot = WorkflowSnapshot((second, first))
    assert snapshot.files == (first, second)
    assert "secret-token" not in repr(snapshot)
    field = "text"
    with pytest.raises(FrozenInstanceError):
        setattr(first, field, "changed")
    with pytest.raises(ValueError):
        WorkflowSnapshot((first, first))
    with pytest.raises(ValueError):
        WorkflowSnapshot(cast(tuple[WorkflowFile, ...], (object(),)))


def test_file_count_and_aggregate_limits() -> None:
    entries = tuple(
        WorkflowFile(f".github/workflows/{i}.yml", "") for i in range(MAX_WORKFLOW_FILES)
    )
    assert len(WorkflowSnapshot(entries).files) == MAX_WORKFLOW_FILES
    with pytest.raises(ValueError, match="count"):
        WorkflowSnapshot((*entries, WorkflowFile(".github/workflows/extra.yml", "")))
    full = tuple(
        WorkflowFile(f".github/workflows/{i}.yml", "x" * MAX_WORKFLOW_BYTES)
        for i in range(MAX_WORKFLOW_TOTAL_BYTES // MAX_WORKFLOW_BYTES)
    )
    assert sum(len(f.text) for f in WorkflowSnapshot(full).files) == MAX_WORKFLOW_TOTAL_BYTES
    with pytest.raises(ValueError, match="aggregate"):
        WorkflowSnapshot((*full, WorkflowFile(".github/workflows/extra.yml", "x")))


def test_context_exact_membership_unavailable_and_empty() -> None:
    data = WorkflowSnapshot((WorkflowFile(".github/workflows/a.yml", "secret"),))
    for inventory in (None, FileInventory(()), FileInventory((".github/workflows/b.yml",))):
        with pytest.raises(ValueError):
            AnalysisContext(Repository("fixture"), inventory, workflows=data)
    valid = AnalysisContext(
        Repository("fixture"), FileInventory((".github/workflows/a.yml",)), workflows=data
    )
    assert "secret" not in repr(valid)
    with pytest.raises(ValueError):
        cast(Callable[..., object], replace)(valid, workflows=object())
    assert AnalysisContext(Repository("fixture")).workflows is None
    assert (
        AnalysisContext(
            Repository("fixture"), FileInventory(()), workflows=WorkflowSnapshot(())
        ).workflows
        is not None
    )
