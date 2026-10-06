"""Bounded non-constructing YAML composition and a narrow Actions projection."""

import re
from dataclasses import dataclass
from typing import cast

import yaml
from yaml.error import Mark
from yaml.events import (
    AliasEvent,
    CollectionEndEvent,
    CollectionStartEvent,
    DocumentStartEvent,
    ScalarEvent,
)
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from repolens.domain.workflow import WorkflowFile, is_workflow_path

MAX_YAML_DEPTH = 32
MAX_YAML_NODES = 4096
MAX_COLLECTION_ITEMS = 256


class UnsupportedWorkflow(Exception):
    """The complete workflow set cannot be inspected within this static subset."""


@dataclass(frozen=True, slots=True)
class SourceLocation:
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class WorkflowObservations:
    unpinned: tuple[SourceLocation, ...]
    write_all: tuple[SourceLocation, ...]


def _preflight(text: str) -> None:
    depth = nodes = documents = 0
    events = yaml.parse(text, Loader=yaml.BaseLoader)
    try:
        for event in events:
            if isinstance(event, DocumentStartEvent):
                documents += 1
                if documents > 1 or event.version is not None or event.tags:
                    raise UnsupportedWorkflow(
                        "Multiple documents or YAML directives are unsupported"
                    )
            if isinstance(event, AliasEvent):
                raise UnsupportedWorkflow("YAML aliases are unsupported")
            if isinstance(event, (ScalarEvent, CollectionStartEvent)):
                nodes += 1
                if nodes > MAX_YAML_NODES or event.anchor is not None or event.tag is not None:
                    raise UnsupportedWorkflow(
                        "YAML node limits, anchors or explicit tags are unsupported"
                    )
            if isinstance(event, CollectionStartEvent):
                depth += 1
                if depth > MAX_YAML_DEPTH:
                    raise UnsupportedWorkflow("YAML nesting limit exceeded")
            elif isinstance(event, CollectionEndEvent):
                depth -= 1
    finally:
        events.close()


def _scalar(node: Node) -> str:
    if not isinstance(node, ScalarNode) or not isinstance(node.value, str):
        raise UnsupportedWorkflow("Expected literal scalar data")
    return node.value


def _sequence(node: Node) -> list[Node]:
    if not isinstance(node, SequenceNode):
        raise UnsupportedWorkflow("Expected sequence data")
    return cast(list[Node], node.value)


def _mapping(node: Node) -> dict[str, Node]:
    if not isinstance(node, MappingNode):
        raise UnsupportedWorkflow("Expected mapping data")
    pairs = cast(list[tuple[Node, Node]], node.value)
    result: dict[str, Node] = {}
    for key, value in pairs:
        name = _scalar(key)
        if name in result or name == "<<":
            raise UnsupportedWorkflow("Duplicate or merge mapping keys are unsupported")
        result[name] = value
    return result


def _validate_tree(node: Node) -> None:
    if isinstance(node, ScalarNode):
        _scalar(node)
        return
    children = list(_mapping(node).values()) if isinstance(node, MappingNode) else _sequence(node)
    if len(children) > MAX_COLLECTION_ITEMS:
        raise UnsupportedWorkflow("YAML collection item limit exceeded")
    for child in children:
        _validate_tree(child)


def _location(node: Node) -> SourceLocation:
    mark = node.start_mark
    if not isinstance(mark, Mark):
        raise UnsupportedWorkflow("YAML source location is unavailable")
    return SourceLocation(mark.line + 1, mark.column)


def _path_parts(path: str) -> bool:
    return bool(path) and all(
        re.fullmatch(r"[A-Za-z0-9_.-]+", part) is not None and part not in {".", ".."}
        for part in path.split("/")
    )


def _unpinned_reference(node: Node, *, reusable: bool) -> bool:
    value = _scalar(node)
    if "${{" in value:
        raise UnsupportedWorkflow("Dynamic action references are unresolved")
    if value.startswith(("./", "$/")):
        relative = value[2:]
        if not _path_parts(relative) or (reusable and not is_workflow_path(relative)):
            raise UnsupportedWorkflow("Local action or workflow reference is unsupported")
        return False
    if value.startswith("docker://"):
        image = value.removeprefix("docker://")
        if reusable or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@+-]*", image) is None:
            raise UnsupportedWorkflow("Docker reference is unsupported in this location")
        return False  # Image pinning is a different policy, outside CI002.
    if value.count("@") != 1:
        raise UnsupportedWorkflow("Remote reference syntax is unsupported")
    identity, reference = value.split("@")
    components = identity.split("/")
    if (
        len(components) < 2
        or not _path_parts(identity)
        or re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", components[0]) is None
        or "--" in components[0]
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", components[1]) is None
        or (reusable and not is_workflow_path("/".join(components[2:])))
        or re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._/+\-]*", reference) is None
        or any(
            not part or part.startswith(".") or part.endswith(".lock")
            for part in reference.split("/")
        )
        or ".." in reference
        or reference.endswith((".", ".lock"))
    ):
        raise UnsupportedWorkflow("Remote reference is outside the supported syntax subset")
    return re.fullmatch(r"[0-9a-fA-F]{40}", reference) is None


