# Final release readiness

This document records the Phase 14 pre-publication audit of development version
`0.1.0.dev0`. The technical commit's exact hosted result must be recorded in the
completion report after publication; a commit cannot embed its own SHA. No public
release or license grant has occurred. Status vocabulary: PASS, BLOCKED, OWNER ACTION.

**NOT READY for public release — owner decisions remain outstanding.** Code
readiness is separate from the decision to expose or redistribute the project.

Release blocker: owner must select and explicitly approve a license before public release / external redistribution.

## Evidence checklist

| Check | Status / evidence |
| --- | --- |
| Phase 13 hosted CI | PASS: `b495e84c4bc042b2f9eca291f93d4d180fb2ec2d`, [Quality 37512872450](https://github.com/asadabbas717/RepoLens/actions/runs/37512872450), all four jobs |
| Intentional working tree | PASS: only Phase 14 docs/tests; cleanliness must be confirmed after commit |
| Full local test matrix / coverage | PASS: 1,211 passed / one existing privilege skip on Windows 3.13.15 and 3.14.7; 99.62% / 99.58% combined coverage |
| Ruff / strict mypy | PASS: format/lint; strict typing in 88 source/test files |
| Bandit / dependency audit | PASS: zero MEDIUM/HIGH; no known dependency vulnerabilities, unpublished RepoLens skipped |
| Clean build / wheel and sdist inspection | PASS: 53 wheel entries / 67 sdist members; clean extracted-sdist rebuild matches every wheel payload |
| Fresh isolated wheel / CLI smoke | PASS: site-packages import, outside-checkout cwd, version/help/scan-help, no dev tools |
| Controlled scans / optional tool states | PASS: complete clean/poor/non-Python/configured results and genuine absent-Bandit behavior |
| Final self-scan / deterministic reports | PASS: 88.75 available, 907 reviewed observations; controlled complete/incomplete JSON repeats byte-identical |
| Documentation consistency / local links | PASS: 32 Markdown files; local destinations exist; implemented/deferred claims and CLI examples reviewed |
| Repository / history / security audit | PASS: 239 reachable historical blobs reviewed heuristically; fixture flags explained, no real secret/artifact identified; boundaries unchanged |
| Exact Phase 14 hosted matrix | BLOCKED at document creation: requires final commit publication; completion report must name exact SHA/run and all four results |
| Owner-selected license | OWNER ACTION: missing; no LICENSE/SPDX expression invented |
| Release version | OWNER ACTION: retain 0.1.0.dev0 until explicit version approval |
| Repository visibility / contributions | OWNER ACTION: keep private; no external contribution enablement |
| Tag / GitHub Release | OWNER ACTION: none created |
| Registry publication | OWNER ACTION: none; package name/registry availability and publication identity remain decisions |

## Preserved contracts and metadata

Package name, development version, Python >=3.13 baseline, setuptools backend,
src package discovery, console entry `repolens = repolens.cli:main` and py.typed
remain appropriate. Existing installed metadata tests verify runtime requirements
and version consistency. Minimal metadata is intentional: there is no authoritative
license/author/contact/public docs/registry identity to add. No classifiers or URLs
were guessed and no packaging change is justified merely for aesthetics.

The sole runtime dependency remains PyYAML>=6.0.3,<7; the lock selects 6.0.3 with
no additional runtime closure. Bandit 1.9.4 is optional trusted tooling. Development
tools remain outside runtime requirements. uv==0.12.23 is pinned bootstrap tooling,
not a project development dependency. No dependencies or lock entries changed.

JSON schema "1", configuration schema 1, policy `repolens-python-static-v1`, exits
0/1/2/3, fixed five-analyzer plan and target non-execution are unchanged. Existing
golden/compatibility/failure tests remain active; no compatibility version changed.
Unavailable work cannot score clean, non-applicable weights are excluded and
configured scope/rule suppression remain disclosed. Documentation/Maintainability
and target vulnerability auditing are not invented capabilities.

CI retains contents:read, reviewed immutable checkout/setup-python SHA references,
Windows/Ubuntu Python 3.13/3.14, locked sync, format/lint, strict typing, warning/
coverage gates, Bandit, development pip-audit and build. No release/publish jobs,
trusted publishing credentials or unrelated automation were added.

## Security review and publication limits

The final pipeline review covers source classification, isolated Git, canonical
root/clone containment, inventory/link/reparse controls, verified bounded reads,
detached snapshots, Python AST parsing, Bandit owned materialization, static
declarations, non-constructing YAML, explicit configuration, state-preserving rule
selection, scoring, escaping, no-overwrite publication and sanitized CLI failures.
Existing adversarial/resource/cleanup tests provide evidence; no duplicate framework
or security bypass was introduced. The operator must still trust patched Git,
Python and optional tool installations. This is not an OS sandbox or atomic snapshot.

No known correctness or security defect was identified by this review. The shipped
pipeline does not import/run targets, tests, setup/build scripts or workflows;
target configuration is not discovered. Reports omit raw source/tool diagnostics,
HTML escapes text and file output rejects overwrite. Arbitrary producer free text
and user-supplied relative filenames/exclusions are not secret detectors: operators
must not encode secrets there. Existing non-atomic filesystem/process-tree/resource
and partial grammar/CI limits remain explicit, not newly excused defects.

History review is a bounded heuristic review of reachable Git blobs and artifact
paths, not a certified exhaustive secret scan. A real historical credential would
block release and require revocation plus deliberate owner-approved history
remediation. No history rewrite or force-push is authorized or performed.

## Detailed local audit evidence (2026-10-06)

Both local versions collected 1,212 cases. 33 added cases cover the 32 local
Markdown documents and installed py.typed presence; existing installed version,
runtime dependency and entry-point checks remain. Goldens, compatibility,
configuration, acquisition, adversarial input, cleanup and real dogfood regressions
all passed. No threshold, assertion or warning handling was weakened.

Wheel inspection verifies the exact current runtime .py set, py.typed, METADATA,
WHEEL, RECORD and console-script metadata; only package/dist-info entries exist.
The sdist supplies README, pyproject, package sources and typing marker. Neither
contains Git data, environments, caches, coverage, dogfood JSON/HTML, symlink entries
or unexpected large files. The sdist was extracted into a fresh owned build tree,
then rebuilt with locked trusted tooling/no isolation. Every resulting wheel entry
payload agrees with the repository build (ZIP container timestamps are not a
bit-for-bit reproducibility promise). No packaging change was necessary.

The fresh base environment contains exactly pip, PyYAML 6.0.3 and the installed
wheel. Inspection used isolated Python and confirmed the import comes from its
site-packages. CLI runs used a newly owned temporary working directory outside
the checkout, with no target imports/dependency installs. Without Bandit, applicable
Python security is UNSUPPORTED, overall unavailable, exit 1 in all formats;
non-Python remains numeric 100.00 with NOT_APPLICABLE Python analyzers, exit 0.
Adding supported Bandit 1.9.4 and its intentional dependencies completes clean
100.00 and poor 92.50 scans. Configured poor remains 96.25 with score gate exit 1;
CLI score override 0 returns 0. Non-Python remains 100.00 in reduced scope.
Full console/JSON/HTML reports, complete and incomplete repeat bytes, schema/policy
identifiers and absent execution markers were verified.

Final actual working-tree self-scan returned 0, all five analyzers completed,
overall 88.75 and security 70. Other categories remain 100. B101 increased from
897 to 900 because of three new test assertions; B404=4, B603=2 and B108=1 remain.
The extra assertions are accepted test tradeoffs. Import-line shifts also relocate
existing package-test IDs, consistently with documented occurrence identity.
The four deducted rule IDs and 5/5/5/15 security penalties did not change. No
self-score optimization, automatic suppression or default exclusions were added.

Seven high-confidence history-search flags were deliberate `user:secret` credential
URL rejection fixtures in current/historical tests. Their controlled fake purpose
was reviewed; no real credential was found. No generated/environment/credential
artifact path was identified. Current machine-path-like strings are portable
examples or deliberate rejection fixtures, not real owner data. This is bounded
heuristic evidence, not proof that no conceivable secret exists. No third-party
source/report was added and no optional repeat public scan was needed.

## Owner-authorized publication sequence

After final exact-SHA CI succeeds, the owner must choose/approve the license and
then update LICENSE and corresponding metadata deliberately. Decide the release
version and publication destination, review package-name availability/identity,
approve visibility and contribution policy, then explicitly authorize tags/releases
and any registry publication. Rebuild/reverify artifacts for that approved version.
Passing technical checks does not substitute for these decisions.
