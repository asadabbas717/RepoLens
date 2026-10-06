# Bounded GitHub Actions workflow data

WorkflowFile/WorkflowSnapshot are immutable detached domain values containing
normalized relative paths and UTF-8 text hidden from default representations.
AnalysisContext.workflows is optional: None means unavailable, not no workflows.
Available membership must exactly match selected FileInventory paths; sorting is
by exact relative path on every platform. No root, lease, handle or read callback
enters these values. Domain code remains standard-library-only.

## Selection and budgets

Select only direct `.github/workflows/<nonempty-stem>.yml` or `.yaml` paths at the
repository root. Components and suffixes are case-sensitive. Hidden filenames
such as .build.yml count; empty stems .yml/.yaml do not. Nested workflow directories,
uppercase suffixes/components, docs/.github paths, .example backups, action.yml
outside this directory and other CI providers are not selected.
GitHub documents the root workflow directory and unsupported subdirectories in
[workflow concepts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows)
and [reusable workflows](https://docs.github.com/en/actions/how-tos/reuse-automations/reuse-workflows).
This is eligible-snapshot presence, not complete filesystem or all-provider CI.

Hard limits are 32 files, 64 KiB per file and 512 KiB total, independent of the
20,000-path inventory bound. These support dozens of modest workflows without
multi-megabyte YAML exposure. Limits apply to raw and decoded UTF-8 data; optional
BOM is removed. Other encodings and invalid Unicode fail safely.

infrastructure.workflow.snapshot_workflow_context inventories once using the
existing bounded metadata walker, admits the entire selected set before reads,
then uses the unchanged private verified_read primitive. It enforces active lease,
root containment, no link/reparse components, regular-file/descriptor identity,
size/mtime checks, bounded reads and closure. Changed size, oversized/unreadable
files, invalid decoding or count/aggregate overflow prevent publication. No partial
snapshot or empty-success fallback is returned. Existing inventory exclusions and
initial link omission apply; absence observations therefore explicitly say eligible.
Snapshots remain usable after lease closure. Existing filesystem race limitations
remain; the read boundary is not an atomic filesystem/process sandbox.

This adapter supplies workflow-only context. It does not redesign other snapshot
builders, orchestration or scan composition, and offers no unrestricted file service.

## Safe YAML contract

PyYAML is an explicit runtime dependency, `>=6.0.3,<7`, currently locked to 6.0.3.
It was previously development-transitive through Bandit, which cannot provide a
runtime contract. types-PyYAML is development-only for strict typing. No GitHub SDK
is added. Standard Python has no YAML parser; hand-written YAML parsing is avoided.

The pure parser first streams PyYAML BaseLoader events and admits at most 4,096
nodes (scalars including keys, plus collection starts) and 32 collection nesting
levels per file. It then composes BaseLoader nodes, without calling constructors.
Scalars retain literal spelling: on/yes/no/off are strings, never YAML 1.1 booleans;
quoted and unquoted spellings of the same mapping key compare identically.

All anchors and aliases, including unused and recursive anchors, are unsupported;
no alias expansion occurs. All explicit tags (even !!str), YAML version/tag
directives and multiple documents are unsupported. Empty documents are unsupported.
Every mapping in the document, including ignored env/with fields, rejects duplicate
scalar keys and << merge keys. Complex keys are unsupported. Every mapping or
sequence is capped at 256 entries. Event limits precede composition; collection
width and duplicate checks operate on the admitted bounded tree. This intentionally
rejects some YAML/GitHub-valid configurations rather than guessing their semantics.

Parser errors never expose source text or raw YAML exception messages. The retained
normalized representation contains only immutable source locations for relevant
observations, not a giant untyped dictionary, raw commands or PyYAML nodes/marks.
One-based evidence lines come from scalar source marks; column participates only
in identity. Source marks retain no buffers in normalized output. This is bounded
input/structure, not an OS memory/CPU quota. Allocation failures remain non-completed.
