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
8. CI/CD: safely parse GitHub Actions and state runtime inference limitations.
9. Scoring calibration: documented sample fixtures and regression tests.
10. CLI: help, validation and defined success/gate/input/internal-error exit codes.
11. Reporting: console, versioned JSON and escaped standalone accessible HTML.
12. Configuration: validated TOML, exclusions, rule controls and thresholds.
13. Dogfooding: self-scan plus clean/poor/non-Python fixtures and a public example.
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
outcomes. Phase 8 will analyze GitHub Actions safely; no Phase 8 code is present.
