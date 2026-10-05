# ADR 0001: Static modular application and reproducible foundation

Status: Accepted (2026-10-05)

## Context

RepoLens must assess untrusted repositories with defensible evidence. It starts
on Windows with Python 3.13 available and must remain inexpensive and portable.
An oversized skeleton would obscure incremental learning and review.

## Decision

Use a modular Python application with a src layout and standard-library domain.
Set Python >=3.13: a supported stable baseline with an established ecosystem,
matching the local interpreter. Reference: https://devguide.python.org/versions/.
CI covers Python 3.13/3.14 on Windows and Linux. Later versions require CI
verification before compatibility claims.

Default to static analysis, typed findings and separate report rendering. Never
execute target repository code implicitly. Add responsibility directories only
as meaningful implementations arrive.

Use setuptools packaging, uv.lock for development/build reproducibility,
pytest/coverage, Ruff, strict mypy, Bandit and pip-audit. No runtime dependencies
or CLI framework until implementation requires them. Keep version 0.1.0.dev0.

## Consequences

Python 3.12 and earlier are excluded. Static analysis cannot prove runtime
correctness; reports must explain uncertainty. Tool/bootstrap and dependency
updates require review. PyPI name availability and license remain release
decisions; this foundation does not publish anything.

## Alternatives considered

Python 3.14 minimum: newer but unnecessarily excludes the available environment.
Python 3.12 minimum: wider support but not needed for the initial scope.
Framework-heavy architecture: adds deployment/dependency cost without a requirement.
Global pip tools: easy initially but not reproducible across environments.
Executing tests in scanned repositories: unsafe without a separately designed,
explicit opt-in isolation model, deferred beyond v1.
