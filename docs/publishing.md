# PyPI publication

RepoLens 0.1.1 is a packaging compatibility patch. The distribution is
`repolens-engineering`; the import package and command remain `repolens`.
Apache-2.0, runtime dependencies, analysis behavior and report/scoring policies
are unchanged. PyPI upload has not been performed; source and local wheel
installation remain the documented installation methods.

The owner confirmed the pending publisher has been saved with project
`repolens-engineering`, owner `asadabbas717`, repository `RepoLens`, workflow
`publish-pypi.yml`, and environment `pypi`. No registry password or API token is
used. See [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/).

## Deliberate publication boundary

The separate `publish-pypi.yml` workflow runs only through manual dispatch on
`main`, with an existing annotated release tag and its exact expected commit SHA.
It requires a published normal GitHub Release and a successful complete Quality
matrix for that same commit: Ubuntu and Windows, Python 3.13 and 3.14. Tag,
checkout, distribution and runtime versions must agree. Creating a release or
pushing a commit does not publish to PyPI. The existing v0.1.0 tag is immutable.

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

After explicit owner authorization, dispatch the workflow with `v0.1.1` and the
exact four-job-green release SHA, then review and approve the `pypi` deployment.
Verify the actual PyPI artifacts and an independent fresh installation before
advertising registry installation. This preparation task stops before dispatch.
