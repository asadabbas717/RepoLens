# Architecture and product contract

RepoLens is a modular Python application, initially a CLI/static-analysis tool.
The `domain`, acquisition `infrastructure`, orchestration `application` and
concrete `analyzers` packages exist after Phase 9. Add further boundaries when implementations arrive.

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
never imply passed checks or a numeric clean result. The [scoring contract](scoring.md)
defines explicit policies, per-rule deductions, caps, weights and uncertainty.
Phase 9 provides explicit product values with documented heuristic rationale;
no runtime coverage estimates are invented.
`models.py` owns domain values, `contracts.py` the analyzer protocol,
`scoring.py` arithmetic and availability, and `report.py` a consistent scored
snapshot. Application orchestration composes these values; rendering remains
outside this phase.
`application/scoring_policy.py` owns the immutable `PYTHON_STATIC_V1` value
profile. Product selection belongs above the generic domain; domain.scoring
remains policy-agnostic and unchanged. No implicit policy/plan selection or
configuration loading is added. See [calibration](scoring-calibration.md) for
versioning, exact values, partial scope and availability interpretation.

## Main engineering risks

- Static heuristics can mislead: document what each rule actually proves.
- Missing tooling can inflate scores: represent availability separately.
- Large/malicious repositories can exhaust resources: impose explicit limits.
- Cross-platform paths and cleanup can differ: test Windows and Linux fixtures.
- Report fields can become API commitments: version JSON and test serialization.
- Dependency updates can break reproducibility: commit uv.lock and review updates.

PyYAML is the selected sole runtime dependency, for non-constructing workflow
parsing. Typer/Rich and Jinja2
remain candidates, not committed dependencies. Add each only with a concrete
requirement and maintenance/security review.

## Acquisition boundary (Phase 2)

`infrastructure/git.py` owns isolated subprocess execution and its narrow test
protocol. `repository_source.py` owns URL/local validation, minimal source
metadata and context-owned leases. `traversal.py` owns bounded no-content-read
inventory, exclusions and no-link descent. `errors.py` defines sanitized source
errors. Only infrastructure performs subprocess/filesystem I/O; the domain
contains no live filesystem access. See [acquisition](acquisition.md) and ADR 0003 for exact semantics and
limitations. Application execution does not acquire sources or traverse files.
Concrete hygiene analysis uses only an immutable path snapshot; CLI remains
unimplemented.


## Orchestration boundary (Phase 3)

`application/orchestration.py` owns AnalyzerPlan and execute_analyzers. Plans
capture valid immutable metadata and bound analyzer callables once, reject
duplicate identifiers and sort by exact identifier. Execution is sequential;
ordinary exceptions and invalid results become sanitized FAILED outcomes.
All valid domain states are preserved. Result ownership includes the complete
registered spec. Cross-result finding identities and rule categories are checked
before acceptance, so invalid results cannot abort later report construction.

The application depends only on domain contracts and the standard library.
Phases 4 and 5 extend AnalysisContext with optional FileInventory and bounded
PythonSourceSnapshot data; execution remains independent of those data shapes. Acquisition stays caller-owned; leases
and filesystem implementations never enter the domain.

Execution returns an ordered tuple of AnalyzerResult values. Callers may compose
AnalysisReport using plan.specs, those results and an explicit ScoringPolicy.
The engine neither chooses policy scope nor scores or renders. See
[orchestration](orchestration.md) for lifecycle and limitations.


## Hygiene and repository data (Phase 4)

FileInventory is a bounded immutable tuple of normalized relative POSIX paths,
canonically ordered and validated without I/O. None inventory means unavailable;
an empty inventory is an available observation. infrastructure.inventory builds
context only after a complete traversal under an open lease. Partial/error
inventories are never published. Detached data has no capability to read a root
or former temporary workspace. Domain path validation is shared with Evidence.

