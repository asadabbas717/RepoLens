# Python static policy v1 calibration

`application.scoring_policy.PYTHON_STATIC_V1` is an explicit immutable
ScoringPolicy named **repolens-python-static-v1**. It contains values only;
domain scoring arithmetic, caller-owned plans and analyzer states are unchanged.
There is no default execution plan, configuration loading or automatic exclusion
of unavailable work. A caller selects this instance explicitly for its report.

## Method and evidence

We inventoried every shipped rule and analyzer outcome before selecting values.
Neutral controlled typed results test arithmetic independently of detection.
Small clean, informational and mixed detached repository fixtures then exercise
real hygiene, Python, testing and CI analyzers plus the real security normalizer
with controlled Bandit observations. They are inert snapshots, not executed
projects or a claim of empirical validation across public repositories. No
score from RepoLens itself was used to choose or tune this policy. Representative
public-repository validation and independent self-dogfooding remain future work.

This first policy is a transparent engineering heuristic. Exact ratios have not
been statistically validated, established as an industry standard or shown to
predict incidents. Calibration asks whether effects are understandable,
monotonic, bounded, reproducible and honest about unsupported evidence.

| Rule / analyzer | Severity | Why retained |
| --- | --- | --- |
| RH001 / repository-hygiene | INFO | Missing eligible root ignore path does not prove absent or ineffective ignore policy |
| RH002 / repository-hygiene | LOW | ASCII case collisions show a limited, reversible checkout-portability risk |
| PY001 / python-static | LOW | Bare except can catch process-control exceptions; intention/control flow is not established |
| PY002 / python-static | LOW | Wildcard imports obscure name origins; deliberate re-exports can be justified |
| TEST001 / testing-static | INFO | Conventional source absence cannot disprove custom discovery |
| TEST002 / testing-static | INFO | Missing direct declarations cannot disprove generated or custom-loaded tests |
| BANDIT-Bnnn / python-security | LOW, MEDIUM, HIGH | Preserve validated native severity exactly; static evidence is not proof of exploitability; confidence does not modify impact |
| dependency-audit | No findings | Auditing lacks structured advisory severity; inventing impact would be misleading |
| CI001 / ci-static | INFO | No observed GitHub Actions workflows cannot disprove another CI provider |
| CI002 / ci-static | LOW | Remote ref lacks immutable SHA form; actual provenance and code safety are unknown |
| CI003 / ci-static | LOW | Literal write-all is broad but overrides/platform controls and legitimate need are unknown |

No severity was changed. Bandit has no copied catalog: rule identity comes from
the validated vendor test ID. No currently shipped analyzer emits CRITICAL;
its policy value is exercised only with explicitly synthetic reference rules.

| Analyzer | Possible direct outcomes |
| --- | --- |
| repository-hygiene | COMPLETED with available inventory; FAILED if unavailable |
| python-static | COMPLETED, NOT_APPLICABLE for empty sources, UNSUPPORTED grammar, FAILED missing data/resources |
| testing-static | COMPLETED including INFO-only, NOT_APPLICABLE empty sources, UNSUPPORTED candidate grammar, FAILED missing data/resources |
| python-security | COMPLETED, NOT_APPLICABLE no .py, UNSUPPORTED grammar/tool, FAILED missing data/resources/tool operation |
| dependency-audit | FAILED missing/malformed data; UNSUPPORTED unknown scope/syntax or unavailable auditing, including valid exact pins |
| ci-static | COMPLETED including absent workflows, UNSUPPORTED YAML/structure/unresolved observations, FAILED missing data/resources |

All ordinary unexpected execution or invalid-result errors become FAILED through
orchestration. SKIPPED is a valid domain outcome even though current concrete
analyzers do not directly select it. Missing planned work is unavailable.
NOT_APPLICABLE establishes irrelevance; UNSUPPORTED establishes no such thing.

## Exact penalties

