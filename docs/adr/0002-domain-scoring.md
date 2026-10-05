# ADR 0002: Immutable findings and conservative explicit scoring

Status: Accepted (2026-10-05)

## Context

Static repository signals need machine-readable evidence and deterministic,
explainable scores. Failed or unimplemented checks must not produce false
perfect scores. No analyzers or representative calibration samples exist yet.

## Decision

Use frozen, slotted standard-library dataclasses and enums for findings,
evidence, analyzer metadata/results, policy and reports. A structural Analyzer
protocol establishes the extensibility boundary without a base-class hierarchy.
AnalysisContext holds only repository display identity at this stage. Extend it
with justified safe data later, not speculative filesystem APIs now.

Require an explicit named scoring policy and expected analyzer plan. There is
no default severity penalty table or category weighting until calibration is
justified. Score each rule once at its highest observed severity, retain all
finding references, start assessed categories at 100 and floor at zero.

Distinguish unsupported/skipped/failed/missing work from explicit irrelevance.
Unavailable work withholds its category and overall score. Non-applicable work
is excluded with a reason; no completed work means no score. Reports calculate
scores from their own immutable inputs. See ../scoring.md for exact arithmetic.

## Consequences

Callers must supply scope, policy and planned work. Partial analysis still
provides evidence but cannot claim a numeric overall assessment. Category
weights are explicit assessment choices, not hidden engine constants.
Rule caps limit size bias but do not capture occurrence prevalence in the score;
evidence retains every occurrence. Recommendations remain attached to findings,
without a redundant recommendation hierarchy. ValueError handles invalid pure
domain construction; an application exception hierarchy is not needed yet.

## Alternatives considered

Default penalty numbers now: premature calibration with no supporting evidence.
Scoring only returned results: hides missing and failed checks.
Assigning zero to failed checks: conflates tool failure with repository quality.
Publishing a partial average: can falsely reward incomplete security analysis.
Penalizing every occurrence: makes large repositories and overlapping analyzers
disproportionately expensive. Pydantic: no external parsing boundary currently
requires a runtime dependency. Abstract analyzer base classes: unnecessary
inheritance when structural typing defines the boundary clearly.
