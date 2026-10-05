# Development and quality gates

Use Python 3.13+ and Git. Commands below are Git Bash compatible on Windows.
uv manages the project environment and committed cross-platform lock file.
Global tool installations are not used for verification.

```bash
python --version
git --version
python -m venv .venv
source .venv/Scripts/activate
python -m pip install uv==0.12.23
uv sync --locked --group dev
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked mypy
uv run --locked pytest --cov --cov-report=term-missing
uv run --locked bandit -r src -ll
uv run --locked pip-audit
uv run --locked python -m build
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
for reproducible package builds; the default local build also verifies isolated
build-backend resolution. Review direct and transitive dependency changes.

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

Git was initialized on main; no commits, remotes or pushes were made. Hosted
CI has not run, and Python 3.14/Linux results remain unverified locally.
