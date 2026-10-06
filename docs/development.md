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

The sole runtime dependency is PyYAML>=6.0.3,<7 for safe workflow parsing.
types-PyYAML is a development-only strict-typing dependency. Lock changes deliberately with `uv lock`, then
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
recorded below for the final hardened Phase 2 commit. No runtime dependencies,
domain contracts, lock entries, quality thresholds or CI workflow were changed. No Phase 3 functionality exists.


## Phase 2 acquisition hardening verification (2026-10-06)

Local Windows/Python 3.13.15 verification passed locked sync, formatting, lint,
strict typing, the established Bandit gate, dependency audit and source/wheel
builds. Of 187 tests, 186 passed and one real symlink test was skipped for Windows
privileges. Total statement/branch coverage is 99.87%; statements, Git execution,
traversal and domain scoring remain at 100%. The same documented test-owned
basetemp was used without changing assertions or quality thresholds.

Real linked-worktree tests cover both repository-root and nested .git indirection
files without reading their contents. Focused boundary tests cover secret-bearing
control-directory and capture-file allocation/cleanup failures, plus preservation
of existing Git error types. Exact .git entries are excluded regardless of type;
Git-related working-tree filenames remain eligible. Remote workspace allocation
and cleanup already have sanitized errors and retain their existing regression
coverage. Cleanup failure may supersede an earlier error and cannot guarantee
physical removal when the OS refuses it.

The audit found no known vulnerabilities, skipping unpublished RepoLens. Bandit
retains its reviewed low-severity subprocess import finding and existing targeted
Popen suppression; no medium/high findings were reported. No dependencies, domain
contracts, security controls or gates changed. These checks are local; this
hardening pass was subsequently published; final hosted verification is recorded
below. No Phase 3 functionality was introduced by that pass.


## Phase 2 canonical-root correction (2026-10-06)

Hosted Windows/Python 3.13 CI for `dbb975d` exposed three remote-source test
failures caused by comparing an incoming short-path alias with Git's resolved
long-path root. `_metadata` now resolves its input strictly before Git inspection
and containment checks. Remote equality also strictly resolves the exact clone
destination; missing/inaccessible paths produce sanitized errors.

Local checks passed locked sync, format, lint, strict typing, coverage tests,
the existing Bandit gate, dependency audit and source/wheel builds. Of 193 tests,
192 passed and one Windows symlink privilege test skipped. Statement coverage
is 100%; combined statement/branch coverage is 99.87%. Alias-resolution unit
cases cover equivalent roots, subdirectories and unrelated roots without assuming
8.3 support or a runner username. Existing real Git integration tests, simulated
remote success/consumer cleanup and the final unexpected-clone-root regression
remain green. Missing/inaccessible inputs and a disappearing clone destination
have focused sanitized-error tests.

The audit found no known vulnerabilities, skipping unpublished RepoLens. Bandit
retains its reviewed LOW subprocess import finding, with no medium/high findings.
No dependencies, gates, security controls or Phase 3 functionality changed. This
correction was published; final hosted verification is recorded below.


## Phase 2 POSIX capture-test correction (2026-10-06)

The Ubuntu/Python 3.14 job in Quality run 37369946743 failed two capture-resource
regressions: their global fstat mock returned size-only metadata to POSIX
TemporaryDirectory cleanup, which requires inode/device metadata. The mock now
handles only the fake capture descriptor and delegates real descriptors to the
original OS function. Assertions, production code and quality gates are unchanged.
Local locked sync, formatting, lint, typing, tests, Bandit, audit and builds passed:
192 passed, one Windows symlink privilege skip, 99.87% combined coverage. Audit
found no known vulnerabilities, skipping unpublished RepoLens. Hosted verification
of the final refinement is recorded below.


## Phase 2 capture-resource isolation refinement (2026-10-06)

