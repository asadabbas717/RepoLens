# RepoLens

RepoLens statically assesses Python Git repositories and language-independent
repository hygiene and GitHub Actions signals. It produces deterministic findings
with relative file/line evidence, recommendations and transparent score deductions.
The development build is `0.1.0.dev0`; it is not a published release.

## Current status

The implemented CLI/configuration/reporting product passed Phase 13 dogfooding and
all four hosted Windows/Linux Python 3.13/3.14 jobs through Phase 14 commit
`be672b2`. Engineering roadmap 0–14 is complete; see
[readiness](docs/release-readiness.md) and [dogfooding](docs/dogfooding.md).
RepoLens is a public GitHub source repository licensed under Apache-2.0. The
licensed public baseline `bb3c0c0` passed all four hosted jobs. The software remains
development version `0.1.0.dev0`; no formal software/package release has occurred.

## Implemented assessment scope

- Local Git repositories and public HTTPS GitHub repositories.
- Python-specific static analysis and language-independent repository checks.
- Root ignore-policy path and ASCII case-collision observations.
- Python bare-except/wildcard-import observations, conventional testing advisories,
  optional Bandit 1.9.4 security observations and three static GitHub Actions rules.
- Evidence-based category scores that distinguish failed, skipped, and unavailable checks.
- Console, versioned JSON, and standalone HTML reports from one typed report model.
- Validated TOML configuration and severity-based CI quality gates.

Private repositories, target-code execution, other language-specific analyzers,
AI services, web servers, and databases are outside v1.
Documentation and Maintainability analysis and target dependency vulnerability
auditing are not implemented assessment capabilities. Target tests/coverage are
not executed or measured; GitHub Actions checks are not comprehensive validation.
Earlier planned documentation-analysis wording is superseded by this implemented
scope; Phase 14 will not invent missing analyzers to fill categories.

## Development setup (Git Bash on Windows)

Python 3.13+ and Git are required. Use the latest security patch of your Python
minor version. Install uv once in a bootstrap environment:

```bash
python -m venv .venv-bootstrap
source .venv-bootstrap/Scripts/activate
python -m pip install uv==0.12.23
uv sync --locked --group dev
uv run --locked pytest --cov --cov-report=term-missing
uv run --locked repolens --help
uv run --locked repolens --version
```

See [development](docs/development.md) for all gates and Git recommendations,
[architecture](docs/architecture.md) for boundaries and safety,
and [roadmap](docs/roadmap.md) for milestones.
After setup, scan an inert or trusted-to-remain-stable local Git working tree:

```bash
uv run --locked repolens scan "C:/projects/example" --fail-under 85.50
```

Target code is never executed. Normal findings do not fail a complete assessment
without a requested gate; incomplete work always returns exit 1.

Local/public acquisition and report choices after setup:

```bash
uv run --locked repolens scan .
uv run --locked repolens scan . --format json
uv run --locked repolens scan . --format html --output repolens-report.html
uv run --locked repolens scan https://github.com/pallets/itsdangerous --format json
```

HTML requires a new output path; existing files are never overwritten. Incomplete
and gate-failed scans still emit the requested report and return exit 1. JSON
overall values are exact decimal strings or null, with explicit availability.
See [reporting](docs/reporting.md) for schema, safety and output compatibility.
Explicit --config now supports bounded literal exclusions, exact rule disabling
and score/severity gates. Target config is never auto-loaded. CLI gate values
override their corresponding file values; all formats disclose effective settings
with additive optional metadata under JSON schema 1. See
[configuration](docs/configuration.md) for the complete schema and trust model.

```bash
uv run --locked repolens scan "C:/projects/example" --config policy.toml --fail-on-severity high --format json
```
See [scoring](docs/scoring.md) for outcome states, scope, arithmetic and limitations.
The unchanged `repolens-python-static-v1` policy weights code quality/testing/
security/hygiene/CI as 2/1/3/1/1, with INFO/LOW/MEDIUM/HIGH/CRITICAL penalties
0/5/15/30/60. Each rule deducts once at its highest observed severity. Unavailable
planned work blocks a numeric overall score; non-applicable work leaves the
denominator. A score of 100 means no deductive findings in completed supported
scope, not a correctness/security certification. Configuration changes disclosed
scope, so differently configured scores must be interpreted accordingly.
See [acquisition](docs/acquisition.md) for source lifetime, exclusions, Git
isolation and practical safety limitations. The acquisition API is not an OS sandbox.
See [orchestration](docs/orchestration.md) for registration, execution, failure
isolation and explicit-policy report composition.
See [repository data](docs/repository-data.md) for the analyzer-safe snapshot and
[hygiene rules](docs/rules/repository-hygiene.md) for exact signals and limitations.
See [Python source](docs/python-source.md) and [Python rules](docs/rules/python.md)
for source limits, encoding, grammar, lifecycle and evidence semantics.

## Safety and limitations

RepoLens will analyze potentially hostile input statically. It will not install
target dependencies, import target modules, run tests, or execute repository
scripts. Detected tests are not executed coverage. Static evidence
cannot establish runtime correctness or prove a repository is secure.

## Development and contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
See [Unreleased changes](CHANGELOG.md) and the
[owner-action checklist](docs/release-readiness.md). Intentionally submitted
contributions follow the project's Apache-2.0 terms and engineering requirements.

## License

RepoLens is licensed under the Apache License 2.0. See [LICENSE](LICENSE).
Public source publication is separate from version promotion, tags, GitHub Releases
and package-registry publication; none of those software-release actions occurred.
