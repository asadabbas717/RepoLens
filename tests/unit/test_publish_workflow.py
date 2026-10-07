"""Publication-only provenance gates; no registry connection or upload."""

import ast
import re
import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
FUNCTIONS = runpy.run_path(str(ROOT / ".github/scripts/validate_pypi.py"))
request = cast(Callable[[str, str], str], FUNCTIONS["validate_request"])
source = cast(Callable[[Path, str, str], str], FUNCTIONS["validate_source"])
SHA = "a" * 40


@pytest.mark.parametrize(
    "tag", ["main", "v0.1", "v0.1.1;echo bad", "v01.1.1", "v0.1.1.dev0", " v0.1.1"]
)
def test_dispatch_rejects_noncanonical_tags(tag: str) -> None:
    with pytest.raises(ValueError, match="tag"):
        request(tag, SHA)


@pytest.mark.parametrize("sha", ["main", "a" * 39, "a" * 41, "A" * 40, "../escape"])
def test_dispatch_requires_exact_commit(sha: str) -> None:
    with pytest.raises(ValueError, match="SHA"):
        request("v0.1.1", sha)


@pytest.fixture
def release_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "src/repolens").mkdir(parents=True)
    (tmp_path / "src/repolens/__init__.py").write_text('__version__ = "0.1.1"\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="repolens-engineering"\nversion="0.1.1"', encoding="utf-8"
    )
    monkeypatch.setitem(source.__globals__, "_git_value", lambda root, ref: SHA)
    return tmp_path


def test_source_matches_tag_sha_name_and_literal_runtime(release_source: Path) -> None:
    assert source(release_source, "v0.1.1", SHA) == "0.1.1"


@pytest.mark.parametrize("wrong_ref", ["HEAD", "refs/tags/v0.1.1^{commit}"])
def test_wrong_checkout_or_tag_fails_before_source_inspection(
    wrong_ref: str, release_source: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        source.__globals__, "_git_value", lambda root, ref: "b" * 40 if ref == wrong_ref else SHA
    )
    with pytest.raises(ValueError, match="expected commit"):
        source(release_source, "v0.1.1", SHA)


@pytest.mark.parametrize("name,version", [("repolens", "0.1.1"), ("repolens-engineering", "0.1.0")])
def test_distribution_name_or_version_disagreement_fails(
    release_source: Path, name: str, version: str
) -> None:
    (release_source / "pyproject.toml").write_text(
        f'[project]\nname="{name}"\nversion="{version}"', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Distribution"):
        source(release_source, "v0.1.1", SHA)


@pytest.mark.parametrize(
    "declaration",
    [
        '__version__="0.1.0"',
        "__version__=calculate()",
        '__version__="0.1.1"\n__version__="0.1.2"',
        '__version__="0.1.1"\nif True:\n __version__="0.1.2"',
    ],
)
def test_runtime_version_disagreement_or_dynamic_value_fails(
    release_source: Path, declaration: str
) -> None:
    (release_source / "src/repolens/__init__.py").write_text(declaration, encoding="utf-8")
    with pytest.raises(ValueError, match="Runtime"):
        source(release_source, "v0.1.1", SHA)


def test_publication_workflow_is_manual_and_separates_credentials() -> None:
    document = yaml.load(
        (ROOT / ".github/workflows/publish-pypi.yml").read_text(), Loader=yaml.BaseLoader
    )
    assert set(document["on"]) == {"workflow_dispatch"}
    assert document["permissions"] == {}
    assert set(document["jobs"]) == {"build", "publish"}
    build, publish = document["jobs"]["build"], document["jobs"]["publish"]
    assert build["permissions"] == {"contents": "read", "actions": "read"}
    assert publish["permissions"] == {"contents": "read", "id-token": "write"}
    assert publish["needs"] == "build" and publish["environment"]["name"] == "pypi"
    assert all(
        re.fullmatch(r"[^@]+@[a-f0-9]{40}", step["uses"])
        for job in (build, publish)
        for step in job["steps"]
        if "uses" in step
    )
    action = publish["steps"][-1]
    assert action["with"] == {
        "packages-dir": "dist/",
        "verify-metadata": "true",
        "attestations": "true",
    }
    assert "username" not in action["with"] and "password" not in action["with"]
    inline = build["steps"][0]["run"].split("python - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
    tree = ast.parse(inline)
    assert not any(isinstance(node, ast.Assert) for node in ast.walk(tree))