The capture-resource regression now uses real temporary binary files wrapped by
a test-local context manager. It replaces only RepoLens's imported TemporaryFile
factory and injects secret-bearing creation/cleanup errors there. No shared
os.fstat patch remains, including the selective descriptor patch from the prior
correction. Real descriptor size inspection and stdlib directory cleanup remain
independent. Assertions verify sanitized GitFailed outcomes, suppressed raw
exception context, both real streams closing and capture reaching subprocess
execution before cleanup failure. Production code and security controls did not
change.

All established local gates passed on Windows/Python 3.13.15: locked sync,
formatting, lint, strict typing, tests, Bandit, dependency audit and builds.
Of 193 tests, 192 passed and one Windows symlink privilege test skipped; combined
coverage is 99.87%, with 100% statement coverage. Tests used the documented
workspace basetemp override. Bandit retains one reviewed LOW finding and no
medium/high findings. Audit found no known vulnerabilities, skipping unpublished
RepoLens. No Phase 3 code or later functionality was introduced. Hosted CI for
this refinement is recorded below; local checks alone did not close validation.


## Phase 2 hosted closure (2026-10-06)

[Quality run 37384103705](https://github.com/asadabbas717/RepoLens/actions/runs/37384103705)
completed successfully for `b91b9d05e35528c6a651cd3fd9a7f59576f3c87d`.
All four jobs succeeded: Ubuntu/Python 3.13, Ubuntu/Python 3.14,
Windows/Python 3.13 and Windows/Python 3.14. This verifies the final acquisition
hardening, canonical-root correction and capture-test isolation refinement.
Phase 2 is closed. It does not constitute hosted verification of Phase 3 changes.


## Phase 3 local verification (2026-10-06)

Windows/Python 3.13.15 passed locked synchronization, formatting, lint, strict
mypy, all tests, the existing Bandit gate, dependency audit and source/wheel
builds. Of 227 tests, 226 passed and one existing real symlink test skipped for
Windows privileges. The 34 new cases cover registration, all result states,
metadata snapshots, ordering, ordinary exception isolation, cancellation,
result ownership, cross-result conflicts and domain-report/acquisition composition.
Combined statement/branch coverage is 99.88%; statements and the new orchestration
module's branches are 100%. Domain scoring remains at 100%.

The documented workspace basetemp workaround was used with unchanged assertions,
warning handling and coverage gates:

```bash
source .venv-bootstrap/Scripts/activate
uv run --locked pytest --basetemp=.pytest_cache/phase3-tmp --cov --cov-report=term-missing
```

The wheel was installed without dependencies into the isolated smoke environment;
application imports and empty-plan execution passed under isolated Python.
Bandit reported no medium/high findings; the existing reviewed LOW subprocess
import finding and targeted Git Popen suppression remain unchanged. Dependency
auditing found no known vulnerabilities, skipping unpublished RepoLens. Whitespace
checks passed and the working tree was reviewed. Domain and infrastructure code,
protocols, dependencies, lock entries and workflow gates are unchanged. No concrete
analyzers, CLI, rendering, configuration or Phase 4 functionality were added.
Phase 3 was subsequently published; its hosted verification is recorded below.


## Phase 3 hosted verification (2026-10-06)

[Quality run 37386215681](https://github.com/asadabbas717/RepoLens/actions/runs/37386215681)
completed successfully for `28e7ffd9aca9a2106b80237efe79679453856e77`.
All four Ubuntu/Windows and Python 3.13/3.14 jobs succeeded. This establishes
hosted Phase 3 verification, not verification of the new Phase 4 changes.


## Phase 4 local verification (2026-10-06)

Windows/Python 3.13.15 passed locked sync, formatting, lint, strict mypy, tests,
the existing Bandit gate, dependency audit and source/wheel builds. Of 295 tests,
294 passed and one existing real symlink test skipped for Windows privileges.
The 68 new cases cover bounded/normalized immutable inventory, catalog metadata,
positive/negative/near-match hygiene signals, stable occurrence IDs, snapshot
failure/lifetime handling, deterministic ordering and acquired-source composition.
Total statement/branch coverage is 99.89%; statements, domain scoring, hygiene
and the snapshot adapter remain at 100%. Traversal/Git controls and Phase 3
orchestration code are unchanged.

The existing documented test-owned basetemp workaround was used without changing
assertions, warning handling or coverage gates:

```bash
source .venv-bootstrap/Scripts/activate
uv run --locked pytest --basetemp=.pytest_cache/phase4-tmp --cov --cov-report=term-missing
```

The built wheel installed without dependencies in the isolated smoke environment;
hygiene, inventory and application imports and a clean-inventory execution passed
under isolated Python. Bandit retained its existing reviewed LOW subprocess import
finding and targeted Git Popen suppression; no medium/high findings were reported.
The advisory audit found no known vulnerabilities, skipping unpublished RepoLens.
Whitespace checks passed and the working tree was reviewed. No dependency, lock,
CI workflow or quality-gate changes were made. No target contents are read by the
new analyzer and no target code is executed. Tests use inert controlled repositories
and simulated remote copying, not live GitHub acquisition. Scoring policies remain
explicit synthetic fixtures; no product weights or penalties were introduced.
Phase 4 was subsequently published; hosted verification is recorded below. No Python
AST checks, target tool adapters, testing/security/CI analysis, CLI, rendering,
configuration or Phase 5 functionality was added.


## Phase 4 hosted verification (2026-10-06)

[Quality run 37388379703](https://github.com/asadabbas717/RepoLens/actions/runs/37388379703)
completed successfully for `18d23e4c84e505d7c6835535efe9a2c57bfdc609`.
All four Windows/Ubuntu and Python 3.13/3.14 jobs succeeded. This establishes
hosted Phase 4 verification, not verification of Phase 5 changes.


## Phase 5 local verification (2026-10-06)

Locked sync, formatting, lint, strict mypy, the established Bandit gate, dependency
audit and source/wheel builds passed. The full 389-case suite ran on both installed
Windows CPython 3.13.15 and 3.14.7: 388 passed and one existing real symlink test
skipped for account privileges on each interpreter. The 94 new cases cover source
selection/values, raw and decoded budgets, encoding/BOM behavior, path and descriptor
checks, file/type/parent replacement, growth, lifetime, AST rules, fixed grammar
boundaries, occurrence identities and acquired-source/report composition.

Coverage was 99.84% on 3.13 and 99.83% on 3.14, with 100% statement coverage and
100% statement/branch coverage for the new Python source boundary, domain values
and analyzer. Scoring remains fully covered. The same grammar fixtures and golden
finding ID passed on both versions. Local environments are not hosted Linux evidence.

The documented sandbox pytest temporary-storage workaround was retained:

```bash
source .venv-bootstrap/Scripts/activate
uv run --locked pytest --basetemp=.pytest_cache/phase5-tmp --cov --cov-report=term-missing
```

A separate ignored .venv-phase5-py314 environment used the same locked dev group
and the installed CPython 3.14.7 interpreter. A Git Bash equivalent, when Python
3.14 is available, is:

```bash
UV_PROJECT_ENVIRONMENT=.venv-phase5-py314 uv sync --locked --group dev --python 3.14
UV_PROJECT_ENVIRONMENT=.venv-phase5-py314 COVERAGE_FILE=.pytest_cache/phase5-py314.coverage uv run --locked --python 3.14 pytest --basetemp=.pytest_cache/phase5-py314-tmp --cov --cov-report=term-missing
```

Temporary fixtures and separate coverage storage change no assertions, warning
handling or quality thresholds. Target parser warnings are scoped out only at
ast.parse as described in the rules contract, preventing target literals from
escaping as diagnostics; project warning-as-error behavior is unchanged.

The wheel installed without dependencies in the isolated smoke environment;
Python source/domain/infrastructure imports and AST orchestration passed under
isolated Python. Bandit reported no medium/high findings and retains the existing
reviewed LOW subprocess import finding and targeted Git Popen suppression. Audit
found no known vulnerabilities, skipping unpublished RepoLens. Whitespace checks
passed and the working tree was reviewed. No dependencies, locks, CI gates,
scoring arithmetic or orchestration special cases changed. Source data is never
imported/executed and tests use inert owned fixtures without live acquisition.

Phase 5 was subsequently published and verified by the hosted matrix below. No testing-quality, security,
dependency, CI/CD, documentation analysis, CLI, rendering, configuration or
Phase 6 functionality was introduced.


## Phase 5 hosted verification (2026-10-06)

[Quality run 37393028192](https://github.com/asadabbas717/RepoLens/actions/runs/37393028192)
completed successfully for `95d701add94289767c2b3a54aab1baf409448b59`.
All four Windows/Ubuntu Python 3.13/3.14 jobs succeeded. This closes Phase 5;
it does not establish hosted verification of uncommitted Phase 6 changes.


## Phase 6 local verification (2026-10-06)

Locked synchronization, Ruff format/lint, strict mypy, the full test suite,
Bandit, dependency audit and source/wheel builds passed locally. Both installed
Windows CPython 3.13.15 and 3.14.7 ran 447 cases: 446 passed and the existing
real-symlink privilege case skipped. Total statement/branch coverage is 99.85%
on both versions, with 100% for testing_static, shared python_ast and scoring.
The 58 added cases cover discovery/near matches, direct AST shapes, comments and
strings, stubs/custom names, unavailable states, grammar/resource failures,
partial rejection, catalog validation, deterministic golden identities and
owned acquisition/report composition. Inert marker fixtures and forbidden I/O
boundaries prove detached execution; unavailable testing cannot produce a score.

The established sandbox workaround remains unchanged:

```bash
source .venv-bootstrap/Scripts/activate
uv run --locked pytest --basetemp=.pytest_cache/phase6-final --cov --cov-report=term-missing
UV_PROJECT_ENVIRONMENT=.venv-phase5-py314 COVERAGE_FILE=.pytest_cache/phase6-py314.coverage uv run --locked --python 3.14 pytest --basetemp=.pytest_cache/phase6-py314-final --cov --cov-report=term-missing
```

The wheel installed without dependencies in the isolated smoke environment;
static-testing imports and empty-snapshot orchestration passed under isolated
Python. Bandit reported no medium/high findings, retaining the reviewed LOW
subprocess import and targeted Git Popen suppression. Audit found no known
vulnerabilities, skipping unpublished RepoLens. No dependencies, lock, workflow,
quality thresholds, acquisition, domain or orchestration code changed. The shared
pure parser preserves Phase 5 policy. Configuration contents are not interpreted,
no target code runs and target coverage is not measured. Whitespace and scope
review passed. No Phase 7 security/dependency adapters or later work was added.

Phase 6 was subsequently published and verified by the hosted matrix below.


## Phase 6 hosted verification (2026-10-06)

[Quality run 37449614765](https://github.com/asadabbas717/RepoLens/actions/runs/37449614765)
completed successfully for `4b47fcf938bd1d8fe17adfe2a68201e421dddb50`.
All four Windows/Ubuntu Python 3.13/3.14 jobs succeeded. This closes Phase 6;
it does not establish hosted verification of uncommitted Phase 7 changes.


## Phase 7 local verification (2026-10-06)

Locked synchronization, Ruff formatting/lint, strict mypy, the existing Bandit
gate, dependency audit and source/wheel builds passed. Both Windows CPython
3.13.15 and 3.14.7 ran the full 606-case suite: 605 passed, with the existing
real-symlink privilege case skipped. Statement/branch coverage was 99.41% on
3.13 and 99.50% on 3.14. Both new analyzers, the manifest/declaration/observation
values, domain scoring and the factored verified-read primitive are fully covered.
The 159 added cases exercise schema/exit validation, paths, severity/confidence,
deterministic IDs, secrets, optional tools, grammar/resource failures, environment
filtering, Linux loader reconstruction, process deadlines/reaping, both output
caps, temporary-resource failures, origin exclusion, static manifest syntax and
acquired-source/report composition. Existing read regressions retain their
assertions with private seams redirected to the extracted read module.

The established sandbox basetemp workaround and separate coverage storage were
retained without changing assertions, warnings or thresholds:

```bash
source .venv-bootstrap/Scripts/activate
uv run --locked pytest --basetemp=.pytest_cache/phase7-release-check --cov --cov-report=term-missing
UV_PROJECT_ENVIRONMENT=.venv-phase5-py314 COVERAGE_FILE=.pytest_cache/phase7-py314.coverage uv run --locked --python 3.14 pytest --basetemp=.pytest_cache/phase7-py314-release-check --cov --cov-report=term-missing
```

Bandit 1.9.4 and pip-audit 2.10.1 help and installed formatter/CLI code were
inspected locally. A pinned pip-audit detached exact-pin no-pip dry run completed;
it is not advisory audit evidence. The normal tests use simulated vendor output
and one real locked Bandit fixture, with no network dependency. Inert targets
never execute, target configuration cannot suppress the Bandit observation, and
source/environment secrets remain absent from context representations, results,
reports and sanitized errors. The owned temporary-storage exclusion is checked
before allocation and the scan works after its origin disappears.

Bandit reported zero medium/high findings; its two LOW subprocess imports are
reviewed and the two targeted B603 suppressions cover trusted absolute Git/Python
launches with application-built arrays. No blanket suppression or gate change was
introduced. Audit found no known vulnerabilities and skipped unpublished RepoLens.
The wheel installed without dependencies in the isolated smoke environment;
missing optional Bandit produced UNSUPPORTED as designed. No dependency, lock,
workflow, Git runner, orchestration, scoring arithmetic or severity changes were
made. Whitespace and scope review passed. No Phase 8 functionality was added.

Phase 7 was subsequently published and verified by the hosted matrix below. Target vulnerability auditing is intentionally deferred because
native pip-audit advisory JSON lacks structured impact severity. This limitation
is visible as UNSUPPORTED, never a clean security result.


## Phase 7 hosted verification (2026-10-06)

[Quality run 37456714218](https://github.com/asadabbas717/RepoLens/actions/runs/37456714218)
completed successfully for `7401b9de3af198de3dc528815c597a0300a006a1`.
All four Windows/Ubuntu Python 3.13/3.14 jobs succeeded. This closes Phase 7;
it does not establish hosted verification of uncommitted Phase 8 changes.


## Phase 8 local verification (2026-10-06)

Locked synchronization, Ruff formatting/lint, strict mypy, the existing Bandit
gate, dependency audit and source/wheel builds passed. Both Windows CPython
3.13.15 and 3.14.7 ran 754 cases: 753 passed and the existing real-symlink
privilege case skipped. Statement/branch coverage was 99.40% on 3.13 and 99.38%
on 3.14. The CI analyzer, workflow domain values and scoring are fully covered;
YAML projection and workflow snapshot infrastructure retain near-complete coverage.

The 148 added cases cover exact selection and near matches, immutable membership,
byte/count/aggregate limits, complete admission, UTF-8/BOM, lifetime, read/type/link
changes, escape rejection, YAML scalar spelling, anchors/aliases/tags/directives,
duplicates, structural budgets, step/job action forms, self/local/Docker refs,
permissions, expressions, controlled evidence, ordering and inert acquired-source
report composition. No normal test needs network. Existing package metadata
assertions now require exactly the reviewed PyYAML runtime constraint rather than
historical zero dependencies; accidental additional runtime dependencies remain
rejected. Existing quality thresholds, warning handling and assertions were retained.

The established sandbox workaround remains:

```bash
source .venv-bootstrap/Scripts/activate
uv run --locked pytest --basetemp=.pytest_cache/phase8-final --cov --cov-report=term-missing
UV_PROJECT_ENVIRONMENT=.venv-phase5-py314 COVERAGE_FILE=.pytest_cache/phase8-py314.coverage uv run --locked --python 3.14 pytest --basetemp=.pytest_cache/phase8-py314-final --cov --cov-report=term-missing
```

PyYAML 6.0.3 was promoted from development-transitive to direct runtime dependency,
with supported constraint >=6.0.3,<7. Development-only types-PyYAML is locked at
6.0.12.20260906; other resolved versions were unchanged. The audited 49-package
group had no known vulnerabilities; unpublished RepoLens was skipped. Bandit
reported zero medium/high and retains the two reviewed LOW subprocess imports and
existing targeted Git/Python launch suppressions. No security gate was weakened.

The built wheel and pinned PyYAML installed in the isolated smoke environment;
imports, dependency metadata and a real detached CI002 observation passed under
isolated Python. Offline installation initially lacked the PyYAML wheel cache;
that dependency was downloaded separately, then the sandbox-owned RepoLens wheel
installed without index/dependency access. This is RepoLens installation, not any
target build/install/execution. GitHub reference semantics were verified against
current official documentation; tests remain entirely independent of that network.
Whitespace and scope review passed. Acquisition/read/process security, orchestration,
scoring arithmetic and prior analyzer semantics were unchanged. No Phase 9 work
or production scoring policy was added.

Phase 8 was subsequently published and verified by the hosted matrix below.
Some valid GitHub/YAML features are intentionally
unsupported, as documented in workflow-data and CI/CD rules; parsed structure
never proves GitHub acceptance or successful execution.

## Phase 8 hosted verification (2026-10-06)

[Quality run 37464126457](https://github.com/asadabbas717/RepoLens/actions/runs/37464126457)
completed successfully for `8fcb44915533a3a42446f2359adda7504f9d5cc5`.
All four Windows/Ubuntu Python 3.13/3.14 jobs succeeded, confirmed from their
hosted job states. This closes Phase 8 and does not verify Phase 9 changes.

## Phase 9 local verification (2026-10-06)

The explicit versioned python-static-v1 product profile was calibrated with
neutral typed reference results and inert real-analyzer snapshot composition.
The 45 added cases lock its identifier, severity table, category scope/weights,
exact category/overall results, half-up rounding, deduplication, floor behavior,
INFO visibility, applicability and missing/failed/skipped/unsupported work.
Controlled vendor observations retain Bandit severity; missing Bandit and planned
dependency auditing cannot produce numeric security/overall scores. Testing's
INFO-only contribution is documented and tested, not interpreted as effectiveness.

Both local Windows CPython 3.13.15 and 3.14.7 collected 799 cases: 798 passed and
the existing real-symlink privilege case skipped. Combined statement/branch
coverage was 99.41% on 3.13 and 99.38% on 3.14. Domain scoring, reports, product
values and analyzer normalization are 100% covered. No quality threshold changed.
Locked synchronization passed for both environments. Ruff format/check and
strict mypy passed (60 source/test files). Bandit had no medium/high findings;
the existing two reviewed LOW subprocess imports and targeted launch suppressions
remain unchanged. No runtime/development dependencies or lock entries changed.

The dependency-audit gate initially hit the restricted environment's denied
network/cache access; the authorized network retry passed with no known
vulnerabilities, skipping only the unpublished RepoLens distribution. The build
produced source and wheel distributions. The wheel was reinstalled without index
or dependency access in the isolated smoke environment; isolated policy import
and empty-plan score safety passed. These operations install/test RepoLens, never
target repository code. Whitespace and scope review passed.

The existing sandbox temporary-directory workaround was retained:

```bash
source .venv-bootstrap/Scripts/activate
uv run --locked pytest --basetemp=.pytest_cache/phase9-full --cov --cov-report=term-missing
UV_PROJECT_ENVIRONMENT=.venv-phase5-py314 COVERAGE_FILE=.pytest_cache/phase9-py314.coverage uv run --locked --python 3.14 pytest --basetemp=.pytest_cache/phase9-py314 --cov --cov-report=term-missing
```

Production changes are confined to the explicit application-layer policy value.
Domain arithmetic, reports, analyzer severities/lifecycle, orchestration and all
acquisition/read/tool/YAML controls are unchanged. No CLI, rendering, configuration,
new analyzers or Phase 10+ functionality was added. No score was tuned to RepoLens.
The policy is a documented heuristic rather than an empirically validated measure.
Phase 9 was subsequently published and verified by the hosted matrix below.
See [calibration](scoring-calibration.md) for exact reference scores
and the rule requiring a new identifier for changed penalties, weights or scope.

## Phase 9 hosted verification (2026-10-06)

[Quality run 37480478013](https://github.com/asadabbas717/RepoLens/actions/runs/37480478013)
completed successfully for `2fabe8851c9b535bad44c90e9071fef975298f94`.
All four Windows/Ubuntu Python 3.13/3.14 jobs succeeded, confirmed from their
hosted job states. This closes Phase 9; it does not verify Phase 10 changes.

## Phase 10 local verification (2026-10-06)

The installed argparse scan command composes one bounded inventory, detached
Python/workflow data, a fixed five-analyzer plan and PYTHON_STATIC_V1. Acquisition
closes before execution. The standalone Python/workflow builders now share their
private admission and snapshot functions with the combined builder; verified-read,
Git/Bandit controls, analyzer semantics and domain arithmetic are unchanged.
Dependency manifests/auditing are deliberately outside the default plan, disclosed
in help/status and [CLI documentation](cli.md), never removed after execution.

132 added cases cover help/version with no acquisition/tool side effects, exact
default metadata, source classification including native Windows paths, strict
Decimal threshold syntax/bounds/equality, exits 0/1/2/3, unavailable/missing work,
sanitized parser/input/internal errors and cancellation propagation. Combined
snapshot tests verify one traversal, equivalent standalone data contracts, all
admission before reads, count/file/aggregate/traversal limits, decoded expansion,
read/type/reparse/escape/mutation/lease failures and all-or-nothing publication.
Local inert repositories exercise all five analyzers with a controlled scanner.
Simulated remote clones prove canonical acquisition, cleanup on every tested exit
and actual execution after origin disappearance. No test requires live GitHub.

Both local Windows CPython 3.13.15 and 3.14.7 collected 931 cases: 930 passed and
the existing real-symlink privilege case skipped. Combined statement/branch
coverage was 99.40% on 3.13 and 99.46% on 3.14. CLI, combined snapshot builder,
shared Python/workflow builders, scoring and reports have 100% coverage. Existing
warning and coverage thresholds were retained. The minor cross-run coverage
difference is in existing tool/resource branches, not incomplete new CLI coverage.

Locked synchronization passed in both environments. Ruff format/check and strict
mypy passed (65 production/test files). Bandit reported zero medium/high findings;
two reviewed LOW subprocess imports and the existing targeted launch suppressions
are unchanged. The authorized dependency-audit gate found no known vulnerabilities,
skipping only the unpublished RepoLens package. Source and wheel distributions
built successfully with locked tools and no build isolation. No dependency,
resolution or lock entries changed; pyproject adds only the console script.

The wheel reinstalled without index/dependency access into the smoke environment
containing only pip, PyYAML and RepoLens. Its actual console executable passed
--version, --help and scan --help without development tooling or Bandit. An inert
installed Python-repository scan with --fail-under 0 returned the expected exit 1,
python-security UNSUPPORTED, unavailable overall/gate and no target marker.
No target modules, tests, builds or workflows were executed. This is controlled
smoke verification, not self-dogfooding or a public release.

The existing sandbox temporary-directory workaround was retained:

```bash
source .venv-bootstrap/Scripts/activate
uv run --locked pytest --basetemp=.pytest_cache/phase10-full --cov --cov-report=term-missing
UV_PROJECT_ENVIRONMENT=.venv-phase5-py314 COVERAGE_FILE=.pytest_cache/phase10-py314.coverage uv run --locked --python 3.14 pytest --basetemp=.pytest_cache/phase10-py314 --cov --cov-report=term-missing
```

Whitespace and scope review passed. No rich console reporting, JSON/HTML,
configuration, plugin discovery, new analyzers, dogfooding or Phase 11+ work was
added. Local content reads remain non-atomic; stable input and a trusted installed
tool environment are required. Phase 10 remains uncommitted, and its full hosted
Windows/Ubuntu Python 3.13/3.14 matrix is still required after publication.
