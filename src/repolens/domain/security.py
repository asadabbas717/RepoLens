"""Small safe vendor-observation contract, without raw tool diagnostics."""

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from repolens.domain.models import Severity, require_enum
from repolens.domain.paths import require_relative_file_path
from repolens.domain.python_source import PythonSourceSnapshot


class SecurityToolUnavailable(Exception):
    """The supported trusted scanner is unavailable."""


class SecurityFailure(StrEnum):
    EXECUTION = "execution"
    TIMED_OUT = "timed_out"
    OUTPUT_LIMIT = "output_limit"
    INVALID_OUTPUT = "invalid_output"
    DIAGNOSTICS = "diagnostics"


class SecurityToolFailed(Exception):
    """Scanner operation, capture, validation or resource handling failed."""

    def __init__(self, message: str, kind: SecurityFailure = SecurityFailure.EXECUTION) -> None:
        require_enum(kind, SecurityFailure, "security failure kind")
        self.kind = kind
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class BanditObservation:
    rule: str
    severity: Severity
    path: str
    line: int
    column: int

    def __post_init__(self) -> None:
        if not isinstance(self.rule, str) or re.fullmatch(r"B[0-9]{3}", self.rule) is None:
            raise ValueError("Invalid Bandit test identifier")
        require_enum(self.severity, Severity, "severity")
        if self.severity not in {Severity.LOW, Severity.MEDIUM, Severity.HIGH}:
            raise ValueError("Unsupported Bandit severity")
        require_relative_file_path(self.path)
        if type(self.line) is not int or self.line < 1:
            raise ValueError("Invalid observation line")
        if type(self.column) is not int or self.column < 0:
            raise ValueError("Invalid observation column")


class BanditScan(Protocol):
    def scan(self, snapshot: PythonSourceSnapshot) -> tuple[BanditObservation, ...]: ...
