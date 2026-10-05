# Milestones

Each milestone requires implementation, meaningful tests, strict typing,
format/lint, coverage, security review, useful docs, and a reviewed working tree.
Keep changes small enough to review and do not declare unavailable gates passed.

0. Foundation: package, lock, quality tools, CI, scope and architecture decisions.
1. Domain: immutable findings/evidence, analyzer contract/results, report and
   documented deterministic scoring with failure/applicability semantics.
2. Acquisition: local Git validation, safe GitHub URL parsing/cloning,
   metadata, ignore behavior, bounded traversal and cleanup integration tests.
3. Orchestration: registry, deterministic lifecycle, failure isolation and statuses.
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
