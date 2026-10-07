# Changelog

## Unreleased

## 0.1.1 - 2026-10-07

Packaging/publication compatibility patch:

- Distribution name changes to `repolens-engineering`; import package and CLI stay `repolens`.
- No analyzer, scoring, policy, schema or CLI behavior changes; Apache-2.0 is unchanged.
- Manual, protected-environment PyPI Trusted Publishing infrastructure is prepared.
- No registry upload is performed by release preparation; `v0.1.0` remains immutable.

## 0.1.0 - 2026-10-07

First public release on GitHub:

- Safe local Git and public HTTPS GitHub acquisition with bounded detached data.
- Repository hygiene, Python AST, static testing and GitHub Actions observations.
- Optional supported Bandit 1.9.4 scanning of owned detached Python material.
- Immutable findings/results, explicit failure/applicability states and deterministic
  `repolens-python-static-v1` heuristic scoring with per-rule deduction traces.
- Installed CLI, console reports, JSON schema 1 and escaped standalone HTML.
- Explicit configuration schema 1, literal exclusions, exact rule controls and
  score/severity gates preserving unavailable analysis.
- Owned fixture, installed-wheel and manual public-example validation.

Documentation/Maintainability analysis, target dependency vulnerability auditing,
private authentication and other-language code analysis are not implemented.
Target code/tests/builds/workflows are never executed; target coverage is not measured.
Licensed under Apache-2.0 and publicly available as GitHub source. No software
release is published to a package registry. Static findings and scores are not
correctness/security certification. Tag v0.1.0 and GitHub Release RepoLens 0.1.0
are the approved first software-release channel; registry publication is separate.
