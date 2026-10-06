# Phase 13 product validation

## Method and provenance

Dogfooding on 2026-10-06 used development version 0.1.0.dev0, supported Bandit
1.9.4 and unchanged policy `repolens-python-static-v1`. Software HEAD was
`faca9217ab47cb90b8e9fa477c82face5675e5c9`; the working tree also contained the
Phase 13 owned fixture tests and documentation. No production source or policy
changed. Phase 12's four hosted jobs were independently confirmed successful in
[Quality run 37509070101](https://github.com/asadabbas717/RepoLens/actions/runs/37509070101).

Real installed CLI scans produced console, JSON and HTML reports. Generated
reports/drivers stayed in already ignored development storage; none are committed.
Fixture source is owned inert string data in `tests/integration/dogfood_cases.py`,
materialized into temporary Git repositories. No nested Git repositories or
third-party source are committed. The normal test suite has no live network input.

Reports were compared with actual evidence, analyzer states, deduction ownership,
recommendations and exit codes. Repeated JSON bytes were compared without ignoring
or normalizing fields. HTML was opened locally for visual inspection; existing
escaping/structure tests remain authoritative for hostile strings. Scans completed
without an obvious performance problem; no timing SLA or concurrency was added.

## RepoLens self-scan

The actual working tree scored **88.75**, available, with **904 findings**.
All five default analyzers completed. Code quality, testing, hygiene and CI/CD
each scored 100; security scored 70. No configuration or rule suppression applied.
Console, JSON and HTML returned 0 without a requested gate. A freshly installed
wheel repeat agrees with the initial JSON report byte-for-byte.

Every finding location was checked against an existing source file and valid line.
Every B101 location was additionally checked against an AST Assert node. The
following exhaustive grouping assigns a triage classification to every finding:

| Rule / count | Location and review | Classification |
| --- | --- | --- |
| BANDIT-B101 / 897 LOW | All in 38 test files; intentional test assertions, not production security enforcement | Valid accepted tradeoff |
| BANDIT-B404 / 4 LOW | Two trusted infrastructure imports and two test imports of subprocess | Valid accepted tradeoff |
| BANDIT-B603 / 2 LOW | Git and Bandit launch boundaries use application-built arrays, absolute executables, isolated inputs, timeouts and capture limits | Valid accepted tradeoff |
| BANDIT-B108 / 1 MEDIUM | An absolute temporary-path literal in `test_security.py` is rejected mock output, not a filesystem operation | Informational observation of inert test data |

The subprocess primitive observations remain legitimate static review prompts;
accepting their constrained uses does not make the observations false. B101 also
correctly observes a construct that Python optimization can remove; tests use
assertions deliberately. The B108 literal does not establish an unsafe temporary
file is created. Generic vendor wording already asks for context review and does
not claim exploitation. No finding requires a product fix from this review.

One deduction per rule is intentional: LOW B101/B404/B603 deduct 5 each and MEDIUM
B108 deducts 15, regardless of occurrence count. Security is 100 - 30 = 70.
Overall is `(100*2 + 100 + 70*3 + 100 + 100) / 8 = 88.75`.
There is no self-score target and no penalty, severity or exclusion was adjusted.

Initial scans failed safely with exit 2 because the local working-tree root and
Git directory had different Windows owners after sandbox Git work. The user
authorized restoring only the Git directory owner to match the working-tree
owner. Contents, access permissions, Git configuration, safety checks and GitHub
state were unchanged; real self-scans then succeeded. This was an environment
repair, not a reason to bypass Git isolation or modify production acquisition.

The full report is long because test assertions remain visible. Identity ordering
is deterministic, not severity sorting. This is a documented usability limitation,
not justification to suppress legitimate observations or redesign reporting here.

## Controlled default scenarios

| Scenario | Overall / exits | Category interpretation |
| --- | --- | --- |
| Clean Python | 100.00 / 0 in all formats | Five completed categories, no findings |
| Poor Python | 92.50 / 0 without gates in all formats | Code quality 90, testing 100, security 90, hygiene 100, CI/CD 90 |
| Non-Python | 100.00 / 0 in all formats | Only hygiene and CI/CD assessed; code quality/testing/security NOT_APPLICABLE |

The clean case includes an exact root ignore path, safe Python, a conventional
test declaration and an inert workflow with read-all permissions and a synthetic
40-hex remote action reference. This reference is not downloaded or asserted to
identify real reviewed code. 100 means no deductive findings in implemented
completed scope, not universal perfection or measured test effectiveness.

The poor case produces eight findings: PY001/PY002, CI002/CI003, BANDIT-B105/B110
(LOW), and RH001/TEST001 (INFO). File/line evidence agrees with fixture text;
all recommendations are nonblank and deductions reference active finding IDs.
Each of the three deductive categories loses 10 points, yielding 740/8 = 92.50.
Application, setup, test-shaped source and workflow marker commands remain inert;
no execution markers appear. Invalid target repolens.toml is never discovered.

The non-Python case contains inert HTML/JavaScript and a supported workflow.
Its denominator is the hygiene/CI weights, 2; Python-specific weights are excluded.
It establishes no JavaScript or HTML code-quality analysis. Bandit is irrelevant
to that absent Python scope; dedicated existing tests also cover absent tools.

## Configured scenario and gates

The explicitly selected trusted file uses exactly schema 1:

```toml
schema_version = 1
[scan]
exclude = ["setup.py", "checks.py"]
[rules]
disable = ["PY002", "CI003", "BANDIT-B105"]
[gate]
fail_under = "99"
fail_on_severity = "medium"
```

Configured poor results are separate from the default quality observations.
Exclusions remove those files from eligible data; suppressed findings and deductions
disappear, while all five analyzer results remain represented. Console/JSON/HTML
disclose canonical exclusions, disabled IDs and gate settings. Remaining findings
are PY001, CI002, BANDIT-B110, RH001 and TEST001. Category values are 95/100/95/100/95;
overall is 770/8 = **96.25**. The score gate fails, severity MEDIUM passes and all
formats still render with exit 1. CLI --fail-under 0 returns 0; additionally
overriding severity to LOW returns 1. Injected security failure still yields an
unavailable score/exit 1 even with disabled Bandit rules and a zero threshold.

Practical gate checks cover clean score 100 plus INFO gate passing, poor equality
92.50 passing, 92.51 failing, LOW failing, MEDIUM passing, and non-Python score 100
passing. Invalid trusted config and missing required HTML output return 2.
An injected internal exception returns sanitized 3 in tests only. No ordinary
dogfood scan deliberately triggers that path. Existing tests cover unavailable
tool states and publication failures without weakening their behavior.

Clean, poor and configured JSON repeats are byte-identical, as are non-Python
repeats. Installed-wheel repetitions also compare complete bytes. No fields are
ignored; fixture contents, supported tool and configuration are held fixed.

The built wheel was reinstalled with --no-index/--no-deps in a separate smoke
environment containing pip, PyYAML, RepoLens and supported Bandit plus its required
dependencies. No pytest, mypy or Ruff was installed there. Actual version/help/
scan-help and all three reports for each fixture passed, including configured
gates, repeated JSON and marker absence, from a working directory outside the
project source. With Bandit temporarily uninstalled, clean Python became
UNSUPPORTED/unavailable with exit 1; non-Python remained NOT_APPLICABLE and
available with exit 0. Supported Bandit was restored offline from the tool cache.

## Manual public example

The actual CLI scanned [pallets/itsdangerous](https://github.com/pallets/itsdangerous)
through `scan https://github.com/pallets/itsdangerous --format json` on 2026-10-06.
Public identity was `itsdangerous`; observed acquisition commit was
`672971d66a2ef9f85151e53283113f33d642dabd`. A follow-up using existing acquisition
metadata observed that commit, asserted the temporary clone was removed before
analyzer execution, and produced JSON byte-identical to the CLI scan. The CLI
schema itself does not expose the target commit, so this is separate manual
provenance evidence, not a new runtime field.

All five analyzers completed; score was **81.25**, exit 0 without gates, 69 findings.
Code quality/testing/hygiene/CI scored 100; security scored 50. Counts were
BANDIT-B101=57, B106=8, B110=1, B324=1, B403=1 and TEST002=1.
Security deductions were LOW B101/B106/B110/B403 (5 each) and HIGH B324 (30);
TEST002 deducted zero. Overall is `(200 + 100 + 150 + 100 + 100) / 8 = 81.25`.
These are static patterns, including test assertions/mock credentials; the HIGH
cryptographic primitive observation is not proof of a vulnerability. TEST002
observes no directly visible conventional declaration in its candidate file,
not absence of a functioning test suite. No external engineering claim is made.

Only supported public HTTPS acquisition was used, with no credentials, target
dependency installation, target configuration loading or target/workflow execution.
Bandit operated on detached owned material after clone removal. External code and
reports were not copied into committed files. Future default-branch scans can
differ; this is manual evidence, never a permanent live CI golden.

## Shipped-rule coverage audit

"Negative" means the rule did not appear in the complete clean scenario; dedicated
tests establish finer matching/absence cases rather than inferring universal quality.

| Rule | Clean negative | Poor positive | Other positive / existing dedicated coverage |
| --- | --- | --- | --- |
| RH001 | Yes | Yes | test_hygiene.py / test_hygiene_pipeline.py |
| RH002 | Yes | Not materialized on Windows | Dedicated ASCII collision domain/pipeline fixtures; no case-insensitive filesystem assumption |
| PY001 | Yes | Yes | test_python_static.py / test_python_pipeline.py |
| PY002 | Yes | Yes | Same; stub exception cases retained |
| TEST001 | Yes | Yes | test_testing_static.py / test_testing_pipeline.py |
| TEST002 | Yes | No | Public example and dedicated declaration/filename tests |
| CI001 | Yes | No | test_ci_static.py / test_workflow_pipeline.py absence cases |
| CI002 | Yes | Yes | Dedicated action/reusable-reference fixtures |
| CI003 | Yes | Yes | Dedicated workflow/job permission fixtures |
| Bandit normalization | Yes | B105/B110 | Real tool here; test_security.py / test_security_pipeline.py schema, severity, failure and lifecycle cases |

## Claims, security review and release boundaries

README now describes implemented capability rather than promising documentation
analysis or target vulnerability auditing in an imminent v1. It names unassessed
Documentation/Maintainability, absent dependency auditing, private acquisition,
other-language code analysis, target execution/coverage and comprehensive Actions
validation. Development version, license caution and limited heuristic score
meaning remain explicit. Target non-execution is unconditional product behavior.

No production defect was demonstrated and no production source changed. The
existing isolated Git, verified-read, detached external-tool, explicit-config,
non-constructing YAML, escaped-report, no-overwrite publication, redaction and
failure-isolation boundaries were re-reviewed against their regression tests.
No defaults, policy, analyzer membership, dependencies or resource ceilings changed.

Remaining blockers: commit/publication and the full Phase 13 hosted matrix;
owner-selected license; Phase 14 release-hardening review and clean-install checks.
No license, version promotion, tag, release, package publication, repository
visibility change, plugin, language or AI feature was introduced. Phase 14 remains
unstarted. Existing grammar/budget, non-atomic read, generic Bandit messaging,
limited CI structure and reduced-scope score limitations still apply.

## Hosted closure

The blockers above record the pre-publication state. Phase 13 was committed as
`b495e84c4bc042b2f9eca291f93d4d180fb2ec2d`, and all Windows/Ubuntu Python 3.13/3.14
jobs passed in [Quality run 37512872450](https://github.com/asadabbas717/RepoLens/actions/runs/37512872450).
Phase 13 is closed. Owner decisions and final [release hardening](release-readiness.md)
remain separate from this dogfooding evidence.
