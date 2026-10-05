# Architecture and product contract

RepoLens is a modular Python application, initially a CLI/static-analysis tool.
The `domain`, acquisition `infrastructure` and orchestration `application`
packages exist after Phase 3. Add further boundaries when implementations arrive.

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
owned temporary workspaces with cleanup attempted on every exit. Bound traversal,
file size, clone time, and tool output; do not follow symlinks outside the repository.

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
snapshot. Application orchestration composes these values; rendering remains
outside this phase.

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

## Acquisition boundary (Phase 2)

`infrastructure/git.py` owns isolated subprocess execution and its narrow test
protocol. `repository_source.py` owns URL/local validation, minimal source
metadata and context-owned leases. `traversal.py` owns bounded no-content-read
inventory, exclusions and no-link descent. `errors.py` defines sanitized source
errors. Only infrastructure imports subprocess/filesystem APIs; the domain is
unchanged. See [acquisition](acquisition.md) and ADR 0003 for exact semantics and
limitations. Application execution does not acquire sources or traverse files.
Concrete analyzers and CLI remain unimplemented.


## Orchestration boundary (Phase 3)

`application/orchestration.py` owns AnalyzerPlan and execute_analyzers. Plans
capture valid immutable metadata and bound analyzer callables once, reject
duplicate identifiers and sort by exact identifier. Execution is sequential;
ordinary exceptions and invalid results become sanitized FAILED outcomes.
All valid domain states are preserved. Result ownership includes the complete
registered spec. Cross-result finding identities and rule categories are checked
before acceptance, so invalid results cannot abort later report construction.

The application depends only on domain contracts and the standard library.
AnalysisContext remains repository display identity only. Acquisition stays
explicitly caller-owned; leases and filesystem implementations do not enter the
domain. Future static analyzers will need a separately justified safe data-access
seam and lifetime model. That capability is not speculatively added here.

Execution returns an ordered tuple of AnalyzerResult values. Callers may compose
AnalysisReport using plan.specs, those results and an explicit ScoringPolicy.
The engine neither chooses policy scope nor scores or renders. See
[orchestration](orchestration.md) for lifecycle and limitations.
