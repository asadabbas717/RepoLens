# Milestones

Each milestone requires implementation, meaningful tests, strict typing,
format/lint, coverage, security review, useful docs, and a reviewed working tree.
Keep changes small enough to review and do not declare unavailable gates passed.

0. Foundation: package, lock, quality tools, CI, scope and architecture decisions.
1. Domain: immutable findings/evidence, analyzer contract/results, report and
   documented deterministic scoring with failure/applicability semantics.
2. Acquisition: local Git validation, safe GitHub URL parsing/cloning,
   metadata, ignore behavior, bounded traversal and cleanup integration tests.
3. Orchestration: implemented explicit immutable plans, sequential execution,
   result ownership, failure isolation and status-preserving outcomes.
4. Hygiene: implemented bounded path snapshots, two conservative catalogued
   observations and inert acquired fixtures.
5. Python: implemented bounded source snapshots and two structural AST signals;
   mature-tool target adapters are deliberately deferred.
6. Testing signals: implemented conservative filename/AST advisories; configuration
   interpretation deferred, no claimed executed coverage.
7. Security/dependencies: implemented detached optional Bandit and bounded direct
   declarations; vulnerability auditing deferred for missing structured severity.
8. CI/CD: implemented bounded non-constructing GitHub Actions YAML and three
   static observations; runtime inference remains deliberately unavailable.
9. Scoring calibration: implemented explicit python-static-v1 values, documented
   neutral reference fixtures, sensitivity and exact policy regression tests;
   full hosted matrix verified after publication.
10. CLI: implemented argparse scan/help/version, installed entry point, one-inventory
    detached composition, fixed product plan and exact score gate with exits 0/1/2/3;
    full hosted matrix verified after publication.
11. Reporting: implemented full deterministic console, JSON schema 1, escaped
    standalone HTML and no-overwrite output publication; hosted verification
    full hosted matrix verified after publication.
12. Configuration: implemented explicit bounded schema-1 TOML, literal exclusions,
    exact rule controls and score/severity gates with transparent applied metadata;
    full hosted matrix verified for `faca921` in Quality run 37509070101.
13. Dogfooding: validated self-scan, clean/poor/non-Python fixtures and public example;
    full hosted matrix verified for `b495e84` in Quality run 37512872450.
14. Release: all gates, audit, clean install, smoke test, docs and owner-selected license.

Release blockers include license selection and any known critical security issue.
Do not create placeholder analyzers or prematurely label a release 1.0.


Phases 0–2 are complete, including the full hosted matrix for Phase 2 commit
`b91b9d0` ([Quality run 37384103705](https://github.com/asadabbas717/RepoLens/actions/runs/37384103705)).
Phase 3 adds application machinery; analyzers remain explicitly registered. Phase 4 introduces the first repository hygiene rules, their typed catalog and
inert controlled fixtures using a bounded path-only domain snapshot. Phase 5
adds bounded decoded-source data and bare-except/wildcard-import observations,
with reviewed read/encoding/grammar limits. Phase 6 adds static testing
structure advisories without running target tests or claiming executed coverage.
Phase 7 adds reviewed optional detached Bandit and bounded root dependency
declarations; pip-audit target execution remains deferred with explicit unsupported
outcomes. Phase 8 adds bounded GitHub Actions data and conservative static observations.
Phase 8 hosted verification passed all four jobs for `8fcb449` in
[Quality run 37464126457](https://github.com/asadabbas717/RepoLens/actions/runs/37464126457).
Phase 9 adds a five-category heuristic product policy without changing scoring
mechanics or analyzer severities. Documentation/maintainability and dependency
vulnerability auditing remain unassessed/unavailable as documented. Phase 9 hosted
verification passed all four jobs for `2fabe8851c9b535bad44c90e9071fef975298f94` in
[Quality run 37480478013](https://github.com/asadabbas717/RepoLens/actions/runs/37480478013).
Phase 10 adds the first operational command and its full matrix passed for
`4daa1b230b31a616279f00e346d6168c939a649c` in
[Quality run 37484518174](https://github.com/asadabbas717/RepoLens/actions/runs/37484518174).
Phase 11 projects one report into three formats without changing scoring or
analysis; its four hosted jobs passed for `e8f412a635559012ee32df2479966780b9bf6825`
in [Quality run 37501851987](https://github.com/asadabbas717/RepoLens/actions/runs/37501851987).
Phase 12 adds explicit user configuration without implicit target trust or policy
mutation; all four hosted jobs passed in
[Quality run 37509070101](https://github.com/asadabbas717/RepoLens/actions/runs/37509070101).
Phase 13 adds owned inert fixture validation and manual product evidence, documented
in [dogfooding](dogfooding.md). All four hosted jobs passed for
`b495e84c4bc042b2f9eca291f93d4d180fb2ec2d` in
[Quality run 37512872450](https://github.com/asadabbas717/RepoLens/actions/runs/37512872450).
Phase 14 stabilizes and audits the existing product; see
[release readiness](release-readiness.md). Public release still requires explicit
owner licensing/version/visibility/publication decisions.
