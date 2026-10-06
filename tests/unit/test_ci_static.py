"""Conservative literal CI observations and adversarial YAML regression cases."""

from collections.abc import Callable
from dataclasses import replace
from typing import cast
from unittest.mock import MagicMock

import pytest
import yaml

from repolens.analyzers import workflow_yaml as parser
from repolens.analyzers.ci_static import RULES, GitHubActionsAnalyzer
from repolens.domain.models import (
    AnalysisContext,
    AnalyzerState,
    Category,
    FileInventory,
    Repository,
    Severity,
)
from repolens.domain.workflow import WorkflowFile, WorkflowSnapshot

SHA = "a" * 40


def workflow(reference: str = "actions/checkout@v4", permissions: str = "") -> str:
    return (
        f"on: [push, pull_request]\n{permissions}jobs:\n  build:\n"
        f"    runs-on: ubuntu-latest\n    steps:\n      - uses: {reference}\n"
    )


def context(text: str, path: str = ".github/workflows/build.yml") -> AnalysisContext:
    return AnalysisContext(
        Repository("fixture"),
        FileInventory((path,)),
        workflows=WorkflowSnapshot((WorkflowFile(path, text),)),
    )


@pytest.mark.parametrize(
    "reference,unpinned",
    [
        ("actions/checkout@v4", True),
        ("actions/checkout@main", True),
        ("owner/action/path@v1", True),
        ("owner/repo@release/v1", True),
        ("owner/repo@123abc", True),
        ("owner/repo@" + "b" * 64, True),
        ("actions/checkout@" + SHA, False),
        ("owner/action/path@" + SHA.upper(), False),
        ("./local-action", False),
        ("./.github/actions/example", False),
        ("$/local-action", False),
        ("docker://alpine:latest", False),
        ("docker://image@sha256:" + "b" * 64, False),
    ],
)
def test_step_reference_forms(reference: str, unpinned: bool) -> None:
    result = GitHubActionsAnalyzer().analyze(context(workflow(reference)))
    assert result.state == AnalyzerState.COMPLETED
    assert tuple(f.rule_id for f in result.findings) == (("CI002",) if unpinned else ())
    if unpinned:
        assert result.findings[0].severity == Severity.LOW
        assert result.findings[0].evidence[0].line_number == 6
        assert reference not in repr(result)


@pytest.mark.parametrize(
    "reference",
    [
        "just@tag",
        "owner/repo",
        "owner/repo@",
        "owner/repo@@tag",
        "https://secret@host/repo",
        "owner/repo@v 1",
        "owner/repo@foo..bar",
        "owner/repo@branch.lock",
        "owner/repo/../action@v1",
        "../local",
        "./../local",
        "docker://",
        "${{ secrets.ACTION }}",
        "owner/repo@${{ env.REF }}",
    ],
)
def test_unknown_malformed_dynamic_references_are_unavailable(reference: str) -> None:
    result = GitHubActionsAnalyzer().analyze(context(workflow(reference)))
    assert result.state == AnalyzerState.UNSUPPORTED and result.findings == ()
    assert "secrets.ACTION" not in repr(result) and "env.REF" not in repr(result)


@pytest.mark.parametrize(
    "reference,state,flag",
    [
        ("owner/repo/.github/workflows/reuse.yml@main", AnalyzerState.COMPLETED, True),
        ("owner/repo/.github/workflows/reuse.yaml@" + SHA, AnalyzerState.COMPLETED, False),
        ("./.github/workflows/reuse.yml", AnalyzerState.COMPLETED, False),
        ("$/.github/workflows/reuse.yml", AnalyzerState.COMPLETED, False),
        ("./local-action", AnalyzerState.UNSUPPORTED, False),
        ("owner/repo/.github/workflows/nested/reuse.yml@main", AnalyzerState.UNSUPPORTED, False),
        ("actions/checkout@v4", AnalyzerState.UNSUPPORTED, False),
        ("docker://alpine", AnalyzerState.UNSUPPORTED, False),
        ("${{ vars.WORKFLOW }}", AnalyzerState.UNSUPPORTED, False),
    ],
)
def test_job_level_reusable_workflows(reference: str, state: AnalyzerState, flag: bool) -> None:
    result = GitHubActionsAnalyzer().analyze(
        context(f"on: push\njobs:\n  call:\n    uses: {reference}\n")
    )
    assert result.state == state
    assert bool(result.findings) is flag


