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
4. Hygiene: first reliable repository rules with catalog and inert fixtures.
5. Python: incremental AST checks and justified mature-tool adapters.
6. Testing signals: static test presence/configuration, no claimed executed coverage.
7. Security/dependencies: safe adapters, missing tools and normalized results.
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
Phase 3 adds application machinery only; no concrete analyzers are registered by
default. Phase 4 will introduce the first repository hygiene rules, their catalog
and inert controlled fixtures, with any required safe repository-data seam
reviewed before concrete implementation.
