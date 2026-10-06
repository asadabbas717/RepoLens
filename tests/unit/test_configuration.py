"""Strict schema, immutable values and exact product-rule validation."""

from dataclasses import FrozenInstanceError
from decimal import Decimal, localcontext
from typing import cast
from unittest.mock import MagicMock

import pytest

from repolens.application.configuration import ScanConfiguration, parse_configuration
from repolens.domain.assessment_configuration import (
    AppliedConfiguration,
    ConfigurationError,
    ExclusionPolicy,
    GateSettings,
)
from repolens.domain.models import Severity


def test_minimal_and_full_config_are_typed_canonical_and_immutable() -> None:
    assert parse_configuration(b"schema_version = 1").applied == AppliedConfiguration(1)
    first = b"""schema_version = 1
[scan]
exclude = ["vendor/", "src/generated.py"]
[rules]
disable = ["PY002", "BANDIT-B602", "CI003"]
[gate]
fail_under = "85.5"
fail_on_severity = "high"
"""
    second = b"""schema_version = 1
[gate]
fail_on_severity = "high"
fail_under = "85.50"
[rules]
disable = ["CI003", "PY002", "BANDIT-B602"]
[scan]
exclude = ["src/generated.py", "vendor/"]
"""
    cfg = parse_configuration(first)
    assert cfg == parse_configuration(second)
    assert cfg.applied.exclusions.entries == ("src/generated.py", "vendor/")
    assert cfg.applied.disabled_rules == ("BANDIT-B602", "CI003", "PY002")
    assert cfg.applied.gates == GateSettings(Decimal("85.50"), Severity.HIGH)
    with pytest.raises(FrozenInstanceError):
        field_name = "schema_version"
        setattr(cfg.applied, field_name, 2)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"schema_version=2",
        b"schema_version=true",
        b'schema_version="1"',
        b"schema_version=1\nsecret_token='must-not-leak'",
        b"schema_version=1\n[gat]\nfail_under='85'",
        b"schema_version=1\n[rules]\ndiable=['PY001']",
        b"schema_version=1\n[scan]\ninclude=['.git/']",
        b"schema_version=1\n[gate]\nfail_under=85.0",
        b"schema_version=1\n[gate]\nfail_under=85",
        b"schema_version=1\n[gate]\nfail_on_severity=true",
        b"schema_version=1\n[gate]\nfail_on_severity='secret-invalid'",
        b"schema_version=1\n[gate]\nfail_under='85.001'",
        b"schema_version=1\n[gate]\nfail_under='NaN'",
        b"schema_version=1\n[gate]\nfail_under='Infinity'",
        b"schema_version=1\n[gate]\nfail_under='101'",
        b"schema_version=1\nscan=[]",
        b"schema_version=1\n[scan]\nexclude='vendor/'",
        b"schema_version=1\n[rules]\ndisable=[1]",
        b"schema_version=1\n[rules]\ndisable=['PY099']",
        b"schema_version=1\n[rules]\ndisable=['B602']",
        b"schema_version=1\n[rules]\ndisable=['BANDIT-B60*']",
        b"schema_version=1\n[rules]\ndisable=['PY002','PY002']",
        b"schema_version=1\n[scan]\nexclude=['vendor/','vendor/']",
        b"schema_version=1\n[scan]\nexclude=[",
        b"schema_version=1\n\xffsecret",
        b"schema_version=1\n[plugin]\nmodule='secret'",
        b"schema_version=1\n[scoring]\nweights=[]",
        b"schema_version=1\n[gate]\ncommand='secret'",
        b"schema_version=1\n[scan]\nexclude=[true]",
        b"schema_version=1\n" + b"#" * (64 * 1024),
    ],
    ids=lambda raw: f"config-{len(raw)}-bytes",
)
def test_invalid_config_is_rejected_without_content_in_exception(raw: bytes) -> None:
    with pytest.raises(ConfigurationError) as raised:
        parse_configuration(raw)
    assert "secret" not in str(raised.value) and "must-not-leak" not in str(raised.value)


