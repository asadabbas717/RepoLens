# Analysis orchestration contract

Phase 3 provides explicit in-process registration and sequential execution of
trusted RepoLens analyzers. It implements no concrete checks, acquisition,
traversal, CLI, configuration, rendering or scoring policy.

## Registration

Construct AnalyzerPlan from an iterable of Analyzer protocol implementations.
Each exposes spec and analyze(context). Registration reads spec and the bound
callable exactly once. Metadata must be an AnalyzerSpec and analyze must be
callable. Unusable registrations raise a sanitized ValueError before execution;
duplicate exact identifiers also raise ValueError. No identities are fabricated.
Errors while iterating a caller-provided iterable are caller errors and are not
analyzer outcomes.

The frozen plan stores a tuple sorted by exact identifier using Python string
ordering (case-sensitive, with no case folding or Unicode normalization).
Caller collection mutations cannot change membership. plan.specs exposes the
ordered immutable domain metadata for report composition. No global registry,
dynamic discovery, entry points, reflection-based loading or default analyzers
are installed. An empty plan is supported and produces an empty result tuple.

The plan snapshots callables and metadata, not analyzer internal state. Changing
an analyzer's method afterward does not replace the registered callable. State
changes inside that callable can change its outputs; analyzer determinism remains
the producer's responsibility. Metadata is not reread during execution. A result
with changed metadata fails ownership validation against the registered snapshot.

## Execution and acceptance

execute_analyzers(plan, context) invokes each registered callable exactly once
in plan order, passing the supplied AnalysisContext. There are no retries,
threads, workers or asynchronous jobs. Each run creates its own result and
validation state; no run state is shared by the engine.

Each invocation produces exactly one result, including when it fails. Accepted
results must be AnalyzerResult values whose complete AnalyzerSpec equals the
registered snapshot: identifier, category and description. Findings are ordered
by identifier, using the domain constructor's existing source/category/state
validation. COMPLETED, FAILED, SKIPPED, UNSUPPORTED and NOT_APPLICABLE retain
their meaning. Completed empty findings are valid; unavailable work is not a pass.

Across accepted results, finding IDs must be globally unique and one rule ID
must have exactly one category, matching the domain report contract. A conflicting
result is rejected as a whole; its findings reserve no identifiers or categories.
The earlier accepted analyzer in canonical identifier order retains its result,
so supplied registration order never decides conflict precedence. Shared rules
within one category remain valid. Later analyzers continue normally.

Ordinary exceptions from analyzer execution become FAILED with the fixed reason
"Analyzer execution failed". Invalid result shape, ownership or aggregate
consistency becomes FAILED with "Analyzer returned an invalid result". Raw
exception text, tracebacks, exception objects and OS diagnostics are not stored
in results or logs. Registration errors suppress raw exception context.
Analyzer-provided valid reasons and evidence are preserved: trusted producers
must redact sensitive content themselves; the engine does not inspect arbitrary
text for secrets.

KeyboardInterrupt, SystemExit and other BaseException cancellation signals
propagate; later analyzers do not run after cancellation. The engine is not a
process sandbox, timeout manager or resource quota. A trusted analyzer that hangs
can block sequential execution; hostile analyzer plugins are unsupported.

## Acquisition, reports and future data access

The original Phase 3 AnalysisContext contract supplied display identity only.
Phase 4 adds optional bounded FileInventory data while preserving identity-only
callers. Callers can explicitly acquire a source and pass lease.identity as
that identity, but the engine never starts or closes acquisition. It imports
only domain APIs and the standard library; no infrastructure objects enter the
domain. All Phase 2 path, lifetime and subprocess safeguards remain independent.
Future content analysis requires a separately justified bounded data-access seam; Phase 4 now supplies an immutable relative-path inventory, documented in
[repository data](repository-data.md), without introducing content reads. Phase 5 adds detached bounded Python text
through infrastructure; the engine remains generic and performs no reads.

Execution returns an immutable ordered tuple of AnalyzerResult values. For a
scored snapshot, callers construct AnalysisReport(repository, plan.specs,
results, policy) with an explicit ScoringPolicy. The engine supplies no weights,
penalties, default scope or calibration and does not render. Existing domain
scoring determines incomplete/non-applicable categories; even an empty plan
cannot imply a perfect score for a declared scope. A policy that excludes a
planned category remains a caller composition error in the domain report.

Unit tests use controlled analyzers to prove registration, ownership, lifecycle,
sanitization and ordering. Integration tests compose acquisition identity and
real domain reports, reject engine acquisition/subprocess calls and verify that
unavailable outcomes suppress numeric scores. All scoring numbers in test
fixtures are synthetic, not product defaults.
