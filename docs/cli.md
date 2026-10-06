# First command-line assessment

Phase 10 exposes the installed console entry point `repolens = repolens.cli:main`.
It uses standard-library argparse and the unchanged product scoring mechanism.
Phase 11 adds reporting; Phase 12 adds explicit validated configuration. `run(argv)` is a small
testable shell boundary returning scan status; normal argparse help/version and
argument failures raise SystemExit with their conventional codes. The entry point
passes actual arguments and exits with the returned status.

## Install and syntax

From the development checkout in Git Bash on Windows:

```bash
source .venv-bootstrap/Scripts/activate
uv sync --locked --group dev
uv run --locked repolens --help
uv run --locked repolens --version
uv run --locked repolens scan --help
uv run --locked repolens scan "C:/projects/example" --fail-under 85.50
```

An existing built wheel can be installed in a separate environment:

```bash
python -m venv .venv-cli
source .venv-cli/Scripts/activate
python -m pip install dist/repolens-0.1.0.dev0-py3-none-any.whl
repolens --help
repolens --version
repolens scan "C:/projects/example"
```

PyYAML is the only mandatory runtime dependency. Bandit is optional: the current
adapter accepts exactly 1.9.4 installed in RepoLens's own trusted interpreter.
If you deliberately want that supported capability, install it into that same
environment, never into the target repository's environment:

```bash
python -m pip install bandit==1.9.4
```

RepoLens never auto-installs Bandit. Missing or another installed version yields
UNSUPPORTED when Python security work is applicable, an unavailable overall score
and exit 1. The CLI still starts, shows help/version and performs safe acquisition.
For no selected executable Python sources, security is explicitly NOT_APPLICABLE;
Bandit is not required for that irrelevant work.

The sole command is:

```bash
repolens scan SOURCE [--config PATH] [--fail-under SCORE] [--fail-on-severity LEVEL] [--format console|json|html] [--output PATH]
```

For example, this explicitly requests public remote acquisition:

```bash
repolens scan https://github.com/owner/project.git --fail-under 85
```

Console is default; console/JSON use stdout unless --output is supplied. HTML
requires --output. File output accepts a new file in an existing parent only,
without overwriting or implicitly creating directories. See
[reporting](reporting.md) for schema 1, publication and presentation semantics.

No authentication/token, arbitrary Git URL, stdin archive, multiple-source,
plugin or arbitrary per-rule severity options exist. Explicit schema-1 TOML
supplies literal exclusions and exact disabled rules; settings are never discovered
in the target or host environment. See [configuration](configuration.md) for the
bounded input contract, complete schema and CLI precedence.

## Source classification and acquisition

Nonblank ordinary source strings are local paths. Absolute drive-rooted Windows
spellings `C:/projects/example` and `C:\projects\example` are recognized before
the URL-scheme check. Quoting paths with spaces works in Git Bash. Use a native
Windows spelling for programmatic argv; Git Bash may translate its own POSIX drive
spellings when launching native Python. Drive-relative `C:project` is not a
supported spelling; use a drive-rooted or ordinary relative path.

An initial URI scheme is always URL input. SCP-like `git@github.com:owner/repo`
is also classified as URL input so it cannot silently become local acquisition.
URL candidates are passed unchanged to Phase 2's canonical_github_url, then
RepositorySource.github: only the exact supported public GitHub HTTPS repository
root forms survive validation. HTTP, SSH, file URLs, credentials, ports, queries,
fragments, deeper pages and malformed forms fail before acquisition. Leading
whitespace does not rescue a URL from strict validation. Control characters and
blank source spellings are rejected. Ordinary local spellings are passed to
RepositorySource.local, including paths within a Git working tree.

Validation and Decimal threshold parsing precede acquisition. Help/version never
resolve Git, traverse a repository, start Bandit or access the network. Parser
errors show controlled usage/text rather than echo untrusted arguments.

The existing Git boundary retains absolute executable selection, argument arrays,
no shell, isolated configuration, disabled credential helpers/prompts, restricted
transport, prohibited redirects, TLS verification, no hooks/templates/lazy fetch/
submodules, timeouts, output bounds and sanitized diagnostics. Public remote
acquisition is the only intentional target network operation; tests simulate it.
Private authentication is not supported.

## One detached context and lease lifecycle

`infrastructure.analysis_context.snapshot_analysis_context` performs one bounded
metadata inventory. All Python and direct GitHub Actions candidates are admitted
before any content read. It reuses private admission and snapshot functions
factored from the standalone Python/workflow builders, which retain their APIs.
There is no second repository traversal or merging of independent inventories.

Existing resource ceilings remain: 20,000 visited entries/depth 32, Python files
256 KiB each / 512 files / 4 MiB aggregate, workflows 64 KiB each / 32 files /
512 KiB aggregate. Raw and decoded limits, Python coding-cookie decoding and
strict UTF-8 optional-BOM workflow decoding remain authoritative. Oversized selected
content fails rather than disappearing. Unselected large inventory files retain
Phase 2's omission behavior. Dependency manifests are not selected or read.