@pytest.mark.parametrize(
    "entry",
    [
        "",
        " ",
        "/absolute",
        "../escape",
        "C:/absolute",
        "C:\\absolute",
        "a\\b",
        "a//b",
        "a/./b",
        ".",
        "./",
        "vendor//",
        "a\x00b",
        "a\nb",
        "a\u202eb",
        "*.py",
        "!vendor/",
        "[ab].py",
        "x" * 257,
    ],
)
def test_exclusions_reject_unsafe_or_ambiguous_spellings(entry: str) -> None:
    with pytest.raises(ConfigurationError):
        ExclusionPolicy((entry,))


def test_exact_file_subtree_and_near_match_semantics() -> None:
    exclusion = ExclusionPolicy(("generated/file.py", "vendor/", "src/nested/"))
    assert exclusion.excludes_file("generated/file.py")
    assert not exclusion.excludes_file("generated/file.py.old")
    assert not exclusion.prunes_directory("generated/file.py")
    assert exclusion.prunes_directory("vendor")
    assert exclusion.prunes_directory("vendor/deep")
    assert exclusion.excludes_file("vendor/deep/app.py")
    assert not exclusion.excludes_file("vendorish/app.py")
    assert not exclusion.prunes_directory("src")
    assert exclusion.prunes_directory("src/nested")
    assert not exclusion.prunes_directory("nested")


@pytest.mark.parametrize("value", [None, Decimal("0"), Decimal("100"), Decimal("85.50")])
def test_gate_values_canonicalize_without_decimal_context_dependence(value: Decimal | None) -> None:
    with localcontext() as context:
        context.prec = 1
        settings = GateSettings(value)
    assert settings.fail_under == value
    if value is not None:
        assert settings.fail_under is not None and settings.fail_under.as_tuple().exponent == -2


@pytest.mark.parametrize(
    "value",
    [
        Decimal("NaN"),
        Decimal("Infinity"),
        Decimal("-1"),
        Decimal("101"),
        Decimal("85.001"),
        85.0,
        True,
    ],
)
def test_direct_gate_construction_rejects_impossible_or_float_values(value: object) -> None:
    with pytest.raises(ConfigurationError):
        GateSettings(cast(Decimal, value))


def test_direct_configuration_constructors_validate_scope_and_known_rules() -> None:
    with pytest.raises(ConfigurationError):
        ExclusionPolicy(cast(tuple[str, ...], "abc"))
    with pytest.raises(ConfigurationError):
        AppliedConfiguration(1, disabled_rules=cast(tuple[str, ...], "PY002"))
    with pytest.raises(ConfigurationError):
        ScanConfiguration(AppliedConfiguration())
    with pytest.raises(ConfigurationError):
        GateSettings(fail_on_severity=cast(Severity, "high"))
    with pytest.raises(ConfigurationError):
        AppliedConfiguration(1, exclusions=cast(ExclusionPolicy, None))
    with pytest.raises(ConfigurationError):
        AppliedConfiguration(True)
    with pytest.raises(ConfigurationError):
        AppliedConfiguration(disabled_rules=("PY002",))
    with pytest.raises(ConfigurationError):
        ScanConfiguration(AppliedConfiguration(1, disabled_rules=("PY099",)))
    with pytest.raises(ConfigurationError):
        AppliedConfiguration(1, disabled_rules=("PY002", "PY002"))
    with pytest.raises(ConfigurationError):
        AppliedConfiguration(1, disabled_rules=("BANDIT-B6*",))
    with pytest.raises(ConfigurationError):
        ExclusionPolicy(tuple(f"f{i}" for i in range(129)))
    with pytest.raises(ConfigurationError):
        AppliedConfiguration(1, disabled_rules=tuple(f"BANDIT-B{i:03d}" for i in range(129)))


def test_parser_has_no_network_or_tool_calls_and_does_not_expand_strings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forbidden = MagicMock(side_effect=AssertionError("Configuration is data"))
    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("socket.create_connection", forbidden)
    monkeypatch.setattr("importlib.import_module", forbidden)
    cfg = parse_configuration(b'schema_version=1\n[scan]\nexclude=["${TOKEN}/"]')
    assert cfg.applied.exclusions.entries == ("${TOKEN}/",)
    forbidden.assert_not_called()
