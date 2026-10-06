# ADR 0005: detached bounded Python source

Status: accepted, 2026-10-06

## Context and decision

Phase 4 paths suffice for hygiene but cannot support genuine AST observations.
Add immutable validated PythonSourceFile and PythonSourceSnapshot values and an
optional source field in AnalysisContext. Keep infrastructure reads out of the
domain/analyzers; source snapshot paths must exactly match selected inventory
paths to prevent accidentally complete-looking partial data.

The infrastructure composition boundary inventories once using the shared safe
metadata walk, admits all eligible Python candidates within explicit byte/count
budgets, then performs verified bounded reads and Python encoding detection under
an active lease. Oversized selected source must fail, not disappear through the
old path-only filter. repository_files retains its original Phase 2 behavior over
that shared walk. Detached text grants no live filesystem capability.

Reject raw roots, leases, arbitrary read callbacks and universal filesystem
services in analyzer context. They blur lifetime and bypass traversal safeguards.
Reject unrestricted whole-tree text materialization because 20,000 path entries
alone are not a practical source-memory budget.

## Consequences

The analyzer can parse pure bounded values without target imports or execution,
and tests separate resource/encoding/path failures from structural rules. Request
3.13 grammar consistently on supported hosts, while documenting the standard
library's best-effort guarantee and testing relevant cross-version boundaries.
Any unparseable source produces a non-completed outcome without partial findings;
this intentionally prioritizes honest availability over a report of every
parseable sibling. Runtime scope validation and complex lint semantics remain
outside the two-rule catalog.

File metadata checks are not a hostile-writer sandbox or atomic snapshot; input
limits are not total AST heap/process quotas. Future tooling and security/testing
analysis need independent justification. Orchestration, score policy and Phase 6
functionality are unchanged.