RepositoryHygieneAnalyzer consumes this data and an immutable typed rule catalog:
RH001 observes no exact root .gitignore path in eligible inventory (INFO), and
RH002 observes ASCII-only case-colliding full file paths (LOW). No tracking,
commit, ignore-effectiveness, content or complete filesystem absence claim is
made. Registration and execution still use the unchanged Phase 3 API, with no
hygiene-specific orchestration logic. Product policy values are separate from these rules. See
[repository data](repository-data.md), [hygiene rules](rules/repository-hygiene.md)
and ADR 0004 for the boundary, eligibility limits and occurrence identities.


## Python source and static analysis (Phase 5)

Pure PythonSourceFile/PythonSourceSnapshot values contain only relative paths and
bounded decoded text, excluded from default representations. Context validation
requires source membership to exactly match selected .py/.pyi inventory paths.
The infrastructure builder reuses the shared metadata walker, inventories once,
admits candidates within per-file/count/aggregate limits, and reads only verified
regular files under a live lease. All reads/encoding failures are sanitized and
prevent publication. Domain relative-path validation now lives in domain.paths;
models preserves its helper import for compatibility.

PythonStaticAnalyzer requests 3.13 grammar, parses each file once and walks its
AST once for bare except and non-stub wildcard import observations. Unsupported
parsing discards partial findings; an empty available source set is non-applicable,
while unavailable data is failed. Orchestration and scoring are unchanged. No
target imports or execution exist. Phase 7 adds a detached security adapter. See
[Python source](python-source.md), [Python rules](rules/python.md) and
ADR 0005 for the resource, encoding, grammar and race limitations.


## Static testing (Phase 6)

TestingStaticAnalyzer consumes the same immutable PythonSourceSnapshot, without
new I/O or configuration content. Two INFO rules observe absent conventional
filenames or direct declarations; framework collection/execution is never inferred.
A tiny pure python_ast module shares Phase 5 grammar/warning policy while keeping
analyzers independent. Orchestration, scoring and acquisition are unchanged.
Testing configuration is not interpreted and target coverage is not measured.
See [testing rules](rules/testing.md) for exact shapes, IDs and unavailable states.


## Security tools and dependency data (Phase 7)

PythonSecurityAnalyzer consumes detached source and a narrow domain BanditScan
contract. Infrastructure owns optional pinned Bandit, temporary materialization,
fixed controls, filtered process environment, deadlines, captures and schema
normalization. Security observations contain only rule/severity/location, never
vendor source or diagnostics. Git execution remains a separate specialized boundary.

DependencyManifestSnapshot admits two bounded root UTF-8 files; context validation
requires exact eligible inventory membership. An opt-in combined source/manifest
builder inventories once. The private verified_read module preserves existing
source checks for both builders. Pure domain declaration parsing supports only
static exact pins; DependencyAuditAnalyzer exposes unavailable vulnerability
auditing honestly. No resolver, target pip invocation, severity invention or
security-specific scoring exception is added. See [security rules](rules/security.md),
[dependency audit](dependency-audit.md) and ADR 0006 for explicit limits.


## GitHub Actions data and static CI/CD (Phase 8)

WorkflowFile/WorkflowSnapshot carry bounded hidden-repr UTF-8 text and exact
relative inventory membership. A dedicated workflow builder inventories once,
uses existing verified reads and publishes no partial data. Other snapshots,
Git/process isolation and generic orchestration remain unchanged.

The CI analyzer uses a pure PyYAML BaseLoader event admission/node composition
layer, not constructors or implicit scalar typing. Structural bounds, duplicate
keys and unsupported YAML features cannot masquerade as clean. Normalization
retains only safe observation locations for three typed catalog rules: eligible
workflow absence, non-full-SHA remote refs and explicit write-all declarations.
Neither Actions execution nor complete schema/runtime inference is implemented.
See [workflow data](workflow-data.md), [CI/CD rules](rules/ci-cd.md) and ADR 0007.