| Severity | Points | One-rule category value | Rationale |
| --- | ---: | ---: | --- |
| INFO | 0 | 100 | Uncertain context is visible without inventing a defect |
| LOW | 5 | 95 | One twentieth of the category range is a modest, visible deduction |
| MEDIUM | 15 | 85 | Three LOW deductions make meaningful evidence clearly more consequential |
| HIGH | 30 | 70 | Twice MEDIUM materially changes the category without one finding exhausting it |
| CRITICAL | 60 | 40 | Twice HIGH consumes most of the category; two distinct critical rules reach zero |

These round ratios deliberately replace the earlier synthetic 0/5/10/25/50
example; matching INFO/LOW values is independently justified above. Rule penalties
sum once per rule at the highest severity, then category value is
`max(0, 100 - sum(points))`. Raw deductions remain traceable beyond the floor.
One hundred findings of one rule do not mean one hundred deductions. This limits
size bias but can understate widespread patterns; finding volume remains visible.
Future changes to this trade-off require a separately reviewed policy/model version.

## Scope and weights

| Category | Weight | Full-scope share | Rationale |
| --- | ---: | ---: | --- |
| CODE_QUALITY | 2 | 2/8 | Supported structural reliability/name-origin observations deserve more influence than one narrow ancillary signal |
| TESTING | 1 | 1/8 | Keep observed testing context explicit with minimum positive influence; currently INFO-only, not test effectiveness |
| SECURITY | 3 | 3/8 | Prioritize genuine severity-backed security patterns, while keeping influence below half the total |
| REPOSITORY_HYGIENE | 1 | 1/8 | Narrow path-portability evidence deserves modest influence |
| CI_CD | 1 | 1/8 | Limited static reference/permission evidence does not establish effective runtime controls |
| DOCUMENTATION | Outside scope | Unassessed | No shipped analyzer |
| MAINTAINABILITY | Outside scope | Unassessed | No shipped analyzer |

Equal weights would give narrow INFO-only testing as much influence as security.
The 2:1:3:1:1 ratio instead makes priorities deliberate with no false numerical
precision. A five-category score is not a complete seven-category assessment.
Missing work within these five categories is INCOMPLETE, not an automatic 100.

The policy declares categories, not capability completeness within them. Security
with only python-security is Bandit-only evidence. Dependency vulnerability
analysis is still unavailable. If dependency-audit is part of the declared plan,
its UNSUPPORTED result makes security and overall None; do not remove it after
execution. Missing Bandit also blocks numbers. No dependency security claim can
be inferred from a numeric Bandit-only result.

## Stable reference scenarios

Category tuple order below is **code quality, testing, security, hygiene, CI/CD**.
Unless specified, one controlled analyzer per category completes and unaffected
categories have no findings. Unit fixtures live in test_product_scoring.py;
real analyzer composition fixtures live in test_product_policy.py.

| Scenario | Category values | Overall |
| --- | --- | ---: |
| Clean supported scope | 100, 100, 100, 100, 100 | 100.00 |
| INFO-only RH001, TEST001, CI001 | 100, 100, 100, 100, 100 | 100.00 |
| One LOW PY001 | 95, 100, 100, 100, 100 | 98.75 |
| Distinct LOW PY001 and PY002 | 90, 100, 100, 100, 100 | 97.50 |
| Twenty LOW PY001 occurrences | 95, 100, 100, 100, 100 | 98.75 |
| MEDIUM BANDIT-B301 | 100, 100, 85, 100, 100 | 94.38 |
| HIGH BANDIT-B602 | 100, 100, 70, 100, 100 | 88.75 |
| Four distinct HIGH security rules (120 raw points) | 100, 100, 0, 100, 100 | 62.50 |
| Two synthetic distinct CRITICAL security rules | 100, 100, 0, 100, 100 | 62.50 |
| Mixed PY001/PY002, TEST002 INFO, MEDIUM/HIGH security, RH002, CI002/CI003 | 90, 100, 55, 95, 90 | 78.75 |
| Testing NOT_APPLICABLE, RH002 LOW | 100, None, 100, 95, 100 | 99.29 |
| Additional security FAILED/SKIPPED/UNSUPPORTED, HIGH still observed | 100, 100, None, 100, 100 | None |
| Missing planned CI result | 100, 100, 100, 100, None | None |
| Dependency audit planned alongside clean Bandit | 100, 100, None, 100, 100 | None |
| Missing Bandit alongside completed other work | 100, 100, None, 100, 100 | None |
| Empty plan | None, None, None, None, None | None |
| Only code-quality work planned and completed | 100, None, None, None, None | None |
| Every category explicitly NOT_APPLICABLE | None, None, None, None, None | None |

