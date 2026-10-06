"""Verify the installed distribution contract rather than a source-path shortcut."""

from importlib.metadata import entry_points, metadata, version

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
