# RepoLens

RepoLens is a Python repository engineering-quality analyzer under development.
It aims to produce deterministic findings backed by file and line evidence,
with transparent scoring and recommendations.

## Current status

Phases 0 and 1 provide packaging, development tooling, tests, CI, immutable
domain models and explicit-policy scoring. No scanning command or concrete
analyzer is implemented yet. The development
version is `0.1.0.dev0`; this is not a released product.

## Planned v1 scope

- Local Git repositories and public HTTPS GitHub repositories.
- Python-specific static analysis and language-independent repository checks.
- Hygiene, documentation, testing signals, security, dependencies, and GitHub Actions.
- Evidence-based category scores that distinguish failed, skipped, and unavailable checks.
- Console, versioned JSON, and standalone HTML reports from one typed report model.
- Validated TOML configuration and severity-based CI quality gates.

Private repositories, target-code execution, other language-specific analyzers,
AI services, web servers, and databases are outside v1.

## Development setup (Git Bash on Windows)

Python 3.13+ and Git are required. Use the latest security patch of your Python
minor version. Install uv once in a bootstrap environment:

```bash
python -m venv .venv-bootstrap
source .venv-bootstrap/Scripts/activate
python -m pip install uv==0.12.23
uv sync --locked --group dev
uv run --locked pytest --cov --cov-report=term-missing
```

See [development](docs/development.md) for all gates and Git recommendations,
[architecture](docs/architecture.md) for boundaries and safety,
and [roadmap](docs/roadmap.md) for milestones.
See [scoring](docs/scoring.md) for outcome states, scope, arithmetic and limitations.

## Safety and limitations

RepoLens will analyze potentially hostile input statically. It will not install
target dependencies, import target modules, run tests, or execute repository
scripts by default. Detected tests are not executed coverage. Static evidence
cannot establish runtime correctness or prove a repository is secure.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
An open-source license has not yet been selected by the owner. Do not publish
a release or assume redistribution rights until that decision is recorded.