@pytest.mark.parametrize(
    "permissions,state,flag",
    [
        ("", AnalyzerState.COMPLETED, False),
        ("permissions: read-all\n", AnalyzerState.COMPLETED, False),
        ("permissions: write-all\n", AnalyzerState.COMPLETED, True),
        ("permissions: {}\n", AnalyzerState.COMPLETED, False),
        ("permissions: {contents: write}\n", AnalyzerState.COMPLETED, False),
        ("permissions: {contents: read, packages: none}\n", AnalyzerState.COMPLETED, False),
        ("permissions: write_all\n", AnalyzerState.UNSUPPORTED, False),
        ("permissions: ${{ secrets.PERMISSIONS }}\n", AnalyzerState.UNSUPPORTED, False),
        ("permissions: {contents: '${{ vars.ACCESS }}'}\n", AnalyzerState.UNSUPPORTED, False),
        ("permissions: [write-all]\n", AnalyzerState.UNSUPPORTED, False),
    ],
)
def test_permissions_observe_declaration_only(
    permissions: str, state: AnalyzerState, flag: bool
) -> None:
    result = GitHubActionsAnalyzer().analyze(
        context(workflow("actions/checkout@" + SHA, permissions))
    )
    assert result.state == state
    assert bool(result.findings) is flag
    if flag:
        assert (
            result.findings[0].rule_id == "CI003"
            and result.findings[0].evidence[0].line_number == 2
        )


def test_job_write_all_and_workflow_override_are_both_static_declarations() -> None:
    text = workflow("actions/checkout@" + SHA, "permissions: write-all\n").replace(
        "    runs-on:", "    permissions: write-all\n    runs-on:"
    )
    result = GitHubActionsAnalyzer().analyze(context(text))
    assert result.state == AnalyzerState.COMPLETED and len(result.findings) == 2
    assert all(f.rule_id == "CI003" for f in result.findings)
    assert len({f.identifier for f in result.findings}) == 2


def test_on_key_and_scalar_spelling_are_preserved() -> None:
    root = yaml.compose("on: push\nyes: no\noff: on\n", Loader=yaml.BaseLoader)
    assert root is not None
    mapping = parser._mapping(root)
    assert set(mapping) == {"on", "yes", "off"}
    assert parser._scalar(mapping["yes"]) == "no"
    assert parser._scalar(mapping["off"]) == "on"
    assert parser.inspect_workflow(WorkflowFile(".github/workflows/a.yml", workflow())).unpinned


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "[secret]",
        "secret",
        "name: secret",
        "on: push\njobs: {}",
        "on: []\njobs: {}",
        "on: {}\njobs: {}",
        "on:\njobs: {}",
        "on: ${{ vars.EVENT }}\njobs: {}",
        "on: [push, '']\njobs: {}",
        "on: [push, '${{ vars.EVENT }}']\njobs: {}",
        "on: push\non: pull_request\njobs: {}",
        "x: &anchor [value]",
        "x: *missing",
        "x: &anchor [*anchor]",
        "x: !!python/object/apply:os.system ['secret']",
        "x: !custom secret",
        "x: !!str secret",
        "%YAML 1.1\n---\nx: secret",
        "%TAG !e! tag:example.com,2020:\n---\nx: secret",
        "on: push\njobs: {}\n---\non: push\njobs: {}",
        "x: [secret",
        "? [complex, key]\n: secret",
        "env: {<<: {TOKEN: secret}}",
        "env: {TOKEN: secret, TOKEN: other}",
    ],
)
def test_yaml_and_structural_ambiguity_are_rejected_without_leaks(bad: str) -> None:
    result = GitHubActionsAnalyzer().analyze(context(bad))
    assert result.state == AnalyzerState.UNSUPPORTED and result.findings == ()
    assert "secret" not in repr(result)
    with pytest.raises(parser.UnsupportedWorkflow) as error:
        parser.inspect_workflow(WorkflowFile(".github/workflows/a.yml", bad))
    assert "secret" not in str(error.value)


