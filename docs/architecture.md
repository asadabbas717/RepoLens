# Architecture and product contract

RepoLens is a modular Python application, initially a CLI/static-analysis tool.
Only the package root exists during Phase 0; create responsibility-specific
directories when real implementations arrive.

| Boundary | Responsibility | Dependencies |
| --- | --- | --- |
| domain | Immutable typed findings, evidence, severity, results, scores | Standard library only |
| application | Deterministic analyzer orchestration and scan use cases | Domain and explicit adapter contracts |
| analyzers | Concrete static checks producing domain findings | Domain and analysis context |
| infrastructure | Filesystem, Git acquisition, external-tool adapters | Domain/application contracts |
| reporting | Console/JSON/HTML rendering of one report | Domain; no independent scoring |
| cli | Argument validation, composition, outputs and exit codes | Application, infrastructure, reporting |

No domain dependency on CLI libraries, subprocess, filesystem traversal, or
external-tool models. Analyzer contracts are a justified extensibility boundary;
avoid interfaces for ordinary internal functions.

## Safety requirements

Never execute target code by default: no import, install, pytest, build, hooks,
or shell scripts. Treat filenames, content, URLs, and tool output as untrusted.
Validate exact public GitHub HTTPS repository URLs before acquisition. Use
argument arrays without a shell, timeouts, controlled Git configuration, and
temporary workspaces with guaranteed cleanup. Bound traversal, file size, clone
time, and tool output; do not follow symlinks outside the repository.

Render HTML with escaping. Findings must not copy secret values. Diagnostic
logging must redact credentials. External analyzer adapters must be reviewed
for configuration/plugin behavior before use against hostile input. In
particular dependency auditing must not trigger target package installation.

## Evidence and scoring contract (to implement in Phase 1)

Findings include stable rule IDs, category, impact severity, explanation,
source analyzer, remediation, and file/line evidence where applicable.
Analysis results distinguish completed, skipped, unsupported, and failed.
Failures never imply passed checks or a perfect score. Scoring must document
penalties, caps, weights, applicability and uncertainty before implementation.
No score or coverage percentage is invented in this foundation.

## Main engineering risks

- Static heuristics can mislead: document what each rule actually proves.
- Missing tooling can inflate scores: represent availability separately.
- Large/malicious repositories can exhaust resources: impose explicit limits.
- Cross-platform paths and cleanup can differ: test Windows and Linux fixtures.
- Report fields can become API commitments: version JSON and test serialization.
- Dependency updates can break reproducibility: commit uv.lock and review updates.

There is no runtime dependency now. Typer/Rich, a safe YAML parser, and Jinja2
remain candidates, not committed dependencies. Add each only with a concrete
requirement and maintenance/security review.
