# Development and quality gates

Use Python 3.13+ and Git. Commands below are Git Bash compatible on Windows.
uv manages the project environment and committed cross-platform lock file.
Quality tools run from the locked project environment. Install pinned uv in a
separate bootstrap environment; uv creates and manages `.venv` itself.

```bash
python --version
git --version
python -m venv .venv-bootstrap
source .venv-bootstrap/Scripts/activate
python -m pip install uv==0.12.23
uv sync --locked --group dev
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest --cov --cov-report=term-missing
uv run --locked bandit -r src -ll
uv run --locked pip-audit
uv run --locked python -m build --no-isolation
git diff --check
git status --short
```

pytest runs once with coverage rather than duplicating the same suite. Coverage
must be at least 90%, with near-complete behavioral coverage for future scoring.
Foundation tests validate installed metadata and the import contract; their
coverage says nothing about future analysis behavior. No target code is tested
by these commands: they test RepoLens itself.

Ruff owns formatting/linting; mypy checks production and tests strictly.
Bandit fails on medium/high findings; low findings still need review.
pip-audit requires network access and audits the development environment,
not a target repository. An unavailable advisory service blocks that gate and
must be reported. Builds must succeed and clean wheel installation must work.

## Dependencies and rationale

| Dependency | Purpose |
| --- | --- |
| setuptools | Standard src-layout build backend and editable installs |
| pytest | Behavioral test runner and reusable fixtures |
| pytest-cov | Branch coverage and enforced 90% gate |
| Ruff | One fast formatter/linter without duplicate tools |
| mypy | Strict static typing |
| Bandit | Static security review of RepoLens code |
| pip-audit | Known dependency vulnerability checks |
| build | Verify wheel and source distribution construction |
| uv (bootstrap tool) | Lock resolution and reproducible environment synchronization |

Runtime dependencies are empty. Lock changes deliberately with `uv lock`, then
run every gate. CI uses locked development/build tools and `--no-isolation`
for reproducible package builds, as do the local gates above. Review direct and
transitive dependency changes.