@pytest.mark.parametrize(
    "extra",
    [
        "extra: " + "[" * 40 + "value" + "]" * 40 + "\n",
        "extra: [" + ",".join("{k: v}" for _ in range(1400)) + "]\n",
        "extra: [" + ",".join("v" for _ in range(257)) + "]\n",
    ],
    ids=["depth", "nodes", "collection"],
)
def test_yaml_structural_budgets(extra: str) -> None:
    result = GitHubActionsAnalyzer().analyze(context(workflow() + extra))
    assert result.state == AnalyzerState.UNSUPPORTED and not result.findings


@pytest.mark.parametrize(
    "text",
    [
        "on: push\njobs: {bad: value}",
        "on: push\njobs: {'1bad': {uses: 'owner/repo/.github/workflows/a.yml@main'}}",
        "on: push\njobs: {bad: {uses: 'owner/repo/.github/workflows/a.yml@main', steps: []}}",
        "on: push\njobs: {bad: {uses: 'owner/repo/.github/workflows/a.yml@main', runs-on: ubuntu}}",
        "on: push\njobs: {bad: {steps: []}}",
        "on: push\njobs: {bad: {runs-on: ubuntu, steps: []}}",
        "on: push\njobs: {bad: {runs-on: ubuntu, steps: [{uses: 'a/b@v1', run: secret}]}}",
        "on: push\njobs: {bad: {runs-on: ubuntu, steps: [{parallel: []}]}}",
        "on: push\njobs: {bad: {runs-on: ubuntu, steps: [{run: ''}]}}",
    ],
)
def test_unknown_execution_shapes_not_silently_skipped(text: str) -> None:
    result = GitHubActionsAnalyzer().analyze(context(text))
    assert result.state == AnalyzerState.UNSUPPORTED and not result.findings


def test_irrelevant_expressions_commands_and_runtime_values_remain_opaque() -> None:
    text = workflow("actions/setup-python@" + SHA).replace(
        "      - uses:", "      - run: echo ${{ secrets.TOKEN }}\n      - uses:"
    )
    text += "        with:\n          python-version: ${{ matrix.python }}\n"
    result = GitHubActionsAnalyzer().analyze(context(text))
    assert result.state == AnalyzerState.COMPLETED and result.findings == ()
    assert "secrets.TOKEN" not in repr(result)


def test_empty_unavailable_and_partial_failure_states() -> None:
    analyzer = GitHubActionsAnalyzer()
    assert analyzer.analyze(AnalysisContext(Repository("fixture"))).state == AnalyzerState.FAILED
    empty = AnalysisContext(
        Repository("fixture"), FileInventory(()), workflows=WorkflowSnapshot(())
    )
    (finding,) = analyzer.analyze(empty).findings
    assert finding.identifier == "ci-static:CI001" and finding.severity == Severity.INFO
    assert finding.evidence[0].file_path is None
    entries = (
        WorkflowFile(".github/workflows/a.yml", workflow()),
        WorkflowFile(".github/workflows/z.yml", "secret: ["),
    )
    ctx = AnalysisContext(
        Repository("fixture"),
        FileInventory(e.path for e in entries),
        workflows=WorkflowSnapshot(entries),
    )
    assert (
        analyzer.analyze(ctx).state == AnalyzerState.UNSUPPORTED
        and not analyzer.analyze(ctx).findings
    )


