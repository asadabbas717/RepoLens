# Final release readiness

This document records the Phase 14 pre-publication audit of development version
`0.1.0.dev0`. The technical commit's exact hosted result must be recorded in the
completion report after publication; a commit cannot embed its own SHA. Phase 14
subsequently passed all four jobs for `be672b29ac79ff0c37d92ffa83615674cef3769f` in
[Quality run 37515155025](https://github.com/asadabbas717/RepoLens/actions/runs/37515155025).
The earlier evidence predates the first software release. Status vocabulary:
PASS, BLOCKED, OWNER ACTION, OWNER AUTHORIZED.

**PUBLIC SOURCE REPOSITORY — COMPLETE.** RepoLens is public on GitHub, Apache-2.0
is active and engineering roadmap 0–14 is complete. **FIRST SOFTWARE RELEASE —
0.1.0 APPROVED.** Package/runtime version is now 0.1.0. Tag v0.1.0 and normal public
GitHub Release "RepoLens 0.1.0" are authorized only after the exact release commit's
four hosted jobs pass. GitHub Release creation remains pending until performed;
the completion report records its public URL and verified state. PyPI/registry
publication is not performed or authorized. Older pre-release results below retain
their original versions/dates for chronology.

RepoLens is licensed under [Apache License 2.0](../LICENSE). The canonical text and
SPDX package metadata resolve the former owner-license blocker. Historical audit
paragraphs below record the state and evidence before this licensing transition.

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
| Exact Phase 14 hosted matrix | PASS: `be672b2`, Quality 37515155025, all four jobs |
| Owner-selected license | PASS: owner selected Apache-2.0; canonical root LICENSE and PEP 639 metadata |
| Release version | PASS: owner approved 0.1.0; package/runtime/lock updated consistently |
| Repository visibility / contributions | PASS: asadabbas717/RepoLens is public, default main; Apache-2.0 contributions; licensed public baseline bb3c0c0 |
| Tag / GitHub Release | OWNER AUTHORIZED: v0.1.0 / RepoLens 0.1.0; pending exact release-SHA CI and publication |
| Registry publication | OWNER ACTION: none; package name/registry availability and publication identity remain decisions |

## Preserved contracts and metadata

Package name, Python >=3.13 baseline, setuptools backend,
src package discovery, console entry `repolens = repolens.cli:main` and py.typed
remain appropriate. Existing installed metadata tests verify runtime requirements
and version consistency. Minimal metadata is intentional: there is no authoritative
author/contact/separate docs/registry identity to add. Public Repository and Issues
URLs now point to the verified GitHub project; no author, email, docs or PyPI URL
was invented. The now-authoritative license
uses `license = "Apache-2.0"` and `license-files = ["LICENSE"]`; no deprecated
table/classifier, attribution identity or repository URL was invented.

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

## Historical owner-authorized publication sequence

The sequence below records the plan before the owner changed visibility. The
completed transition and independent access verification follow in the next section.

After the licensed commit's local checks and full exact-SHA CI pass, rerun the
bounded secret/personal-data/history exposure audit. The authorized action is to
change only asadabbas717/RepoLens visibility from private to public, then verify
main, licensed HEAD, LICENSE/README and anonymous access. If no authenticated
admin-capable tool is available, stop at the green licensed commit and ask the
owner to use Settings → General → Danger Zone → Change repository visibility.
Do not bypass authentication/permissions or infer visibility from authorization.

The official LICENSE bytes were retrieved twice from
[Apache's canonical text](https://www.apache.org/licenses/LICENSE-2.0.txt), with
identical 11,358-byte content and SHA-256
`cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`.
No custom NOTICE is required by any identified attribution, so none was added.
No mass source headers or custom copyright owner/conditions were inserted.

First release version, tags, GitHub Release, package-registry publication and
future release automation still require separate explicit decisions. Rebuild and
reverify artifacts for an approved release version; 0.1.0.dev0 stays unchanged.

## Licensing transition verification (2026-10-07)

The new licensing metadata and actual artifact contracts passed on Windows
CPython 3.13.15 and 3.14.7: each collected 1,214 tests, with 1,213 passed and the
existing real-symlink privilege case skipped. Combined statement/branch coverage
was 99.62% / 99.51%. The small 3.14 coverage variation includes an unchanged
external-process polling path, not a changed security control. Ruff format/lint,
strict mypy (89 source/test files), Bandit and pip-audit passed. The audit found
no known vulnerabilities and skipped only unpublished RepoLens. Thresholds,
runtime dependencies and lock entries are unchanged.

The wheel has 54 intended package/metadata entries; its dist-info/licenses/LICENSE
matches root LICENSE byte-for-byte. METADATA and sdist PKG-INFO expose
License-Expression: Apache-2.0; wheel metadata also declares License-File: LICENSE.
The 68-member sdist includes root LICENSE and required build/source files. No Git,
environment, cache, coverage or dogfood-report artifacts were admitted. A clean
extracted-sdist rebuild produced identical wheel entry payloads.

A fresh environment and working directory outside the checkout verified isolated
site-packages imports, installed license/version metadata, --version/--help/scan
--help, and only pip/PyYAML/RepoLens in the base environment. Bandit-absent Python
scans remained UNSUPPORTED/incomplete/exit 1; non-Python remained available/exit 0.
Adding supported Bandit 1.9.4 completed the unchanged clean 100.00, poor 92.50 and
configured poor 96.25 outcomes. All formats and whole-byte JSON repeats passed;
no target dependency was installed and no execution marker appeared.

The pre-commit bounded history audit examined 247 reachable blobs and found only
the seven previously reviewed fake credential-URL fixtures; no generated/private
artifact paths were found. Current-file review found no unintended home paths,
personal contact/account data or real credential. Ordinary Git authorship remains.
This is heuristic review, not an exhaustive guarantee. A final exposure audit
still follows the licensing commit's green hosted matrix.

At licensing-commit preparation, visibility was not yet marked PASS: GitHub CLI
was unavailable and the connected tool provided read access without admin mutation.
The corresponding completion report therefore stated
LICENSED COMMIT READY / CI GREEN / MANUAL VISIBILITY CHANGE REQUIRED and provided
the supported GitHub settings path. The owner subsequently performed the change;
no permission workaround was used.

## Public-source transition closure (2026-10-07)

The owner changed asadabbas717/RepoLens visibility to public. Licensed public HEAD
at the transition was `bb3c0c051395c89ac288f61c6e8171207400323c`; default branch
remains main. All four jobs passed for that exact SHA in
[Quality run 37528410790](https://github.com/asadabbas717/RepoLens/actions/runs/37528410790).
Fresh anonymous REST access confirms public visibility and Apache-2.0 detection;
credential-isolated HTTPS Git ls-remote returned that HEAD without a credential
helper, prompting or ambient Git credentials. Public raw LICENSE is byte-identical
to the canonical root file. This is public source publication, not a tagged/package
release. The synchronization commit may advance main within this licensed lineage.

No current-state exposure issue was identified; prior bounded history review
remains qualified heuristic evidence with only known inert credential fixtures.
No history rewriting, contribution bureaucracy, new feature or compatibility
change was introduced. Optional repository description/topics remain manual
polish because admin mutation tooling is unavailable; they are not release blockers.

The 0.1.0 candidate has no identified correctness, security, installation, licensing
or packaging blocker. Final candidate readiness requires the synchronization
commit's own full local gates and exact hosted four-job matrix; the completion
report records that final result. Known disclosed scope/resource limits are not
new technical blockers. No version promotion, tag, GitHub Release or registry
publication is performed by this pass.

Synchronization local verification passed 1,213 cases with one existing skip on
each Windows Python 3.13.15/3.14.7 environment (99.62% / 99.51% coverage). Ruff,
strict mypy, Bandit, development dependency audit and builds passed; both artifacts
expose the verified public URLs and canonical license. Fresh external wheel scans
retain clean 100.00, poor 92.50, configured poor 96.25 and reduced non-Python 100.00;
missing applicable Bandit still withholds the score. Reports remain deterministic.
No current secret/personal/artifact exposure issue or technical defect was identified.
Description/topics can be set manually via GitHub's About edit control; recommended
description: "Static, evidence-based repository engineering-quality analysis for
Python projects." Topics: python, static-analysis, code-quality, security,
developer-tools, github-actions. No metadata mutation was performed by this pass.

## First GitHub release authorization (2026-10-07)

The public-state synchronization commit
`ce185bd8d1b3f3ed516b4f625adb737507456fbc` passed all four jobs in
[Quality run 37532612417](https://github.com/asadabbas717/RepoLens/actions/runs/37532612417).
The owner subsequently approved version 0.1.0, annotated tag v0.1.0 and a normal
public GitHub Release. Earlier statements that version/tag/release were unauthorized
or unperformed record those earlier audits; this authorization supersedes them.

Release order is unchanged: local gates, reviewed version commit, normal main push,
exact-SHA green four-job matrix, annotated tag at that SHA, tag push/independent
target verification, then GitHub Release creation and anonymous verification.
A tag/release collision must stop publication; existing tags are never overwritten.
No release automation or registry credentials are added. Source tag and GitHub
source archives suffice; no manually attached wheel/sdist assets are planned.
Policy, JSON/config schemas, analyzer plan and exit codes are unchanged.

The release-local suites each passed 1,213 tests with one existing skip on Python
3.13.15/3.14.7; coverage was 99.62% / 99.58%. Ruff, strict mypy, Bandit, dependency
audit and fresh builds passed. Actual 0.1.0 wheel/sdist metadata/license/runtime
contracts and external installation were verified. The self-scan remains 88.75
with unchanged deducted rules; extra accepted test observations since Phase 14
are explained in [development verification](development.md). Tag and GitHub Release
must still wait for the exact release commit's hosted matrix; the final completion
report supplies immutable commit/run/tag-target/release evidence.
