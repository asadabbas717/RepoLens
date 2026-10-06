"""Immutable applied assessment scope/gates, independent of TOML and product catalogs."""

import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal

from repolens.domain.models import Severity, require_enum
from repolens.domain.paths import require_relative_file_path

MAX_CONFIGURATION_ENTRIES = 128
MAX_EXCLUSION_BYTES = 256


class ConfigurationError(ValueError):
    """Controlled invalid configuration data; never include caller values."""


def parse_score_threshold(value: str) -> Decimal:
    if (
        not isinstance(value, str)
        or re.fullmatch(r"[0-9]+(?:\.[0-9]{1,2})?", value, re.ASCII) is None
    ):
        raise ConfigurationError(
            "Expected a plain decimal score with at most two fractional digits"
        )
    result = Decimal(value)
    if not result.is_finite() or not 0 <= result <= 100:
        raise ConfigurationError("Score threshold must be finite and between 0 and 100")
    return result


@dataclass(frozen=True, slots=True)
class ExclusionPolicy:
    entries: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entries, (tuple, list)):
            raise ConfigurationError("Exclusions require a path collection, not scalar text")
        entries = tuple(self.entries)
        if len(entries) > MAX_CONFIGURATION_ENTRIES:
            raise ConfigurationError("Too many exclusion entries")
        for entry in entries:
            if (
                not isinstance(entry, str)
                or not entry.strip()
                or any(c in entry for c in "*?[]!")
                or any(unicodedata.category(c).startswith("C") for c in entry)
            ):
                raise ConfigurationError("Exclusions must be literal relative paths")
            try:
                if len(entry.encode("utf-8")) > MAX_EXCLUSION_BYTES:
                    raise ValueError("Oversized entry")
                require_relative_file_path(entry[:-1] if entry.endswith("/") else entry)
            except (ValueError, UnicodeError):
                raise ConfigurationError(
                    "Exclusion path is invalid or exceeds its byte limit"
                ) from None
        if len(set(entries)) != len(entries):
            raise ConfigurationError("Exclusion entries must be unique")
        object.__setattr__(self, "entries", tuple(sorted(entries)))

    def excludes_file(self, relative: str) -> bool:
        return any(
            relative.startswith(entry) if entry.endswith("/") else relative == entry
            for entry in self.entries
        )

    def prunes_directory(self, relative: str) -> bool:
        return any(
            (relative + "/").startswith(entry) for entry in self.entries if entry.endswith("/")
        )


@dataclass(frozen=True, slots=True)
class GateSettings:
    fail_under: Decimal | None = None
    fail_on_severity: Severity | None = None

    def __post_init__(self) -> None:
        value = self.fail_under
        if value is not None:
            exponent = value.as_tuple().exponent if isinstance(value, Decimal) else None
            if (
                not isinstance(value, Decimal)
                or not value.is_finite()
                or not 0 <= value <= 100
                or not isinstance(exponent, int)
                or exponent < -2
            ):
                raise ConfigurationError("Score threshold requires a bounded exact Decimal")
            object.__setattr__(self, "fail_under", Decimal(format(value, ".2f")))
        if self.fail_on_severity is not None:
            try:
                require_enum(self.fail_on_severity, Severity, "severity gate")
            except ValueError:
                raise ConfigurationError("Severity gate requires a Severity member") from None


@dataclass(frozen=True, slots=True)
class AppliedConfiguration:
    """Visible settings only; schema None denotes explicit CLI-only gates."""

    schema_version: int | None = None
    exclusions: ExclusionPolicy = field(default_factory=ExclusionPolicy)
    disabled_rules: tuple[str, ...] = ()
    gates: GateSettings = field(default_factory=GateSettings)

    def __post_init__(self) -> None:
        if self.schema_version is not None and (
            type(self.schema_version) is not int or self.schema_version != 1
        ):
            raise ConfigurationError("Unsupported configuration schema version")
        if not isinstance(self.exclusions, ExclusionPolicy) or not isinstance(
            self.gates, GateSettings
        ):
            raise ConfigurationError("Applied configuration requires typed scope and gates")
        if not isinstance(self.disabled_rules, (tuple, list)):
            raise ConfigurationError("Disabled rules require an identifier collection")
        rules = tuple(self.disabled_rules)
        if len(rules) > MAX_CONFIGURATION_ENTRIES or any(
            not isinstance(rule, str)
            or re.fullmatch(r"(?:RH|PY|TEST|CI)[0-9]{3}|BANDIT-B[0-9]{3}", rule) is None
            for rule in rules
        ):
            raise ConfigurationError("Disabled rules require exact supported identifier forms")
        if len(set(rules)) != len(rules):
            raise ConfigurationError("Disabled rule IDs must be unique")
        if self.schema_version is None and (rules or self.exclusions.entries):
            raise ConfigurationError("File-based scope controls require a configuration schema")
        object.__setattr__(self, "disabled_rules", tuple(sorted(rules)))
