# Scoring contract and product policy

Phase 1 supplies generic mechanics; Phase 9 supplies the first explicit product
policy, `application.scoring_policy.PYTHON_STATIC_V1`, identified as
`repolens-python-static-v1`. Callers still supply a named immutable ScoringPolicy
to score_repository or AnalysisReport; there is no implicit policy selection,
analyzer registration or configuration loader. Caller-supplied policies remain
supported. Earlier synthetic engine tests remain separate from product goldens.

The product penalties are INFO 0, LOW 5, MEDIUM 15, HIGH 30 and CRITICAL 60.
Its scope and weights are code quality 2, testing 1, security 3, repository hygiene
1 and CI/CD 1. Documentation and maintainability are unassessed, outside scope.
This is not yet a seven-category engineering-quality score. See
[calibration](scoring-calibration.md) for rule evidence, rationale, exact reference
scenarios, sensitivity and policy compatibility. These values are transparent
engineering heuristics, without statistical or incident-prediction validation.

Scores represent deductions from 100 within the explicitly declared, completed
assessment scope. They are not certifications, probabilities, percentile ranks
or guarantees of correctness, security, maintainability, test effectiveness,
CI success or production readiness. **100 means no score-deducting findings
observed by completed analyzers in this policy scope.** INFO observations can
still be present. **0 means distinct observed rule penalties reached the category
floor**, or all assessed categories reached it for an overall zero; it does not
prove every practice is deficient. No grades or presentation bands are assigned.

## Inputs and invariants

The policy's category weights explicitly declare the assessment scope. Categories
outside that scope receive no score and must not be presented as passed. All
seven categories would require real assessable capability and a different declared
policy; adding weights alone cannot supply missing work. Categories are code
quality, testing, security, documentation,
repository hygiene, CI/CD and maintainability.

An explicit analyzer plan declares expected work. Each analyzer has a unique
identifier, category and description. Results must match this metadata exactly,
with at most one result per analyzer. Results outside the plan are rejected;
missing results remain unavailable. Finding identifiers must be globally unique.
A rule ID must belong to exactly one category. Findings must include observations,
source ownership and remediation; results validate their category and source.

Severity levels describe impact, in ascending order:

Enum declaration/iteration order defines this hierarchy. Penalty monotonicity
and highest-severity selection both use it; lexical string ordering is never
used for impact. A regression test fixes the deliberate ordering contract.

| Severity | Intended meaning |
| --- | --- |
| INFO | Context or an observation without a quality deduction |
| LOW | Limited, localized engineering weakness |
| MEDIUM | Meaningful maintainability, reliability or process weakness |
| HIGH | Substantial risk requiring priority attention |
| CRITICAL | Severe, immediate risk such as confirmed exposed credentials |

Rule authors must justify severity using actual evidence and project context,
not aesthetic preference. Phase 9 changes no shipped rule severity.
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
completed work. Phase 3 orchestration isolates ordinary exceptions and invalid
results as sanitized FAILED outcomes. UNSUPPORTED is not interchangeable with
NOT_APPLICABLE: inability to
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
Impact measures distinct observed rule classes, not finding volume. Twenty PY001
occurrences cost 5 under v1, just as one does. Repeated BANDIT-Bnnn observations
likewise deduct once at their highest normalized severity; occurrence evidence
remains visible. No repository-size, occurrence or confidence multiplier exists.

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
Score constructors now validate value-object integrity even when called
directly. Obtain policy-derived assessments from this report or score_repository.

RuleDeduction requires a nonblank rule ID, real Severity, integer points in
0..100, and nonempty unique nonblank finding IDs. INFO deductions must be zero.
CategoryScore validates Category/ScoreState, requires integer values in 0..100
only for ASSESSED, and rejects numbers for other states. Analyzer groups must
contain unique nonblank IDs and be disjoint. Assessed work needs completed
analyzers and no unavailable work; non-applicable work needs only non-applicable
analyzers. Incomplete work needs unavailable analyzers or an entirely empty plan.
Deductions need completed work, unique rules and nonoverlapping finding IDs.

RepositoryScore requires a nonempty unique category scope. Analyzer, rule and
finding identities must not conflict across categories. Numeric overall values
must be finite Decimal values in 0..100 with exactly two decimal places, without
incomplete categories and with at least one assessed category. Complete assessed
scope needs a numeric overall value. Overall numbers cannot fall outside the
assessed category minimum/maximum. Collections are copied to immutable tuples.

These are structural and availability invariants, not policy recalculation.
Constructors do not recompute category penalties or the weighted mean: the
policy is not part of these value objects. A structurally valid manually supplied
number is not evidence that policy arithmetic was followed; AnalysisReport and
score_repository remain the trusted derivation path.

100 means no penalized findings in completed declared scope. TEST001/TEST002 can
leave testing at 100 and CI001 can leave CI/CD at 100; these uncertain absence
observations remain INFO. Testing currently has no deductive rules, so completed
testing always scores 100 under v1. This can raise an overall mean relative to a
non-applicable testing category; the calibration document quantifies that effect.
Category values are comparable only with their scope and availability context.
100 is not proof of security, runtime correctness, executed test coverage or comprehensive
analysis. The analyzer plan and policy are essential context. Rule repetition
caps prevent size bias but can understate widespread occurrences; the full
evidence remains available. Tiny project/library/application applicability
decisions require later concrete rules; the scoring engine does not guess them.

Security currently means supported detached Bandit observations, not a clean
dependency graph. Missing Bandit is UNSUPPORTED. DependencyAuditAnalyzer produces
FAILED or UNSUPPORTED, never a clean audit: structured advisory severity is still
unavailable. If declared in the plan, it blocks security and overall numbers even
when Bandit completes cleanly. Choosing a Bandit-only plan must be disclosed;
unavailable work must never be removed after execution to salvage a number.

Any future penalty, category weight or scope change requires a new policy
identifier. Keep the identifier together with plan, results and score;
AnalysisReport already retains the complete policy. Analyzer/tool versions and
input eligibility also matter for comparison; the policy identifier alone cannot
freeze those inputs. Do not mutate released v1 values under the existing name.

Evidence uses nonempty observations, normalized relative POSIX paths and positive
1-based lines when supplied. A line needs a file path. Lexical location checks
do not resolve files or symlinks. Producers must redact secrets; this domain
does not implement secret detection, filesystem containment or report escaping.
