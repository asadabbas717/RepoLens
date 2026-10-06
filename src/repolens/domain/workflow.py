"""Bounded detached GitHub Actions text, never a workflow execution capability."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from repolens.domain.paths import require_relative_file_path

MAX_WORKFLOW_FILES = 32
MAX_WORKFLOW_BYTES = 64 * 1024
MAX_WORKFLOW_TOTAL_BYTES = 512 * 1024


def is_workflow_path(path: str) -> bool:
    parts = path.split("/")
    return (
        len(parts) == 3
        and parts[:2] == [".github", "workflows"]
        and (
            (parts[2].endswith(".yml") and len(parts[2]) > 4)
            or (parts[2].endswith(".yaml") and len(parts[2]) > 5)
        )
    )


@dataclass(frozen=True, slots=True)
class WorkflowFile:
    path: str
    text: str = field(repr=False)

    def __post_init__(self) -> None:
        require_relative_file_path(self.path)
        if not is_workflow_path(self.path):
            raise ValueError("Workflow requires an exact direct GitHub Actions path")
        if not isinstance(self.text, str) or len(self.text) > MAX_WORKFLOW_BYTES:
            raise ValueError("Workflow text must be bounded")
        try:
            self.path.encode("utf-8")
            size = len(self.text.encode("utf-8"))
        except UnicodeError:
            raise ValueError("Workflow data must be valid Unicode") from None
        if size > MAX_WORKFLOW_BYTES:
            raise ValueError("Workflow byte limit exceeded")


@dataclass(frozen=True, slots=True, init=False)
class WorkflowSnapshot:
    files: tuple[WorkflowFile, ...]

    def __init__(self, files: Iterable[WorkflowFile]) -> None:
        entries: dict[str, WorkflowFile] = {}
        total = 0
        for entry in files:
            if len(entries) >= MAX_WORKFLOW_FILES:
                raise ValueError("Workflow file count exceeded")
            if not isinstance(entry, WorkflowFile) or entry.path in entries:
                raise ValueError("Workflow entries must be valid and unique")
            total += len(entry.text.encode("utf-8"))
            if total > MAX_WORKFLOW_TOTAL_BYTES:
                raise ValueError("Workflow aggregate byte limit exceeded")
            entries[entry.path] = entry
        object.__setattr__(self, "files", tuple(entries[path] for path in sorted(entries)))
