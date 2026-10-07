# PyPI publication

RepoLens 0.1.1 is a packaging compatibility patch. The distribution is
`repolens-engineering`; the import package and command remain `repolens`.
Apache-2.0, runtime dependencies, analysis behavior and report/scoring policies
are unchanged. Version 0.1.1 is published on
[production PyPI](https://pypi.org/project/repolens-engineering/).

## First production publication (2026-10-07)

| Item | Verified value |
| --- | --- |
| PyPI project / first version | `repolens-engineering` / `0.1.1` |
| Authentication | PyPI Trusted Publishing / GitHub Actions OIDC |
| Repository | `asadabbas717/RepoLens` |
| Workflow | `.github/workflows/publish-pypi.yml` |
| GitHub environment | `pypi` |
| Release tag | `v0.1.1` |
| Exact source | `aede95b6a5810920645eca48a6e845aaab37276a` |
| Successful publication | [Run 37609131316](https://github.com/asadabbas717/RepoLens/actions/runs/37609131316), build and publish passed |

The protected deployment was approved only after the exact-source build passed.
Production [JSON metadata](https://pypi.org/pypi/repolens-engineering/json) verified
name/version, Apache-2.0, Python >=3.13, the sole existing PyYAML runtime requirement,
and Repository/Issues URLs. Both `repolens_engineering-0.1.1-py3-none-any.whl` and
`repolens_engineering-0.1.1.tar.gz` are present. PyPI reports publish attestations
for both files identifying this repository, workflow and environment.

A fresh production-PyPI installation outside the checkout verified import and
installed metadata version 0.1.1, `repolens 0.1.1`, help commands, and controlled
scans with optional Bandit absent and with supported Bandit 1.9.4. Missing
applicable Bandit analysis correctly remained unsupported/incomplete. No retry
was needed. No long-lived PyPI API token is required or used; the publisher obtains
short-lived credentials through OIDC. See
[PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/).

## Deliberate publication boundary

The separate `publish-pypi.yml` workflow runs only through manual dispatch on
`main`, with an existing annotated release tag and its exact expected commit SHA.
It requires a published normal GitHub Release and a successful complete Quality
matrix for that same commit: Ubuntu and Windows, Python 3.13 and 3.14. Tag,
checkout, distribution and runtime versions must agree. Creating a release or
pushing a commit does not publish to PyPI. Existing v0.1.0 and v0.1.1 tags are immutable.

The build job has `contents: read` and `actions: read` (to inspect hosted Quality
results), with no OIDC permission. It checks out the requested tag, checks its
exact SHA before executing project scripts, uses bootstrap uv 0.12.23 and locked
development dependencies, builds wheel/sdist, validates package metadata and
contents, and tests the installed wheel outside the checkout.

The publish job requires approval from `asadabbas717` through the dedicated `pypi`
GitHub environment. Only `main` may deploy and administrator bypass is disabled.
Self-review is allowed so the sole owner can approve their deliberately dispatched run.
It alone has `id-token: write`, alongside `contents: read`. It downloads the exact
build artifact ID, checks both SHA-256 digests, and invokes the official PyPA
publisher with metadata validation and attestations. It does not check out or
execute repository source with OIDC privileges. Every action is pinned to an
immutable full commit SHA with its corresponding release in a comment.
See [GitHub environments](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment).

Future publications require separate explicit owner authorization for the package,
version, existing release tag and exact four-job-green SHA before dispatch on
`main`. Review and approve only the matching green build's `pypi` deployment.
Verify production artifacts and an independent fresh installation afterward.
Version 0.1.1 is already published and must not be overwritten or republished.
If a future upload fails, inspect PyPI for accepted files before considering any
retry; do not retry blindly or weaken the protection rules.
