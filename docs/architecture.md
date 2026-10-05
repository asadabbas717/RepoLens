# Architecture and product contract

RepoLens is a modular Python application, initially a CLI/static-analysis tool.
The package root and pure `domain` package exist after Phase 1; create other
responsibility-specific directories when real implementations arrive.

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

## Evidence and scoring contract (implemented in Phase 1)

Findings include stable rule IDs, category, impact severity, explanation,
source analyzer, remediation, and file/line evidence where applicable.
Analysis results distinguish completed, skipped, unsupported, failed and
explicitly non-applicable. Missing planned results remain unavailable. Failures
never imply passed checks or a perfect score. The [scoring contract](scoring.md)
defines explicit policies, per-rule deductions, caps, weights and uncertainty.
No calibrated default penalties or runtime coverage estimates are invented.
`models.py` owns domain values, `contracts.py` the analyzer protocol,
`scoring.py` arithmetic and availability, and `report.py` a consistent scored
snapshot. There is no analysis orchestration or report renderer yet.

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
