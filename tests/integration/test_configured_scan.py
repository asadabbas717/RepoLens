"""Inert acquisition scope, rule controls, CLI precedence and report transparency."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from repolens import cli
from repolens.domain.assessment_configuration import (
    ExclusionPolicy,
    GateSettings,
)
from repolens.domain.models import Severity
from repolens.domain.security import BanditObservation
from repolens.infrastructure import python_source, workflow
from repolens.infrastructure.analysis_context import snapshot_analysis_context
from repolens.infrastructure.errors import AcquisitionError
from repolens.infrastructure.git import GitRunner
from repolens.infrastructure.repository_source import RepositorySource
from repolens.infrastructure.traversal import TraversalLimits, repository_files


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    assert GitRunner().run(("init", "--quiet"), root, 10).returncode == 0
    (root / "app.py").write_text(
        "from module import *\nfrom pathlib import Path\n"
        "Path(__file__).with_name('executed-marker').touch()",
        encoding="utf-8",
    )
    (root / "vendor").mkdir()
    (root / "vendor/bad.py").write_bytes(b"\xff-secret")
    (root / ".github/workflows").mkdir(parents=True)
    (root / ".github/workflows/bad.yml").write_bytes(b"\xff-secret")
    (root / "repolens.toml").write_bytes(b"secret malformed [")
    return root


def test_one_configured_inventory_prunes_before_reads_and_preserves_near_matches(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / "vendorish").mkdir()
    (repository / "vendorish/keep.py").write_bytes(b"pass")
    (repository / "vendor/deep").mkdir()
    (repository / "vendor/deep/large.py").write_bytes(b"x" * (256 * 1024 + 1))
    original_python = python_source._read_source
    observed: list[str] = []

    def source_read(lease: object, name: str, limit: int) -> bytes:
        assert not name.startswith("vendor/")
        observed.append(name)
        from repolens.infrastructure.repository_source import RepositoryLease

        assert isinstance(lease, RepositoryLease)
        return original_python(lease, name, limit)

    forbidden = MagicMock(side_effect=AssertionError("Excluded workflow must not be read"))
    monkeypatch.setattr(python_source, "_read_source", source_read)
    monkeypatch.setattr(workflow, "_read_verified", forbidden)
    exclusions = ExclusionPolicy(("vendor/", ".github/workflows/bad.yml"))
    with RepositorySource().local(repository) as lease:
        data = snapshot_analysis_context(lease, exclusions=exclusions)
    assert data.inventory is not None
    assert "vendorish/keep.py" in data.inventory.paths
    assert not any(
        p.startswith("vendor/") or p == ".github/workflows/bad.yml" for p in data.inventory.paths
    )
    assert data.python_sources is not None and tuple(f.path for f in data.python_sources.files) == (
        "app.py",
        "vendorish/keep.py",
    )
    assert data.workflows is not None and data.workflows.files == ()
    assert observed == ["app.py", "vendorish/keep.py"]
    forbidden.assert_not_called()


def test_exclusions_cannot_broaden_builtins_or_bypass_traversal_limits(repository: Path) -> None:
    (repository / "node_modules").mkdir()
    (repository / "node_modules/hidden.py").write_bytes(b"\xff")
    with RepositorySource().local(repository) as lease:
        paths = tuple(repository_files(lease, exclusions=ExclusionPolicy(("vendor/",))))
        assert not any(".git" in p.parts or "node_modules" in p.parts for p in paths)
        with pytest.raises(AcquisitionError, match="entry limit"):
            tuple(
                repository_files(
                    lease, TraversalLimits(max_entries=1), exclusions=ExclusionPolicy(("vendor/",))
                )
            )
        with pytest.raises(AcquisitionError, match="depth limit"):
            tuple(
                repository_files(
                    lease, TraversalLimits(max_depth=1), exclusions=ExclusionPolicy(("vendor/",))
                )
            )


@pytest.mark.parametrize("format_name", ["console", "json", "html"])
def test_configured_cli_reports_scope_without_paths_and_keeps_gate_exit(
    format_name: str,
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = repository.parent / "user-config.toml"
    config.write_text(
        'schema_version=1\n[scan]\nexclude=["vendor/", ".github/workflows/"]\n'
        '[rules]\ndisable=["PY002"]\n[gate]\nfail_under="100"\nfail_on_severity="info"',
        encoding="utf-8",
    )
    scanner = MagicMock()
    scanner.scan.return_value = ()
    monkeypatch.setattr(cli, "BanditRunner", MagicMock(return_value=scanner))
    argv = ["scan", str(repository), "--config", str(config), "--format", format_name]
    destination = repository.parent / "report.html"
    if format_name == "html":
        argv += ["--output", str(destination)]
    assert cli.run(argv) == 1  # INFO gate trips; the score remains 100.
    output = capsys.readouterr()
    assert not output.err
    text = destination.read_text(encoding="utf-8") if format_name == "html" else output.out
    if format_name == "json":
        data = json.loads(text)
        assert data["schema_version"] == "1"
        assert data["assessment"]["overall_score"] == "100.00"
        assert data["configuration"] == {
            "schema_version": 1,
            "exclusions": [".github/workflows/", "vendor/"],
            "disabled_rules": ["PY002"],
            "gates": {"fail_under": "100.00", "fail_on_severity": "info"},
        }
        assert "PY002" not in {f["rule_id"] for f in data["findings"]}
    else:
        assert "PY002" in text and "vendor/" in text and "100.00" in text
    assert str(config) not in text and str(repository) not in text and "secret" not in text
    assert not (repository / "executed-marker").exists()


@pytest.mark.parametrize(
    "override,expected",
    [
        ([], 1),
        (["--fail-under", "0"], 0),
        (["--fail-under", "98.75"], 0),
        (["--fail-under", "100"], 1),
    ],
)
def test_cli_score_gate_overrides_only_corresponding_config_value(
    repository: Path,
    override: list[str],
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = repository.parent / "config.toml"
    config.write_text(
        'schema_version=1\n[scan]\nexclude=["vendor/", ".github/workflows/"]\n'
        '[gate]\nfail_under="100"',
        encoding="utf-8",
    )
    scanner = MagicMock()
    scanner.scan.return_value = ()
    monkeypatch.setattr(cli, "BanditRunner", MagicMock(return_value=scanner))
    assert (
        cli.run(["scan", str(repository), "--config", str(config), "--format", "json", *override])
        == expected
    )
    data = json.loads(capsys.readouterr().out)
    assert data["assessment"]["overall_score"] == "98.75"
    assert data["configuration"]["gates"]["fail_under"] == (
        "100.00"
        if not override
        else format(GateSettings(cli._threshold(override[1])).fail_under, ".2f")
    )


def test_no_implicit_target_config_and_excluding_all_python_is_explicit_non_applicability(
    repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Hostile target TOML is inventory metadata only. No discovery occurs.
    (repository / "vendor/bad.py").unlink()
    (repository / ".github/workflows/bad.yml").unlink()
    scanner = MagicMock()
    scanner.scan.return_value = ()
    monkeypatch.setattr(cli, "BanditRunner", MagicMock(return_value=scanner))
    monkeypatch.setattr(
        cli, "load_configuration", MagicMock(side_effect=AssertionError("No implicit load"))
    )
    assert cli.run(["scan", str(repository), "--format", "json"]) == 0
    unconfigured = json.loads(capsys.readouterr().out)
    assert "configuration" not in unconfigured
    assert unconfigured["assessment"]["overall_score"] == "98.75"
    with RepositorySource().local(repository) as lease:
        context = snapshot_analysis_context(
            lease, exclusions=ExclusionPolicy(("app.py", "vendor/", ".github/workflows/"))
        )
    assert context.python_sources is not None and context.python_sources.files == ()


@pytest.mark.parametrize(
    "raw", [b"schema_version=2", b"secret = [", b'schema_version=1\n[rules]\ndisable=["PY099"]']
)
def test_invalid_config_prevents_all_target_acquisition(
    repository: Path,
    raw: bytes,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = repository.parent / "secret-config.toml"
    config.write_bytes(raw)
    acquisition = MagicMock(side_effect=AssertionError("Must validate config first"))
    monkeypatch.setattr(cli, "_scan", acquisition)
    assert cli.run(["scan", "https://github.com/owner/project", "--config", str(config)]) == 2
    output = capsys.readouterr()
    assert not output.out and output.err == "repolens: configuration could not be loaded safely.\n"
    acquisition.assert_not_called()


@pytest.mark.parametrize("override,expected", [([], 1), (["--fail-on-severity", "critical"], 0)])
def test_severity_override_and_vendor_suppression_are_honest(
    repository: Path,
    override: list[str],
    expected: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config = repository.parent / "config.toml"
    config.write_text(
        'schema_version=1\n[scan]\nexclude=["vendor/", ".github/workflows/"]\n'
        '[gate]\nfail_under="0"\nfail_on_severity="high"',
        encoding="utf-8",
    )
    scanner = MagicMock()
    scanner.scan.return_value = (BanditObservation("B602", Severity.HIGH, "app.py", 1, 0),)
    monkeypatch.setattr(cli, "BanditRunner", MagicMock(return_value=scanner))
    assert (
        cli.run(["scan", str(repository), "--config", str(config), "--format", "json", *override])
        == expected
    )
    data = json.loads(capsys.readouterr().out)
    assert data["assessment"]["overall_score"] == "87.50"
    assert data["configuration"]["gates"]["fail_on_severity"] == (
        "critical" if override else "high"
    )
    with config.open("a", encoding="utf-8") as stream:
        stream.write('\n[rules]\ndisable=["BANDIT-B602"]\n')
    assert cli.run(["scan", str(repository), "--config", str(config), "--format", "json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["assessment"]["overall_score"] == "98.75"
    assert "BANDIT-B602" not in {f["rule_id"] for f in data["findings"]}


def test_disabled_rule_cannot_bypass_missing_bandit(
    repository: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from importlib.metadata import PackageNotFoundError

    from repolens.infrastructure import bandit

    config = repository.parent / "config.toml"
    config.write_text(
        'schema_version=1\n[scan]\nexclude=["vendor/", ".github/workflows/"]\n'
        '[rules]\ndisable=["BANDIT-B602"]',
        encoding="utf-8",
    )
    monkeypatch.setattr(bandit, "version", MagicMock(side_effect=PackageNotFoundError("bandit")))
    assert cli.run(["scan", str(repository), "--config", str(config), "--format", "json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert data["assessment"]["overall_score"] is None
    assert (
        next(a for a in data["analyzers"] if a["identifier"] == "python-security")["state"]
        == "unsupported"
    )
