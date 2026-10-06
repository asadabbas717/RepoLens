"""Verify the installed distribution contract rather than a source-path shortcut."""

from importlib.metadata import distribution, entry_points, metadata, version
from importlib.resources import files

import repolens


def test_installed_distribution_version_matches_public_version() -> None:
    assert version("repolens") == repolens.__version__


def test_distribution_declares_python_baseline_and_only_reviewed_runtime_dependency() -> None:
    package_metadata = metadata("repolens")
    assert package_metadata["Requires-Python"] == ">=3.13"
    assert package_metadata.get_all("Requires-Dist") == ["PyYAML<7,>=6.0.3"]


def test_installed_console_entry_point_is_declared() -> None:
    matches = tuple(
        entry for entry in entry_points(group="console_scripts") if entry.name == "repolens"
    )
    assert len(matches) == 1
    assert matches[0].value == "repolens.cli:main"


def test_installed_package_contains_public_typing_marker() -> None:
    assert files("repolens").joinpath("py.typed").is_file()


def test_installed_distribution_has_apache_expression_and_canonical_license() -> None:
    from pathlib import Path

    package = distribution("repolens")
    assert package.metadata["License-Expression"] == "Apache-2.0"
    assert package.metadata.get_all("License-File") == ["LICENSE"]
    assert set(package.metadata.get_all("Project-URL") or ()) == {
        "Repository, https://github.com/asadabbas717/RepoLens",
        "Issues, https://github.com/asadabbas717/RepoLens/issues",
    }
    entries = tuple(
        item for item in package.files or () if item.as_posix().endswith("/licenses/LICENSE")
    )
    assert len(entries) == 1
    assert (
        package.locate_file(entries[0]).read_bytes()
        == (Path(__file__).resolve().parents[2] / "LICENSE").read_bytes()
    )
