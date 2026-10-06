# Python structural rules

PythonStaticAnalyzer has stable ID `python-static`, category CODE_QUALITY and
an immutable typed catalog. These are small AST observations, not a complete
Python linter, runtime syntax certification, security scan or testing assessment.

| Rule | Severity | Observation |
| --- | --- | --- |
| PY001 | LOW | ExceptHandler has no exception type |
| PY002 | LOW | ImportFrom contains a wildcard, except in .pyi stubs |

## PY001: bare except

Evidence identifies the relative file and handler's first line without copying
its body or literals. A bare handler can intercept BaseException subclasses,
including process-control exceptions. Prefer specifically intended types when
that broad behavior is unnecessary. LOW reflects a potentially unintended
exception-handling choice, not proof of swallowed errors or a runtime defect.
Intentional cleanup/re-raise handlers may retain a bare catch; this structural
observation does not analyze handler control flow. Explicit Exception,
BaseException, tuples of types and except-star handlers are not bare catches.

## PY002: wildcard import

Evidence identifies the relative module path and import line, never imported
module names or source text. Wildcard imports obscure local name origins; prefer
explicit imports where practical. LOW reflects that maintainability concern,
not proof of missing/undefined symbols or unsafe execution. Deliberate public
re-export modules may justify the pattern. The check is omitted for .pyi files
because wildcard re-exports are a common stub API declaration. Module contents,
__all__, installed dependencies and runtime resolution are not inspected.
Ordinary imports, explicit from-imports, comments and matching strings are not
findings.

## Grammar and outcomes

Parse each selected file once with ast.parse, feature_version=(3, 13), optimize=0,
then perform one iterative ast.walk serving both rules. Type-comment analysis,
AST compilation into executable code and runtime scoping validation are not
performed. No target module is imported, evaluated or executed.

The intended target is Python 3.13 syntax, independent of RepoLens's 3.13/3.14
host. Python documents feature_version as best-effort, not a universal grammar
emulator. Tests pin outcomes for 3.13 type-parameter defaults, match, except-star,
and rejected 3.14-only template strings/unparenthesized exception lists. Future
runtime/parser differences outside this tested subset may require further review.
Successful AST parsing alone does not establish executable or correct Python.

Available, fully parsed source produces COMPLETED, even with no findings. An
available empty source set is NOT_APPLICABLE. Missing required source data is
FAILED. SyntaxError or null-input ValueError gives UNSUPPORTED with a fixed
"not parseable with the Python 3.13 grammar" reason, discarding earlier findings.
This does not distinguish broken syntax from syntax outside the selected grammar
and does not accuse the repository of invalid Python. Recursion/MemoryError in
parsing gives FAILED; other unexpected errors use Phase 3's sanitized isolation.
No unparseable file silently disappears and no partial findings imply complete
coverage. Unsupported/failed work blocks numeric scores under existing policy.

Target SyntaxWarning/DeprecationWarning messages can contain literals and vary
by host version. They are suppressed only within the individual target AST parse;
project tests retain their unchanged warning-as-error gate. Raw diagnostics and
warning text are not published. Read/encoding/budget failures are acquisition
errors before an analyzer-facing context exists, not grammar observations.

## Identities and mature tools

Occurrence IDs are `python-static:<rule ID>:<SHA-256 hex>`. The hash input is rule
ID, NUL, normalized relative path, NUL, and `<line>:<UTF-8 byte column>`. NULs are
invalid in paths, so input fields are unambiguous. IDs contain no absolute root,
randomness or time. Adding earlier lines can change location and identity; perfect
persistence across edits is not claimed. Final findings sort by exact ID and use
1-based evidence lines. Separate occurrences, including same-line locations,
remain distinguishable.

Ruff's existing [E722](https://docs.astral.sh/ruff/rules/bare-except/) and
[F403](https://docs.astral.sh/ruff/rules/undefined-local-with-import-star/) cover
these simple patterns. Phase 5 deliberately stays AST-only to establish bounded
source composition and two precisely stated observations. It does not attempt
Ruff parity, sophisticated analysis or a competing lint framework. A broader
mature-tool adapter is deferred until it adds concrete value warranting reviewed
executable/configuration/cache/output/timeout controls. Ruff remains a project
quality tool, not a target adapter. The analyzer selects no scoring policy;
Phase 9 supplies separate explicit [product values](../scoring-calibration.md).
Earlier mechanism tests retain their synthetic numbers.
