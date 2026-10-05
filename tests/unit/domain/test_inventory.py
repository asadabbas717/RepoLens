"""Inventory is bounded immutable data, not a filesystem capability."""

from collections.abc import Iterator
from dataclasses import FrozenInstanceError
from typing import cast

import pytest

from repolens.domain.models import MAX_INVENTORY_FILES, AnalysisContext, FileInventory, Repository


@pytest.mark.parametrize("paths", [(), ("one",), ("z", "a/file", "A")])
def test_inventory_canonically_orders_relative_paths(paths: tuple[str, ...]) -> None:
    assert FileInventory(paths).paths == tuple(sorted(paths))
    assert FileInventory(reversed(paths)) == FileInventory(paths)


@pytest.mark.parametrize(
    "path",
    [
        "",
        ".",
        "..",
        "../x",
        "a/../x",
        "/root/x",
        "C:/x",
        "C:x",
        "//host/share/x",
        "a\\x",
        "a//x",
        "./x",
        "a/./x",
        "a/",
        "x\x00",
        None,
        1,
    ],
)
def test_malformed_inventory_paths_are_rejected(path: object) -> None:
    with pytest.raises(ValueError, match="relative POSIX"):
        FileInventory((cast(str, path),))


def test_duplicate_paths_are_rejected_without_case_folding() -> None:
    with pytest.raises(ValueError, match="unique"):
        FileInventory(("same", "same"))
    assert FileInventory(("same", "SAME")).paths == ("SAME", "same")


def test_inventory_preserves_unicode_and_caller_mutations_do_not_change_it() -> None:
    supplied = ["caf\u00e9/file", ".gitignore"]
    inventory = FileInventory(supplied)
    supplied.clear()
    assert inventory.paths == (".gitignore", "caf\u00e9/file")
    with pytest.raises(FrozenInstanceError):
        inventory.__setattr__("paths", ())


def test_inventory_bound_stops_consumption_without_materializing_unbounded_input() -> None:
    consumed = 0

    def many_paths() -> Iterator[str]:
        nonlocal consumed
        for index in range(MAX_INVENTORY_FILES + 100):
            consumed += 1
            yield f"file-{index}"

    assert (
        len(FileInventory(str(index) for index in range(MAX_INVENTORY_FILES)).paths)
        == MAX_INVENTORY_FILES
    )
    with pytest.raises(ValueError, match="path limit"):
        FileInventory(many_paths())
    assert consumed == MAX_INVENTORY_FILES + 1


def test_empty_inventory_is_distinct_from_unavailable_context() -> None:
    identity = Repository("fixture")
    assert AnalysisContext(identity).inventory is None
    assert AnalysisContext(identity, FileInventory(())).inventory == FileInventory(())
    with pytest.raises(ValueError, match="FileInventory"):
        AnalysisContext(identity, cast(FileInventory, ()))