def _permissions(node: Node) -> bool:
    if isinstance(node, ScalarNode):
        value = _scalar(node)
        if value not in {"write-all", "read-all"}:
            raise UnsupportedWorkflow("Permissions value is unresolved or unsupported")
        return value == "write-all"
    for scope_name, scope_value in _mapping(node).items():
        if not scope_name or "${{" in scope_name:
            raise UnsupportedWorkflow("Permission scope name is unresolved")
        if _scalar(scope_value) not in {"read", "write", "none"}:
            raise UnsupportedWorkflow("Permission scope value is unresolved or unsupported")
    return False  # No scope/default/inheritance evaluator is implemented.


def inspect_workflow(source: WorkflowFile) -> WorkflowObservations:
    try:
        _preflight(source.text)
        tree = yaml.compose(source.text, Loader=yaml.BaseLoader)
        if tree is None:
            raise UnsupportedWorkflow("Empty workflow data")
        _validate_tree(tree)
        root = _mapping(tree)
        trigger = root.get("on")
        jobs = root.get("jobs")
        if trigger is None or jobs is None:
            raise UnsupportedWorkflow("Workflow trigger/jobs structure is unavailable")
        if isinstance(trigger, ScalarNode):
            if not _scalar(trigger) or "${{" in _scalar(trigger):
                raise UnsupportedWorkflow("Workflow trigger is unresolved")
        elif isinstance(trigger, SequenceNode):
            if not _sequence(trigger) or any(
                not _scalar(item) or "${{" in _scalar(item) for item in _sequence(trigger)
            ):
                raise UnsupportedWorkflow("Workflow trigger sequence is unsupported")
        else:
            trigger_map = _mapping(trigger)
            if not trigger_map or any(not name or "${{" in name for name in trigger_map):
                raise UnsupportedWorkflow("Workflow trigger mapping is empty or unresolved")
        unpinned: list[SourceLocation] = []
        broad: list[SourceLocation] = []
        if "permissions" in root and _permissions(root["permissions"]):
            broad.append(_location(root["permissions"]))
        job_map = _mapping(jobs)
        if not job_map:
            raise UnsupportedWorkflow("Workflow jobs are empty")
        for identifier, job_node in job_map.items():
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", identifier) is None:
                raise UnsupportedWorkflow("Job identifier is outside the supported subset")
            job = _mapping(job_node)
            if "permissions" in job and _permissions(job["permissions"]):
                broad.append(_location(job["permissions"]))
            if "uses" in job:
                if "steps" in job or "runs-on" in job:
                    raise UnsupportedWorkflow("Reusable job structure is ambiguous")
                if _unpinned_reference(job["uses"], reusable=True):
                    unpinned.append(_location(job["uses"]))
                continue
            if "runs-on" not in job or "steps" not in job:
                raise UnsupportedWorkflow("Step job structure is unavailable")
            runner = job["runs-on"]
            if isinstance(runner, ScalarNode):
                if not _scalar(runner):
                    raise UnsupportedWorkflow("Runner declaration is empty")
            elif isinstance(runner, SequenceNode):
                if not _sequence(runner) or any(not _scalar(item) for item in _sequence(runner)):
                    raise UnsupportedWorkflow("Runner sequence is empty or unsupported")
            elif not _mapping(runner):
                raise UnsupportedWorkflow("Runner mapping is empty")
            steps = _sequence(job["steps"])
            if not steps:
                raise UnsupportedWorkflow("Job steps are empty")
            for step_node in steps:
                step = _mapping(step_node)
                if ("uses" in step) == ("run" in step):
                    raise UnsupportedWorkflow("Step execution form is unsupported or ambiguous")
                if "uses" in step:
                    if _unpinned_reference(step["uses"], reusable=False):
                        unpinned.append(_location(step["uses"]))
                elif not _scalar(step["run"]):
                    raise UnsupportedWorkflow("Run declaration is empty")
        return WorkflowObservations(tuple(unpinned), tuple(broad))
    except (yaml.YAMLError, ValueError, RecursionError):
        raise UnsupportedWorkflow("Workflow YAML could not be inspected safely") from None
