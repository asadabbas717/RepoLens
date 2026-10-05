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

The Phase 0 hardening changes require a new hosted run after publication;
the original successful run does not verify the changed lock or action pins.
The hardening pass was verified locally on Windows/Python 3.13.15 with all
the gates above, plus clean wheel installation/import. Two tests passed with
100% foundation coverage; Bandit found no issues and dependency auditing found
no known vulnerabilities, again skipping only the unpublished RepoLens package.
The initial elevated test run encountered cache permissions; rerunning under
the workspace account passed without changing warning or coverage settings.
