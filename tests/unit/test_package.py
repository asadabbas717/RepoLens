"""Verify the installed distribution contract rather than a source-path shortcut."""

from importlib.metadata import metadata, version

import repolens


def test_installed_distribution_version_matches_public_version() -> None:
    assert version("repolens") == repolens.__version__


def test_distribution_declares_python_baseline_and_no_runtime_dependencies() -> None:
    package_metadata = metadata("repolens")
    assert package_metadata["Requires-Python"] == ">=3.13"
    assert package_metadata.get_all("Requires-Dist") is None