def test_order_determinism_and_controlled_evidence() -> None:
    entries = (
        WorkflowFile(".github/workflows/z.yml", workflow()),
        WorkflowFile(".github/workflows/a.yml", workflow(permissions="permissions: write-all\n")),
    )

    def run(files: tuple[WorkflowFile, ...]) -> object:
        return GitHubActionsAnalyzer().analyze(
            AnalysisContext(
                Repository("fixture"),
                FileInventory(e.path for e in files),
                workflows=WorkflowSnapshot(files),
            )
        )

    assert run(entries) == run(tuple(reversed(entries)))
    result = GitHubActionsAnalyzer().analyze(context(workflow()))
    assert result == GitHubActionsAnalyzer().analyze(context(workflow()))
    assert all(f.evidence[0].file_path == ".github/workflows/build.yml" for f in result.findings)


@pytest.mark.parametrize(
    "field,value",
    [
        ("identifier", "bad"),
        ("category", Category.SECURITY),
        ("severity", "low"),
        ("title", ""),
        ("description", " "),
        ("recommendation", ""),
    ],
)
def test_typed_catalog(field: str, value: object) -> None:
    with pytest.raises(ValueError):
        cast(Callable[..., object], replace)(RULES[0], **{field: value})
    assert tuple(r.identifier for r in RULES) == ("CI001", "CI002", "CI003")


def test_parser_resource_failure_is_noncompleted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "repolens.analyzers.ci_static.inspect_workflow",
        MagicMock(side_effect=MemoryError("secret")),
    )
    result = GitHubActionsAnalyzer().analyze(context(workflow()))
    assert result.state == AnalyzerState.FAILED and "secret" not in repr(result)


@pytest.mark.parametrize(
    "reference", ["owner/repo@foo.lock/bar", "owner/repo@.hidden", "owner/repo@release/.hidden"]
)
def test_invalid_git_ref_components_are_not_confident_findings(reference: str) -> None:
    assert (
        GitHubActionsAnalyzer().analyze(context(workflow(reference))).state
        == AnalyzerState.UNSUPPORTED
    )


@pytest.mark.parametrize(
    "runner,state",
    [
        ("ubuntu-latest", AnalyzerState.COMPLETED),
        ("[ubuntu-latest, x64]", AnalyzerState.COMPLETED),
        ("{group: trusted}", AnalyzerState.COMPLETED),
        ("", AnalyzerState.UNSUPPORTED),
        ("[]", AnalyzerState.UNSUPPORTED),
        ("{}", AnalyzerState.UNSUPPORTED),
        ("['']", AnalyzerState.UNSUPPORTED),
        ("${{ matrix.os }}", AnalyzerState.COMPLETED),
    ],
)
def test_runner_shape_is_checked_without_inference(runner: str, state: AnalyzerState) -> None:
    text = workflow().replace("runs-on: ubuntu-latest", "runs-on: " + runner)
    assert GitHubActionsAnalyzer().analyze(context(text)).state == state


def test_mapping_trigger_and_unresolved_structural_names() -> None:
    text = workflow().replace("on: [push, pull_request]", "on: {push: {}, workflow_dispatch: {}}")
    assert GitHubActionsAnalyzer().analyze(context(text)).state == AnalyzerState.COMPLETED
    for modified in (
        text.replace("push: {}", "'${{ vars.EVENT }}': {}"),
        workflow(permissions="permissions: {'${{ secrets.SCOPE }}': read}\n"),
    ):
        result = GitHubActionsAnalyzer().analyze(context(modified))
        assert result.state == AnalyzerState.UNSUPPORTED and "secrets.SCOPE" not in repr(result)


@pytest.mark.parametrize("step", ["uses: [actions/checkout@v4]", "run: {command: secret}"])
def test_nonscalar_instruction_is_unsupported(step: str) -> None:
    text = "on: push\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n      - " + step
    result = GitHubActionsAnalyzer().analyze(context(text))
    assert result.state == AnalyzerState.UNSUPPORTED and "secret" not in repr(result)