uv is bootstrap tooling, not a project development dependency. Keep version
`0.12.23` explicitly pinned in setup instructions and CI. Installing it inside
the environment it synchronizes is unnecessary and risks its removal during
exact synchronization. See [uv sync semantics](https://docs.astral.sh/uv/concepts/projects/sync/).
The bootstrap environment stays separate from `.venv`; activate it again in a
new Git Bash session before running the commands above. CI installs pinned uv
into the runner Python environment, separate from the project environment.

## GitHub Actions pin maintenance

[Checkout v4.3.1](https://github.com/actions/checkout/releases/tag/v4.3.1) and
[setup-python v5.6.0](https://github.com/actions/setup-python/releases/tag/v5.6.0)
use full commit SHAs verified against their official release tags.
Major-version tags provide automatic updates but
can move; immutable SHAs keep the action code fixed until explicitly reviewed.
The trade-off is manual maintenance to receive fixes. When updating, verify the
new release tag and full SHA in the official action repository, review release
changes, update the SHA and version comment together, and rerun hosted CI.
No dependency-update automation is introduced.

## Testing strategy

Unit-test pure domain behavior with real values, especially deterministic
scoring boundaries and failure states. Use small temporary Git repositories
for integration tests, not live GitHub as the primary test source. Mock only
external subprocess/network boundaries; test cleanup, timeout, invalid input,
unsupported languages and missing tools. Add CLI exit-code and report-schema
tests when those features exist. Keep hostile-content fixtures inert.

## Git discipline

The initial branch is main. No commit, remote, or push is created automatically.
Line endings are enforced by .gitattributes. Set your own identity; do not use
an invented author. Review diffs before each focused conventional commit.

```bash
git config --local user.name "Your Name"
git config --local user.email "your-email@example.com"
git config --local core.autocrlf false
git diff
git status
# After reviewing the foundation and passing gates:
git add .
git commit -m "chore: establish RepoLens engineering foundation"
```

Never rewrite history or force-push as part of routine development. Defer
pre-commit hooks until tooling has stabilized; CI is the enforced gate now.

## Foundation verification (2026-10-05)

Verified locally on Windows with Python 3.13.15: locked synchronization,
Ruff formatting/lint, strict mypy, two installed-package tests, 100% coverage
of the one executable foundation statement, Bandit (no findings), source/wheel
build using locked tools, and clean wheel installation/import. Dependency audit
found no known vulnerabilities; the unpublished RepoLens distribution was
skipped because it is not listed on PyPI. Audit cache warnings did not prevent
completion. This is not a claim about future analyzers or runtime safety.

The original foundation was committed and pushed as `e705586` on main.
[Quality run 37354375153](https://github.com/asadabbas717/RepoLens/actions/runs/37354375153)
completed successfully for that commit. Its job and step results verify all
configured gates (sync, format, lint, typing, coverage tests, Bandit, audit and
build) across Ubuntu/Python 3.13, Ubuntu/Python 3.14, Windows/Python 3.13 and
Windows/Python 3.14. These are hosted results, not additional local runs.
They establish foundation compatibility only, not future analyzer correctness.

[Hardening Quality run 37355931792](https://github.com/asadabbas717/RepoLens/actions/runs/37355931792)
subsequently passed all four matrix jobs for commit `6d51d51`, verifying the
changed lock and immutable action pins. These prior runs do not verify Phase 1;
its hosted verification is recorded separately below.
The hardening pass was verified locally on Windows/Python 3.13.15 with all
the gates above, plus clean wheel installation/import. Two tests passed with
100% foundation coverage; Bandit found no issues and dependency auditing found
no known vulnerabilities, again skipping only the unpublished RepoLens package.
The initial elevated test run encountered cache permissions; rerunning under
the workspace account passed without changing warning or coverage settings.

## Phase 1 local verification (2026-10-05)

On Windows/Python 3.13.15, locked sync, format, lint, strict typing, all 64 unit
tests, Bandit, dependency audit and source/wheel builds passed. Statement and
branch coverage are 100% for the current domain/package code, including scoring.
The wheel was reinstalled into the isolated smoke environment and all domain
modules imported successfully. Git whitespace checks passed and the working
tree was reviewed. No dependencies, lock entries or quality thresholds changed.
The audit found no known vulnerabilities; the unpublished RepoLens package
was not auditable through PyPI. These original local checks predated hosted CI.

## Phase 1 domain-integrity hardening verification (2026-10-05)

Direct score constructors now enforce structural invariants independently of
policy calculation. The 43 added test cases cover invalid direct construction,
valid boundaries, collection immutability and the deliberate severity hierarchy.
All 107 tests passed on Windows/Python 3.13.15 with 100% statement/branch coverage.
Locked sync, formatting, lint, strict typing, Bandit, dependency audit and
source/wheel builds passed. The audit found no known vulnerabilities, skipping
the unpublished RepoLens package. No dependencies or quality gates changed;
no Phase 2 functionality was introduced. The subsequent
[Quality run 37360390526](https://github.com/asadabbas717/RepoLens/actions/runs/37360390526)
passed for commit `6f73243`, establishing hosted Phase 1/hardening verification.

## Phase 2 verification (2026-10-06)

Windows/Python 3.13.15 and Git 2.54.0.windows.1 passed locked synchronization,
formatting, lint, strict typing, coverage tests, the established Bandit gate,
dependency audit and source/wheel builds. Of 178 tests, 177 passed and one real
symlink test was skipped because this Windows account cannot create symlinks.
Separate tests exercise symlink/reparse metadata exclusion without that privilege.
Total statement/branch coverage is 99.86%; domain scoring remains at 100%.
The clean smoke environment successfully installed/imported the acquisition wheel.
The advisory audit found no known vulnerabilities, skipping unpublished RepoLens.

Bandit's expanded scan flags the subprocess import (B404, LOW); this was reviewed
as necessary for the isolated Git boundary, not suppressed. The Popen call has
a targeted B603 suppression with its absolute-executable/argument-array rationale
beside the call. No shell is used. Medium/high security gates are unchanged.
See [acquisition](acquisition.md) for the full security model and limitations.

The local sandbox's shared pytest temporary directory was inaccessible. The
same tests/gates ran using a test-owned workspace location; this changes only
temporary storage, not assertions, warnings or coverage:

```bash
source .venv-bootstrap/Scripts/activate
uv run --locked pytest --basetemp=.pytest_cache/phase2-tmp --cov --cov-report=term-missing
```

That location contains pytest-owned disposable fixtures only; pytest may clear
it on repeat runs. Ordinary CI continues to use its normal temporary directory.
There are no live-network acquisition tests. Public GitHub acquisition uses a
simulated clone seam in tests, not an actual GitHub clone. Phase 2 hosted CI is
pending publication. No runtime dependencies, domain contracts, lock entries,
quality thresholds or CI workflow were changed. No Phase 3 functionality exists.
