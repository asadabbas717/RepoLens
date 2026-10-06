"""Strict product configuration parsing and immutable result selection."""

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

from repolens.analyzers.ci_static import RULES as CI_RULES
from repolens.analyzers.hygiene import RULES as HYGIENE_RULES
from repolens.analyzers.python_static import RULES as PYTHON_RULES
from repolens.analyzers.testing_static import RULES as TESTING_RULES
from repolens.domain.assessment_configuration import (
    AppliedConfiguration,
    ConfigurationError,
    ExclusionPolicy,
    GateSettings,
    parse_score_threshold,
)
from repolens.domain.models import AnalyzerResult, Severity

MAX_CONFIG_BYTES = 64 * 1024
KNOWN_RULE_IDS = frozenset(
    rule.identifier for rule in (*CI_RULES, *HYGIENE_RULES, *PYTHON_RULES, *TESTING_RULES)
)


@dataclass(frozen=True, slots=True)
class ScanConfiguration:
    applied: AppliedConfiguration

    def __post_init__(self) -> None:
        if not isinstance(self.applied, AppliedConfiguration) or self.applied.schema_version != 1:
            raise ConfigurationError("A parsed file configuration requires schema 1")
        for rule in self.applied.disabled_rules:
            if rule not in KNOWN_RULE_IDS and re.fullmatch(r"BANDIT-B[0-9]{3}", rule) is None:
                raise ConfigurationError("Disabled static rule is not in the shipped catalogs")


def _section(data: Mapping[str, object], name: str, fields: set[str]) -> Mapping[str, object]:
    value = data.get(name, {})
    if not isinstance(value, dict) or not set(value).issubset(fields):
        raise ConfigurationError("Unknown or invalid configuration section fields")
    return cast(Mapping[str, object], value)


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
        raise ConfigurationError("Configuration selections require string arrays")
    return tuple(cast(list[str], value))


def parse_configuration(raw: bytes) -> ScanConfiguration:
    """Parse bounded UTF-8 once; no discovery, I/O, expansion or arbitrary imports."""
    if len(raw) > MAX_CONFIG_BYTES:
        raise ConfigurationError("Configuration byte limit exceeded")
    try:
        data: Mapping[str, object] = tomllib.loads(raw.decode("utf-8"))
        if not set(data).issubset({"schema_version", "scan", "rules", "gate"}):
            raise ConfigurationError("Unknown configuration top-level keys")
        version = data.get("schema_version")
        if type(version) is not int or version != 1:
            raise ConfigurationError("Configuration requires schema_version = 1")
        scan = _section(data, "scan", {"exclude"})
        rules = _section(data, "rules", {"disable"})
        gate = _section(data, "gate", {"fail_under", "fail_on_severity"})
        threshold = gate.get("fail_under")
        severity = gate.get("fail_on_severity")
        if threshold is not None and not isinstance(threshold, str):
            raise ConfigurationError("Configured score threshold must be a decimal string")
        if severity is not None and not isinstance(severity, str):
            raise ConfigurationError("Configured severity gate must be a severity string")
        return ScanConfiguration(
            AppliedConfiguration(
                1,
                ExclusionPolicy(_strings(scan.get("exclude", []))),
                _strings(rules.get("disable", [])),
                GateSettings(
                    parse_score_threshold(threshold) if threshold is not None else None,
                    Severity(severity) if severity is not None else None,
                ),
            )
        )
    except (UnicodeError, ValueError, RecursionError, MemoryError):
        raise ConfigurationError("Configuration data could not be validated") from None


def select_results(
    results: tuple[AnalyzerResult, ...], disabled_rules: tuple[str, ...]
) -> tuple[AnalyzerResult, ...]:
    """Remove exact disabled findings only; states/reasons/metadata stay intact."""
    disabled = frozenset(disabled_rules)
    return tuple(
        AnalyzerResult(
            result.analyzer,
            result.state,
            tuple(f for f in result.findings if f.rule_id not in disabled),
            result.reason,
        )
        for result in results
    )
