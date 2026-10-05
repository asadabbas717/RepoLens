# Domain scoring contract

Phase 1 implements scoring mechanics, not calibrated product penalties. No
default scoring policy is supplied. A caller must provide a named immutable
ScoringPolicy with one penalty for each severity and a positive integer weight
for each category it intends to assess. Tests use synthetic numbers only.
Product penalty selection/calibration belongs to Phase 9 and requires evidence,
documented rationale and regression tests. There is no configuration loader yet.

## Inputs and invariants

The policy's category weights explicitly declare the assessment scope. Categories
outside that scope receive no score and must not be presented as passed. Use all
seven categories for a full repository assessment; a smaller scope must be
identified as such. Categories are code quality, testing, security, documentation,
repository hygiene, CI/CD and maintainability.

An explicit analyzer plan declares expected work. Each analyzer has a unique
identifier, category and description. Results must match this metadata exactly,
with at most one result per analyzer. Results outside the plan are rejected;
missing results remain unavailable. Finding identifiers must be globally unique.
A rule ID must belong to exactly one category. Findings must include observations,
source ownership and remediation; results validate their category and source.

Severity levels describe impact, in ascending order:

| Severity | Intended meaning |
| --- | --- |
| INFO | Context or an observation without a quality deduction |
| LOW | Limited, localized engineering weakness |
| MEDIUM | Meaningful maintainability, reliability or process weakness |
| HIGH | Substantial risk requiring priority attention |
| CRITICAL | Severe, immediate risk such as confirmed exposed credentials |

Rule authors must justify severity using actual evidence and project context,
not aesthetic preference. No concrete rules are introduced in Phase 1.
Penalty values are integer points in [0,100], nondecreasing in severity. INFO
must be zero and at least CRITICAL must be positive. Weights are positive
integers. Duplicate/missing severity entries or duplicate/empty weights fail.

## Analyzer outcomes

| State | Meaning | Scoring treatment |
| --- | --- | --- |
| COMPLETED | Finished declared work, including a clean result | Eligible for scoring |
| FAILED | Could not finish due to an error | Category incomplete |
| SKIPPED | Deliberately did not run applicable work | Category incomplete |
| UNSUPPORTED | Work cannot be performed with the available capability | Category incomplete |
| NOT_APPLICABLE | Work is explicitly irrelevant to this project context | Excluded |
| Missing result | Planned work has no recorded outcome | Category incomplete |

Every non-completed result needs a nonblank reason and must have no findings.
COMPLETED cannot carry an outcome reason. Partial work must not masquerade as
completed work. Failure isolation itself is deferred to Phase 3; unexpected
exceptions propagate across the analyzer protocol until the application layer
exists. UNSUPPORTED is not interchangeable with NOT_APPLICABLE: inability to
check something does not establish irrelevance.

## Category arithmetic

For each category, group completed findings by rule ID. Deduct once per rule
using the policy penalty for the highest observed severity. Repeated occurrences
and overlapping analyzer observations cannot multiply the penalty for that rule.
Every rule deduction retains all associated finding IDs in sorted order, its
selected severity, and raw penalty. INFO observations remain in the report.

An assessed category value is `max(0, 100 - sum(rule penalties))`. Total applied
deductions are capped at 100 points; raw deduction records remain intact even
when their sum exceeds 100. There is no additional undocumented penalty.

If any planned analyzer is missing, failed, skipped or unsupported, category
state is INCOMPLETE and value is None. Observed deductions are still retained
for explanation, without publishing a provisional numeric score. A category
in scope with no planned analyzers is also INCOMPLETE. A category whose planned
analyzers are all NOT_APPLICABLE has that state and value None. Completed work
mixed with non-applicable work remains assessed if nothing is unavailable.

## Overall arithmetic

If any in-scope category is INCOMPLETE, the overall value is None. If no category
is ASSESSED, the overall value is also None; this includes an all-non-applicable
report. Otherwise, exclude non-applicable categories and compute:

`sum(category value * category weight) / sum(assessed category weights)`

Round to two decimal places, half up. Integer quotient/remainder arithmetic
implements rounding; Decimal is used to hold the exact final value. Ambient
Decimal precision cannot change the result. Category, rule and finding-ID
ordering is deterministic; no time, random input, filesystem or network is used.

For an explicitly synthetic example, penalties INFO/LOW/MEDIUM/HIGH/CRITICAL
of 0/5/10/25/50 make two HIGH occurrences of one rule cost 25, not 50. Another
MEDIUM rule costs 10, leaving 65. These are examples, not shipped defaults.

## Report and limitations

AnalysisReport keeps repository display identity, planned analyzer metadata,
results, policy and derived scores together. It computes its score on
construction; callers cannot inject a score inconsistent with its inputs.
Score dataclasses are derived output containers: obtain them from this report
or score_repository, rather than manually assembling an assessment.

100 means no penalized findings in completed declared scope. It is not proof
of security, runtime correctness, executed test coverage or comprehensive
analysis. The analyzer plan and policy are essential context. Rule repetition
caps prevent size bias but can understate widespread occurrences; the full
evidence remains available. Tiny project/library/application applicability
decisions require later concrete rules; the scoring engine does not guess them.

Evidence uses nonempty observations, normalized relative POSIX paths and positive
1-based lines when supplied. A line needs a file path. Lexical location checks
do not resolve files or symlinks. Producers must redact secrets; this domain
does not implement secret detection, filesystem containment or report escaping.
