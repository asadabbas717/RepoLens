"""Real optional Bandit, owned Git fixtures and network-independent product checks."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dogfood_cases import CONFIGURATION, materialize

from repolens import cli
from repolens.domain.security import SecurityToolFailed


def scan_json(root: Path, capsys: pytest.CaptureFixture[str], *arguments: str) -> tuple[int, str]:
    status = cli.run(["scan", str(root), "--format", "json", *arguments])
    output = capsys.readouterr()
    assert output.err == ""
    return status, output.out


@pytest.mark.parametrize("case", ["clean-python", "poor-python", "non-python"])
def test_real_product_findings_deductions_and_determinism(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = materialize(tmp_path, case)
    first_status, first = scan_json(root, capsys)
    second_status, second = scan_json(root, capsys)
    assert first_status == second_status == 0
    assert first.encode("utf-8") == second.encode("utf-8")
    data = json.loads(first)
    assert data["policy"]["identifier"] == "repolens-python-static-v1"
    assert data["assessment"]["overall_score"] == ("92.50" if case == "poor-python" else "100.00")
    assert "configuration" not in data
    assert str(tmp_path) not in first
    rules = {finding["rule_id"] for finding in data["findings"]}
    assert rules == (
        {"PY001", "PY002", "CI002", "CI003", "RH001", "TEST001", "BANDIT-B105", "BANDIT-B110"}
        if case == "poor-python"
        else set()
    )
    active = {finding["identifier"] for finding in data["findings"]}
    for category in data["categories"]:
        for deduction in category["deductions"]:
            assert set(deduction["finding_ids"]) <= active
            assert deduction["points"] == (0 if deduction["severity"] == "info" else 5)
    for finding in data["findings"]:
        assert finding["recommendation"]
        for evidence in finding["evidence"]:
            name = evidence["file_path"]
            line = evidence["line_number"]
            if name is not None:
                assert (root / name).is_file()
                if line is not None:
                    assert 1 <= line <= len((root / name).read_text().splitlines())
    states = {item["identifier"]: item["state"] for item in data["analyzers"]}
    for identifier in ("python-static", "python-security", "testing-static"):
        assert states[identifier] == ("not_applicable" if case == "non-python" else "completed")
    assert not list(root.rglob("*-executed"))


@pytest.mark.parametrize("case", ["clean-python", "poor-python", "non-python"])
@pytest.mark.parametrize("format_name", ["console", "json", "html"])
def test_owned_scenarios_all_reports(
    case: str, format_name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = materialize(tmp_path, case)
    output = tmp_path / (format_name + ".txt")
    assert cli.run(["scan", str(root), "--format", format_name, "--output", str(output)]) == 0
    assert capsys.readouterr().out == ""
    raw = output.read_bytes()
    assert b"\r" not in raw and str(root).encode() not in raw
    assert case.encode() in raw and b"repolens-python-static-v1" in raw
    if format_name == "html":
        assert b"<!doctype html>" in raw.lower() and b"<script" not in raw.lower()
    if format_name == "json":
        assert json.loads(raw)["assessment"]["state"] == "available"
    assert not list(root.rglob("*-executed"))


def test_configured_scope_gates_and_repeat_bytes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = materialize(tmp_path, "poor-python")
    config = tmp_path / "trusted.toml"
    config.write_text(CONFIGURATION, encoding="utf-8")
    first_status, first = scan_json(root, capsys, "--config", str(config))
    assert first_status == 1  # 96.25 remains below 99; severity medium passes.
    assert scan_json(root, capsys, "--config", str(config)) == (first_status, first)
    data = json.loads(first)
    assert data["assessment"]["overall_score"] == "96.25"
    assert data["configuration"]["exclusions"] == ["checks.py", "setup.py"]
    assert data["configuration"]["disabled_rules"] == ["BANDIT-B105", "CI003", "PY002"]
    assert {item["rule_id"] for item in data["findings"]} == {
        "CI002",
        "PY001",
        "RH001",
        "TEST001",
        "BANDIT-B110",
    }
    assert scan_json(root, capsys, "--config", str(config), "--fail-under", "0")[0] == 0
    assert (
        scan_json(
            root, capsys, "--config", str(config), "--fail-under", "0", "--fail-on-severity", "low"
        )[0]
        == 1
    )
    for format_name in ("console", "html"):
        destination = tmp_path / (format_name + ".txt")
        assert (
            cli.run(
                [
                    "scan",
                    str(root),
                    "--config",
                    str(config),
                    "--format",
                    format_name,
                    "--output",
                    str(destination),
                ]
            )
            == 1
        )
        text = destination.read_text(encoding="utf-8")
        assert all(
            value in text for value in ("checks.py", "setup.py", "BANDIT-B105", "99.00", "medium")
        )
    assert not list(root.rglob("*-executed"))


@pytest.mark.parametrize(
    ("case", "arguments", "expected"),
    [
        ("clean-python", ("--fail-under", "100", "--fail-on-severity", "info"), 0),
        ("poor-python", ("--fail-under", "92.50"), 0),
        ("poor-python", ("--fail-under", "92.51"), 1),
        ("poor-python", ("--fail-on-severity", "low"), 1),
        ("poor-python", ("--fail-on-severity", "medium"), 0),
        ("non-python", ("--fail-under", "100"), 0),
    ],
)
def test_practical_gates(
    case: str,
    arguments: tuple[str, ...],
    expected: int,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert scan_json(materialize(tmp_path, case), capsys, *arguments)[0] == expected


def test_configuration_cannot_hide_failed_security(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = materialize(tmp_path, "poor-python")
    scanner = MagicMock()
    scanner.scan.side_effect = SecurityToolFailed("Must not escape")
    monkeypatch.setattr(cli, "BanditRunner", MagicMock(return_value=scanner))
    config = tmp_path / "trusted.toml"
    config.write_text(CONFIGURATION, encoding="utf-8")
    status, raw = scan_json(root, capsys, "--config", str(config), "--fail-under", "0")
    assert status == 1 and "Must not escape" not in raw
    data = json.loads(raw)
    assert data["assessment"]["overall_score"] is None
    assert (
        next(x for x in data["analyzers"] if x["identifier"] == "python-security")["state"]
        == "failed"
    )


def test_controlled_errors_and_injected_internal_defect(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = materialize(tmp_path, "clean-python")
    config = tmp_path / "bad.toml"
    config.write_text("secret invalid [", encoding="utf-8")
    assert cli.run(["scan", str(root), "--config", str(config)]) == 2
    assert "secret" not in capsys.readouterr().err
    assert cli.run(["scan", str(root), "--format", "html"]) == 2
    capsys.readouterr()
    monkeypatch.setattr(cli, "_scan", MagicMock(side_effect=RuntimeError("internal-secret")))
    assert cli.run(["scan", str(root)]) == 3
    assert "internal-secret" not in capsys.readouterr().err
