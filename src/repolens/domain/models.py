"""Immutable evidence, findings and analyzer lifecycle values."""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath, PureWindowsPath


class Severity(StrEnum):
    """Impact levels in ascending declaration order; INFO carries no penalty.

    Scoring uses enum iteration order, never lexical string comparisons.
    """

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Category(StrEnum):
    CODE_QUALITY = "code_quality"
    TESTING = "testing"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    REPOSITORY_HYGIENE = "repository_hygiene"
    CI_CD = "ci_cd"
    MAINTAINABILITY = "maintainability"


class AnalyzerState(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    UNSUPPORTED = "unsupported"
    NOT_APPLICABLE = "not_applicable"


def require_text(value: str, field: str) -> None:
    """Reject empty required text without silently changing producer data."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonblank string")


def require_enum(value: StrEnum, enum_type: type[StrEnum], field: str) -> None:
    """Annotations alone do not protect public constructors at runtime."""
    if not isinstance(value, enum_type):
        raise ValueError(f"{field} must be a {enum_type.__name__} member")


@dataclass(frozen=True, slots=True)
class Repository:
    """Display identity only; no acquisition, path validation or I/O."""

    name: str

    def __post_init__(self) -> None:
        require_text(self.name, "repository name")


MAX_INVENTORY_FILES = 20_000


def require_relative_file_path(value: str) -> None:
    """Validate a canonical relative POSIX location without performing I/O."""
    if not isinstance(value, str):
        raise ValueError("file_path must be a normalized relative POSIX file path")
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or "\x00" in value
        or PureWindowsPath(value).drive
        or path.is_absolute()
        or ".." in path.parts
        or path.as_posix() != value
        or value == "."
    ):
        raise ValueError("file_path must be a normalized relative POSIX file path")


@dataclass(frozen=True, slots=True, init=False)
class FileInventory:
    """Completed eligible-file inventory; empty differs from unavailable.

    Paths carry no access capability or claim of Git tracking. Infrastructure
    enforces filesystem exclusions; this value validates bounded lexical data.
    """

    paths: tuple[str, ...]

    def __init__(self, paths: Iterable[str]) -> None:
        unique_paths: set[str] = set()
        for value in paths:
            if len(unique_paths) >= MAX_INVENTORY_FILES:
                raise ValueError("File inventory exceeds its path limit")
            require_relative_file_path(value)
            if value in unique_paths:
                raise ValueError("File inventory paths must be unique")
            unique_paths.add(value)
        object.__setattr__(self, "paths", tuple(sorted(unique_paths)))


@dataclass(frozen=True, slots=True)
class AnalysisContext:
    """Immutable identity and optional bounded data; no filesystem capabilities."""

    repository: Repository
    inventory: FileInventory | None = None

    def __post_init__(self) -> None:
        if self.inventory is not None and not isinstance(self.inventory, FileInventory):
            raise ValueError("inventory must be a FileInventory or unavailable")


@dataclass(frozen=True, slots=True)
class Evidence:
    """A redacted observation, optionally located in a repository-relative file.

    Producers must omit secret values. Location validation is lexical only;
    containment and symlink checks belong to the future source layer.
    """

    description: str
    file_path: str | None = None
    line_number: int | None = None

    def __post_init__(self) -> None:
        require_text(self.description, "evidence description")
        if self.file_path is not None:
            require_relative_file_path(self.file_path)
        if self.line_number is not None:
            if self.file_path is None:
                raise ValueError("line_number requires file_path")
            if type(self.line_number) is not int or self.line_number < 1:
                raise ValueError("line_number must be a positive integer")


@dataclass(frozen=True, slots=True)
class Finding:
    """One identified occurrence; rule_id groups occurrences for scoring."""

    identifier: str
    rule_id: str
    category: Category
    severity: Severity
    title: str
    description: str
    evidence: tuple[Evidence, ...]
    recommendation: str
    source_analyzer: str

    def __post_init__(self) -> None:
        require_enum(self.category, Category, "category")
        require_enum(self.severity, Severity, "severity")
        for field, value in (
            ("identifier", self.identifier),
            ("rule_id", self.rule_id),
            ("title", self.title),
            ("description", self.description),
            ("recommendation", self.recommendation),
            ("source_analyzer", self.source_analyzer),
        ):
            require_text(value, field)
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if not self.evidence:
            raise ValueError("a finding requires evidence")


@dataclass(frozen=True, slots=True)
class AnalyzerSpec:
    """Stable metadata for one planned analyzer."""

    identifier: str
    category: Category
    description: str

    def __post_init__(self) -> None:
        require_enum(self.category, Category, "category")
        require_text(self.identifier, "analyzer identifier")
        require_text(self.description, "analyzer description")


@dataclass(frozen=True, slots=True)
class AnalyzerResult:
    """A complete outcome, never a silent partial success.

    Non-completed outcomes contain reasons and no findings. An analyzer that
    cannot finish must return FAILED rather than COMPLETED with partial data.
    """

    analyzer: AnalyzerSpec
    state: AnalyzerState
    findings: tuple[Finding, ...] = ()
    reason: str | None = None

    def __post_init__(self) -> None:
        require_enum(self.state, AnalyzerState, "state")
        object.__setattr__(self, "findings", tuple(self.findings))
        if self.state == AnalyzerState.COMPLETED:
            if self.reason is not None:
                raise ValueError("completed results must not have an outcome reason")
        else:
            if self.reason is None:
                raise ValueError("non-completed results require a reason")
            require_text(self.reason, "outcome reason")
            if self.findings:
                raise ValueError("non-completed results must not contain findings")
        identifiers: set[str] = set()
        for finding in self.findings:
            if finding.source_analyzer != self.analyzer.identifier:
                raise ValueError("finding source must match its analyzer")
            if finding.category != self.analyzer.category:
                raise ValueError("finding category must match its analyzer")
            if finding.identifier in identifiers:
                raise ValueError("finding identifiers must be unique")
            identifiers.add(finding.identifier)
