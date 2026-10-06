# ADR 0007: Bounded workflow data and non-constructing YAML

Status: accepted for Phase 8.

## Context

GitHub Actions inspection requires non-Python text and YAML semantics. Development-
transitive PyYAML is not a runtime dependency contract. Implicit YAML 1.1 typing
can corrupt the literal on key; constructors, aliases, duplicates and large graphs
must not introduce execution, ambiguity or uncontrolled expansion.

## Decision

Add optional WorkflowSnapshot data, exactly matching direct eligible root workflow
paths, with 32-file/64-KiB/512-KiB caps. A dedicated infrastructure builder uses the
existing verified-read primitive, complete admission and all-or-nothing publication.
Domain models remain standard-library-only and analyzers receive no live I/O.

Declare PyYAML>=6.0.3,<7 as the single runtime dependency and add development typing
stubs. Stream BaseLoader events to enforce node/depth limits before composing
non-constructing nodes. Preserve scalar spellings, reject aliases/anchors, explicit
tags/directives, multiple documents, duplicate/merge/complex keys and wide collections.
Project only safe observation locations, not the complete GitHub schema or YAML data.

## Consequences

Some valid YAML/GitHub configurations are explicitly unsupported. No workflow,
expression, command, action or Docker container is executed and no network lookup
occurs. Runtime inference and scoring calibration remain deferred. Parsed structure
is not proof of GitHub validity/execution. Unsupported data prevents partial clean
results; current independent orchestration and prior content boundaries remain intact.
