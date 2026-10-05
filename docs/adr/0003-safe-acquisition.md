# ADR 0003: Context-owned static repository acquisition

Status: Accepted (2026-10-06)

## Context

Repository sources are potentially hostile. Acquisition must not run project
code, leak credentials or silently mutate a user's local working tree. Tests
must remain deterministic without live GitHub. Domain values should stay pure.

## Decision

Use standard-library context managers, pathlib and an isolated Git executable
boundary. Local acquisition is a live working-tree view; linked worktrees and
unborn repositories are supported. Root/commit verification is read-only with
all transport forbidden and lazy fetching disabled. Public GitHub clone inputs
are restricted to structurally validated HTTPS repository roots.

Remote repositories live in context-owned TemporaryDirectory workspaces. Empty
Git templates/hooks and isolated configuration prevent inherited hook/filter
execution. Clone shallowly without tags, redirects, authentication or submodules.
Expose sanitized errors, bounded retained output and explicit timeouts.

Provide a no-content-read bounded path inventory with no symlink/reparse descent.
RepoLens exclusions are independent of .gitignore. RepositoryLease owns temporary
root lifetime and holds a domain Repository identity; no domain changes are needed.
See ../acquisition.md for exact limits, controls and their documented purposes.

## Consequences

Local results can reflect uncommitted/ignored content and concurrent edits.
Remote sources requiring auth, redirects, custom proxies or user Git settings
fail deliberately. LFS/submodule contents are not acquired. Output polling and
timeouts are practical bounds, not disk quotas or process-tree isolation.
Cleanup is attempted on every normal exit path; OS denial/crashes can defeat
physical removal and must not be represented as success.

## Alternatives considered

GitPython: adds a dependency without eliminating Git subprocess security concerns.
GitHub SDK/authentication: unnecessary for public clones and expands credential scope.
Archive downloads: would require additional HTTP/decompression/path-safety design.
Executing target setup/tests: violates the static acquisition boundary.
Respecting every .gitignore rule now: risks hiding relevant untracked evidence and
requires semantics not needed by this phase. OS-wide sandbox/job management:
stronger limits but substantial platform machinery; state current limitations
honestly and defer stronger isolation to a separately designed increment.