The mixed real-output fixture uses TEST001 rather than TEST002; both have zero
penalty, and its exact values remain the same. Bandit observations there are
controlled normalized vendor fixtures, not assertions about what Bandit detects
from the fixture source. Existing detached real-tool integration coverage remains.
The dependency reference covers unknown manifests, empty declarations, exact pins
and unsupported ranges. None of these is a completed vulnerability audit.

Overall arithmetic is `sum(value * weight) / sum(assessed weights)` rounded half
up to two decimals. Mixed is `(90*2 + 100 + 55*3 + 95 + 90) / 8 = 78.75`.
Testing non-applicable excludes weight 1 entirely:
`(100*2 + 100*3 + 95 + 100) / 7 = 99.29` after rounding. All non-applicable scope
has no assessed denominator and no numeric value. Any incomplete category blocks
the overall value, retaining observed deductions for explanation.

## Sensitivity review

With all five categories assessed, one security rule gives these overall values:

| Severity | Security value | Overall |
| --- | ---: | ---: |
| INFO | 100 | 100.00 |
| LOW | 95 | 98.13 |
| MEDIUM | 85 | 94.38 |
| HIGH | 70 | 88.75 |
| CRITICAL (synthetic) | 40 | 77.50 |

One LOW quality rule gives 98.75; one LOW hygiene or CI rule gives 99.38.
The unrounded LOW security result 98.125 rounds **up** to 98.13; MEDIUM 94.375
rounds to 94.38 and LOW hygiene 99.375 to 99.38. Decimal context precision does
not alter these values. HIGH changes security twice as much as MEDIUM. Two
distinct CRITICAL or four HIGH rules saturate security at zero. Security accounts
for at most 37.5 overall points with all categories assessed; no category dominates
the full mean. After non-applicable exclusions its share can grow, up to all the
assessed denominator if it is the only applicable category. Always disclose scope.

Completed INFO-only testing adds a 100-valued weight to the mean. In the mixed
reference, explicitly non-applicable testing would yield 75.71 instead of 78.75.
This is an arithmetic consequence, not evidence of test effectiveness. We retain
the existing model with honest interpretation rather than introduce a second
score, zero weights or rule-specific exceptions. TEST001/TEST002 and CI001 must
remain visible even at 100; absent conventions do not establish failing practices.

## Interpretation and compatibility

100 means **no deductive findings among the completed supported observations**,
including possible INFO advisories. Zero means observed distinct rule penalties
reached the floor. Neither is a certification or a runtime quality measure.
Scores are not probabilities, ranks, test pass rates, guarantees of security,
maintainability, CI success or production readiness. Do not infer grades or bands.

Changes to penalties, weights or category scope require a **new policy identifier**;
never silently alter released v1 values. Keep identifier, full policy, analyzer
plan, states and findings together for reproduction; AnalysisReport already does.
Input selection, rule/catalog and tool versions also affect comparability. The
identifier cannot make different analyzer coverage or missing work comparable.
No scoring mechanics changed and no new runtime dependency was added. Existing
mechanism/version boundaries make an additional ADR unnecessary for this value
profile; the public compatibility decision is documented here and regression-tested.
