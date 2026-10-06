# RepoLens

RepoLens is a Python repository engineering-quality analyzer under development.
It aims to produce deterministic findings backed by file and line evidence,
with transparent scoring and recommendations.

## Current status

Phases 0 through 6 provide packaging, development tooling, tests, CI, immutable
domain models, explicit-policy scoring, local/public-GitHub acquisition APIs and
deterministic sequential orchestration and a path-only repository-hygiene analyzer.
It observes root ignore-policy paths and ASCII case collisions using bounded data.
Python source now reaches an AST-only analyzer through a verified bounded text
snapshot, with two conservative code-quality observations targeting 3.13 syntax.
Static testing now observes conventional filenames and AST declarations through
the same detached data, without executing tests or measuring target coverage.
See [testing rules](docs/rules/testing.md) for exact conventions and limitations.
No scanning command is implemented yet. The development version is `0.1.0.dev0`; this is
not a released product.

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
scripts by default. Detected tests are not executed coverage. Static evidence
cannot establish runtime correctness or prove a repository is secure.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
An open-source license has not yet been selected by the owner. Do not publish
a release or assume redistribution rights until that decision is recorded.
