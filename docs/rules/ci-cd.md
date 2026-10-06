# Static GitHub Actions observations

GitHubActionsAnalyzer (`ci-static`, Category.CI_CD) consumes only an available
WorkflowSnapshot. It never acquires sources, reads files, starts processes, contacts
GitHub, downloads actions, imports target code or executes/evaluates workflows,
shell/run contents, Docker, expressions, matrices, composite actions or reuse.
Generic Phase 3 registration/execution and explicit-policy reports are unchanged.
See [workflow data](../workflow-data.md) for exact selection and parser limits.

## Rule catalog

| Rule | Severity | Observation |
| --- | --- | --- |
| CI001 | INFO | No GitHub Actions workflow files observed in the eligible snapshot |
| CI002 | LOW | Recognized remote action/reusable-workflow reference lacks full commit-SHA form |
| CI003 | LOW | Literal write-all permissions declared at workflow or job level |

The immutable typed catalog validates CI plus three-digit IDs, Category.CI_CD,
Severity membership and required text. CI001 does not establish no CI: other
providers, excluded data or other input formats can exist. CI002 is a reproducibility
and supply-chain review advisory, not proof of malicious action code. CI003 observes
an explicit broad declaration, not effective token permissions or an exploit.
Legitimate jobs can require writes; overrides/platform settings can reduce access.
Absence of permissions, read-all, empty mapping and named read/write/none scopes
are not flagged. No permission inheritance/default evaluator or individual-write
scope rule is implemented. Severity remains deliberately advisory; no production
weights, penalties or CI maturity percentages are selected.

## Supported structure and references

Require one mapping document with literal on trigger presence (nonempty scalar,
sequence of scalar names or mapping) and nonempty jobs mapping. Job IDs use an
ASCII letter/underscore followed by ASCII letters/digits/underscores/hyphens.
Normal jobs require nonempty runs-on scalar/sequence/mapping and a nonempty flat
steps sequence; each step must specify exactly one uses or nonempty scalar run.
Reusable jobs use job-level uses without steps/runs-on. This is a small recognized
structure, not GitHub's full schema or validation of event names, runner labels,
action existence, permissions names, platform acceptance, reachability or success.
Newer parallel/wait/control step forms are outside this subset and yield UNSUPPORTED
rather than hiding their possible action references.

CI002 handles both step actions and job-level reusable workflows. Remote forms are
owner/repo@ref and owner/repo/subpath@ref; job references require the exact remote
.github/workflows/<name>.yml/.yaml file shape. Owner/repository and subpaths use
conservative ASCII identifiers, no empty/dot/parent segments, and documented owner
length. Refs use an ASCII Git-ref subset: letters/digits/underscore initial character,
then letters/digits/dot/underscore/slash/plus/hyphen; empty/dot-prefixed/.lock
components, double dots and trailing dots are rejected. This is not a complete Git
ref validator. Unsupported/malformed forms make the entire analyzer unavailable.

A literal ref of exactly 40 hexadecimal characters, case-insensitive, has the
supported full SHA-1 form and avoids CI002. Short hex, branch/tag names and 64-hex
values do not have that form. This does not verify the commit exists, its repository
provenance, contents or safety; there are no GitHub/marketplace lookups. Revisit
compatibility if GitHub documents other commit forms. The current
[secure-use reference](https://docs.github.com/en/actions/reference/security/secure-use)
describes full-length SHA pinning and SHA-1, while the
[workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)
shows the reference forms and full commit examples.

Local ./path actions, direct local reusable workflow paths and current $/path
self-repository forms are recognized and excluded from this remote-Git rule.
Job-local forms must point directly into .github/workflows. Self-repository syntax
is documented in the [GitHub changelog](https://github.blog/changelog/2026-07-30-reference-same-repository-actions-with-self-repository-syntax/);
this analyzer does not infer runner compatibility. Docker:// references in steps
are distinguished from GitHub Git references; image digest pinning and image-name
validation are outside CI002. Reusable Docker jobs and unknown locations/forms are
unsupported. Referenced action/composite/reusable bodies are never fetched/followed.

## Expressions, states and evidence

All expression contents remain opaque. Dynamic uses, permission values/scope names
or trigger names make required observations unresolved: UNSUPPORTED with no partial
findings. Expressions in run/if/with/matrix and dynamic runs-on are not evaluated.
No runtime-version rule is shipped: even literal setup-python configuration cannot
prove project support, interpreter use, matrix execution, tests or coverage.

Missing workflow data yields FAILED. An available empty snapshot yields COMPLETED
with CI001, never NOT_APPLICABLE solely for absence. Successfully supported files
produce COMPLETED with zero or more observations. Any selected file violating YAML
safety or recognized structure yields UNSUPPORTED for the whole set, discarding all
partial findings. Memory failure yields FAILED; unexpected ordinary exceptions are
isolated by Phase 3. Unavailable states retain incomplete-score semantics.

CI001 uses singleton ID ci-static:CI001 and repository-level evidence with no invented
path/line. Occurrence IDs use ci-static:CI00n: plus SHA-256 of rule ID, NUL, exact
relative workflow path, NUL, one-based line:zero-based column. Only structural
locations enter hashes; no action ref, job ID, expression, command, credential,
root, timestamp or randomness is included. IDs identify observations at locations;
source-layout changes can change them. Findings sort by exact identifier.
Evidence contains only normalized relative path, scalar declaration line and a
RepoLens-controlled statement. Raw YAML/parse diagnostics and arbitrary values
never enter findings. Parsing and recognizing structure do not establish platform
validity or whether any workflow/action/test/deployment actually runs successfully.