Every selected read retains the existing verified-read path/lease/containment,
link/reparse, regular-file/descriptor identity, size/mtime, bounded-read and closure
controls. Domain constructors verify exact snapshot membership in the one
eligible inventory. Any admission, decoding, detected mutation, lease or resource
failure prevents context publication. This is not an atomic filesystem snapshot:
local repositories must remain stable, and undetected concurrent same-size edits
or cross-file races are still possible. No new hostile-writer isolation claim is
made; see [Python source](python-source.md) and [acquisition](acquisition.md).

The CLI composes BanditRunner with the canonical origin root while the lease is
active. Its retained origin metadata is the existing temporary-storage exclusion
guard, not a source-read capability. It constructs the declared plan, then exits
acquisition before execution. Local leases close; temporary remote clones are
deleted. Only detached context reaches execute_analyzers. Bandit operates on its
owned detached copy after the original remote root disappears.

## Declared product capability and policy

The default plan always contains exactly these analyzers, canonically sorted by
identifier by Phase 3:

1. ci-static
2. python-security
3. python-static
4. repository-hygiene
5. testing-static

Membership is fixed before execution, independent of repository contents, tooling
availability or findings. Analyzer applicability stays inside existing lifecycle
semantics. Failed, skipped, unsupported or missing work is never removed to salvage
a score. Ordinary analyzer exceptions/invalid outcomes remain sanitized FAILED.

AnalysisReport receives plan.specs, all results and **PYTHON_STATIC_V1 directly**,
with policy ID `repolens-python-static-v1`. No weights/penalties are copied or
CLI-editable. Documentation and maintainability are outside the current scope.

**Dependency vulnerability auditing is not included in the default assessment.**
DependencyAuditAnalyzer is intentionally omitted before execution because its
auditing capability is still unavailable. This is not removal of an unavailable
result afterward. Bandit security evidence does not establish dependency security
or comprehensive security. Explicit programmatic plans that include dependency
auditing still become incomplete under the unchanged scoring contract.

100 means no deductive findings in completed supported scope, including possible
INFO advisories. Testing signals do not establish execution, coverage or
effectiveness. No target imports, tests, installs, builds, hooks, workflow commands
or expression evaluation are performed. See [calibration](scoring-calibration.md).

## Gate and exit codes

`--fail-under` accepts plain ASCII decimal notation between 0 and 100 inclusive,
with zero, one or two fractional digits. Examples: 0, 85, 85.50, 100.00. Parsing
uses Decimal and comparisons use the policy's published two-decimal score;
no binary floats are involved. Leading zeroes are allowed. Signs, exponent
notation, whitespace, percentage notation, NaN/Infinity, missing integer/fraction
digits, out-of-range values and more than two fractional digits are rejected.
The gate is inclusive: score equal to threshold succeeds. Unavailable score
always fails closed, even when the threshold is zero.

`--fail-on-severity` fails when an active finding meets or exceeds the requested
level in the explicit INFO, LOW, MEDIUM, HIGH, CRITICAL order. Disabled findings
affect neither gate. Each CLI gate overrides its corresponding configuration
field independently; an explicit zero score threshold also overrides the file.
When both gates are requested, either failure returns 1. Reports still render.

| Exit | Meaning |
| --- | --- |
| 0 | Numeric usable assessment and all requested gates pass |
| 1 | Incomplete/unavailable overall assessment, or either requested gate fails |
| 2 | Invalid invocation/configuration/source or controlled acquisition/input/output failure |
| 3 | Unexpected internal RepoLens composition/programming failure |

Without a gate, ordinary findings alone do not fail a usable numeric assessment.
NOT_APPLICABLE excludes its weight and need not fail the command. An all-unassessed
score would still be unavailable and exit 1. Missing Bandit, required analyzer
failure/unsupported work or planned missing work cannot return success.

Exit 2 includes source/clone failures, unavailable Git, snapshot budgets, decoding/
read failures, detected source mutation and origin validation before execution.
Syntactically unsupported Python or YAML is an analyzer outcome after detachment,
so it makes assessment incomplete (exit 1), not an input-processing exception.
An ordinary analyzer failure is also exit 1, not the internal failure path.
KeyboardInterrupt and SystemExit propagate; no BaseException catch is used.

## Report output

Phase 11 replaces the minimal summary with three deterministic projections of
AnalysisReport. Console displays all findings, evidence, recommendations, category
deductions and controlled analyzer reasons. JSON schema 1 is complete machine data;
HTML is standalone escaped text with embedded CSS. Reports expose suitable public
repository basenames, never absolute or temporary roots. No source excerpts or raw
tool/OS diagnostics are added. See [reporting](reporting.md) for identity checks
and the producer redaction contract; arbitrary free text is not a secret detector.

Normal stdout contains only the selected report. File output leaves stdout empty;
input/internal/output errors remain sanitized stderr. Incomplete or gate-failed
assessments still render, then return 1. Rendering/publication problems return 2
or unexpected-error 3, superseding assessment status. Console appends a requested
score/severity gate footers; JSON/HTML gate status remains in process exit, with
applied settings disclosed in report metadata. No timestamp,
TTY, color or locale behavior changes output. Score 100 receives no certification.
