"""Whitelisted manifest values and deliberately narrow static declarations."""

from collections.abc import Callable
from dataclasses import replace
from typing import cast

import pytest

from repolens.analyzers.dependency_audit import DependencyAuditAnalyzer
from repolens.domain.dependency_declarations import (
    DeclaredDependency,
    InvalidManifest,
    UnsupportedDeclarations,
    parse_declarations,
)
from repolens.domain.dependency_manifest import (
    MAX_MANIFEST_BYTES,
    DependencyManifest,
    DependencyManifestSnapshot,
)
from repolens.domain.models import AnalysisContext, AnalyzerState, FileInventory, Repository


def snapshot(text: str, path: str = "requirements.txt") -> DependencyManifestSnapshot:
    return DependencyManifestSnapshot((DependencyManifest(path, text),))


@pytest.mark.parametrize(
    "text,expected",
    [
        ("requests==2.32.0", (DeclaredDependency("requests", "2.32.0"),)),
        ("# comment\n A_B.C == 1.2rc1 # safe comment\n", (DeclaredDependency("a-b-c", "1.2rc1"),)),
        ("a==1.2.post1\na==1.2.post1\n", (DeclaredDependency("a", "1.2.post1"),)),
        (
            "b==1.0.dev2\na==2.0+local.1",
            (DeclaredDependency("a", "2.0+local.1"), DeclaredDependency("b", "1.0.dev2")),
        ),
        ("", ()),
    ],
)
def test_supported_exact_pins(text: str, expected: tuple[DeclaredDependency, ...]) -> None:
    assert parse_declarations(snapshot(text)) == expected


@pytest.mark.parametrize(
    "text",
    [
        "a>=1",
        "a",
        "a==1.*",
        "a==1; python_version>'3'",
        "a[extra]==1",
        "-r secret.txt",
        "-c secret.txt",
        "-e .",
        ".",
        "./pkg",
        "file:/secret",
        "git+https://host/repo",
        "a @ https://host/pkg",
        "--index-url https://user:secret@host",
        "${SECRET}==1",
        "a==1 --hash=sha256:secret",
        "a==1\\",
        "garbage !!!",
        "a==1\na==2",
        "a===1",
        "a==1!2",
    ],
)
def test_unaccepted_syntax_never_forwarded(text: str) -> None:
    with pytest.raises(UnsupportedDeclarations) as error:
        parse_declarations(snapshot(text))
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "text,exception",
    [
        ('[project]\ndependencies=["a==1", "b==2"]', None),
        ("[project]\ndependencies=[]", None),
        ('[other]\nx="secret"', None),
        ('[project]\ndynamic=["dependencies"]', UnsupportedDeclarations),
        ('[project]\ndependencies=["a>=1"]', UnsupportedDeclarations),
        ('[project]\ndependencies=["a==1; os_name==\\"nt\\""]', UnsupportedDeclarations),
        ('[project]\ndependencies="secret"', InvalidManifest),
        ("[project]\ndependencies=[2]", InvalidManifest),
        ("[project]\ndynamic=2", InvalidManifest),
        ('project="secret"', InvalidManifest),
        ("[project]\ndynamic=[2]", InvalidManifest),
        ("[project secret", InvalidManifest),
    ],
)
def test_static_pep621_shapes(text: str, exception: type[Exception] | None) -> None:
    if exception:
        with pytest.raises(exception):
            parse_declarations(snapshot(text, "pyproject.toml"))
    else:
        assert isinstance(parse_declarations(snapshot(text, "pyproject.toml")), tuple)


def test_combined_declarations_merge_canonically() -> None:
    entries = (
        DependencyManifest("requirements.txt", "A_B==1"),
        DependencyManifest("pyproject.toml", '[project]\ndependencies=["a-b==1", "z==2"]'),
    )
    assert parse_declarations(DependencyManifestSnapshot(entries)) == parse_declarations(
        DependencyManifestSnapshot(reversed(entries))
    )
    assert len(parse_declarations(DependencyManifestSnapshot(entries))) == 2


def test_count_bound() -> None:
    with pytest.raises(UnsupportedDeclarations, match="count"):
        parse_declarations(snapshot("a==1\n" * 1001))


@pytest.mark.parametrize(
    "path",
    [
        "sub/requirements.txt",
        "requirements.txt.example",
        "/requirements.txt",
        "setup.py",
        "Requirements.txt",
    ],
)
def test_root_whitelist(path: str) -> None:
    with pytest.raises(ValueError):
        DependencyManifest(path, "secret")


@pytest.mark.parametrize(
    "text",
    ["x" * (MAX_MANIFEST_BYTES + 1), "é" * (MAX_MANIFEST_BYTES // 2 + 1), "\udcff"],
    ids=["characters", "utf8-bytes", "invalid-unicode"],
)
def test_manifest_value_bounds(text: str) -> None:
    with pytest.raises(ValueError):
        DependencyManifest("requirements.txt", text)


def test_snapshot_unique_and_text_hidden() -> None:
    entry = DependencyManifest("requirements.txt", "secret-token")
    assert "secret-token" not in repr(DependencyManifestSnapshot((entry,)))
    with pytest.raises(ValueError):
        DependencyManifestSnapshot((entry, entry))
    with pytest.raises(ValueError):
        DependencyManifestSnapshot(cast(tuple[DependencyManifest, ...], (object(),)))


def test_context_requires_exact_available_inventory() -> None:
    data = snapshot("a==1")
    for inventory in (None, FileInventory(())):
        with pytest.raises(ValueError):
            AnalysisContext(Repository("x"), inventory, dependency_manifests=data)
    valid = AnalysisContext(
        Repository("x"), FileInventory(("requirements.txt",)), dependency_manifests=data
    )
    assert "a==1" not in repr(valid)
    with pytest.raises(ValueError):
        cast(Callable[..., object], replace)(valid, dependency_manifests=object())


@pytest.mark.parametrize(
    "name,version", [("A", "1"), ("a_b", "1"), ("a", "1.*"), ("a", "secret"), ("../a", "1")]
)
def test_declaration_constructor(name: str, version: str) -> None:
    with pytest.raises(ValueError):
        DeclaredDependency(name, version)


@pytest.mark.parametrize(
    "text,state",
    [
        ("a==1", AnalyzerState.UNSUPPORTED),
        ("a>=1", AnalyzerState.UNSUPPORTED),
        ("", AnalyzerState.UNSUPPORTED),
    ],
)
def test_audit_deferral_is_never_clean(text: str, state: AnalyzerState) -> None:
    ctx = AnalysisContext(
        Repository("x"), FileInventory(("requirements.txt",)), dependency_manifests=snapshot(text)
    )
    result = DependencyAuditAnalyzer().analyze(ctx)
    assert result.state == state and result.findings == ()


def test_unavailable_empty_and_malformed_inputs() -> None:
    analyzer = DependencyAuditAnalyzer()
    assert analyzer.analyze(AnalysisContext(Repository("x"))).state == AnalyzerState.FAILED
    empty = AnalysisContext(
        Repository("x"), FileInventory(()), dependency_manifests=DependencyManifestSnapshot(())
    )
    assert analyzer.analyze(empty).state == AnalyzerState.UNSUPPORTED
    malformed = AnalysisContext(
        Repository("x"),
        FileInventory(("pyproject.toml",)),
        dependency_manifests=snapshot("secret [", "pyproject.toml"),
    )
    result = analyzer.analyze(malformed)
    assert result.state == AnalyzerState.FAILED and "secret" not in repr(result)
