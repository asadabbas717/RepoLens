# Report formats and JSON schema 1

Three pure functions accept the same immutable AnalysisReport:
`render_console`, `render_json` and `render_html`. They use its existing policy,
scores, deductions, plan, results and findings. They do not recalculate scores,
select capability, run analyzers, acquire sources, read target files, probe the
environment or perform network/subprocess work. A frozen internal ReportView
provides one public-name check, declared analyzer outcomes and outside-scope list;
it is presentation data, not another scoring model. No new dependency is required.

## CLI selection and exits

In Git Bash, after the existing development setup:

```bash
uv run --locked repolens scan .
uv run --locked repolens scan . --format console
uv run --locked repolens scan . --format json
uv run --locked repolens scan . --format json --output report.json
uv run --locked repolens scan . --format html --output repolens-report.html
```

These are examples, not a claim of self-dogfooding. Console is the default. Console
and JSON go to stdout unless --output is supplied; HTML requires --output. Format
is explicit and is never inferred from a filename extension. All formats may be
written to a new file, with no stdout status/path messages. JSON stdout contains
exactly one complete JSON document with a final LF, even for an incomplete scan.

The Phase 10 exit codes remain: 0 for usable numeric assessment with no failing
gate, 1 for unavailable assessment or unmet score gate, 2 for controlled input,
acquisition or output-processing failure, and 3 for unexpected internal failure.
An incomplete or gate-failed assessment still emits its full requested report
before returning 1. Rendering/publication failure takes precedence (2/3).
Thresholds remain exact Decimal comparisons of the final domain score.
Console includes requested gate status footers; JSON/HTML expose effective settings
in optional applied metadata, with outcomes conveyed by process exit. No report rescoring
occurs. Argparse help/version perform no acquisition or analysis.

## Intentional JSON contract

The top-level keys, in serialized order, are:

| Key | Fields / meaning |
| --- | --- |
| schema_version | String `"1"`; independent of package and policy versions |
| tool | `name` (RepoLens), `version` (package version constant) |
| repository | `name` (public display basename only) |
| policy | `identifier`, `scope` category strings, `penalties`, `weights` |
| assessment | `state`, `overall_score`, `finding_count`, `outside_scope`, `limitations` |
| categories | One entry for every in-policy category, including unavailable work |
| analyzers | One entry for every planned analyzer, including missing results |
| findings | Every retained finding, including INFO |
| configuration (optional) | Configuration schema/null, exclusions, disabled rules and effective gates; appended in Phase 12 |

Policy penalties are `{severity: string, points: integer}` entries, weights are
`{category: string, weight: integer}` entries. The full policy values are preserved
to explain scoring, without selecting defaults in reporting. Scope/outside-scope
use Category declaration order. No software/tool environment paths, timestamps,
hostnames, usernames or canonical URLs are synthesized. The domain has no remote
URL field, so no renderer reaches back into acquisition to add one.

Assessment `state` is `"available"` for a numeric domain overall value and
`"unavailable"` for None. It describes value availability, not a new analyzer
state. `overall_score` is an exact two-decimal string such as `"98.75"`, or JSON
null. There is no binary float conversion. Categories have integer values or null,
never an artificial zero for unavailable work. `finding_count` is an integer;
limitations are strings and outside_scope is a category-string array.

Each category entry has these exact keys in order:

```text
category, state, value, deductions, completed_analyzers,
unavailable_analyzers, non_applicable_analyzers
```

Category states use the domain strings `assessed`, `incomplete`, `not_applicable`.
Deductions contain `rule_id`, `severity`, integer `points`, and `finding_ids`.
All raw rule deductions remain visible, including zero-point INFO and sums above
the category floor, or completed observations alongside unavailable work.

Each analyzer entry has:

```text
identifier, category, state, reason, finding_count
```

Recorded states are exactly `completed`, `failed`, `skipped`, `unsupported` or
`not_applicable`. Completed reason is null; recorded non-completed reasons are
producer-controlled strings. For a missing planned result, state is null, count
is zero, and reason is `"Planned analyzer result is missing"`; reporting does not
invent FAILED/SKIPPED for work with no recorded outcome. Its category already
contains that analyzer in unavailable_analyzers under the domain contract.

Each finding has:

```text
identifier, rule_id, category, severity, title, description,
evidence, recommendation, source_analyzer
```

Severity strings are `info`, `low`, `medium`, `high`, `critical`. Each evidence entry
has `description`, `file_path` (existing relative POSIX path or null), and
`line_number` (positive 1-based integer or null). No source snippets, target
literals, vendor diagnostics or additional absolute paths are added.

Serialization uses the standard JSON encoder, two-space indentation, ASCII
escaping, explicit field insertion order and one final `\n`. Unicode/control
values round-trip through json.loads; HTML-looking strings are ordinary JSON data.
Do not embed JSON directly in HTML script elements without a separate reviewed
embedding boundary. No dataclasses.asdict, enum reprs or private fields are dumped.

Categories follow domain Category order, analyzers and findings their canonical
identifier order, deductions rule-ID order and deduction finding IDs sorted order.
Evidence retains each finding's original tuple order. Penalties follow Severity
order and weights Category order regardless of input policy entry ordering.
Identical reports and software version yield byte-identical UTF-8/LF output on
Windows/Linux; locale, terminal size, TTY status and clock do not affect output.

**Breaking JSON field, type or semantic changes require a new schema version.**
Phase 12 uses the already documented additive-extension rule to append optional
configuration metadata. Existing required fields/types/semantics and no-config
default report bytes are unchanged; compatibility tests lock that decision. See
[configuration](configuration.md) for the exact object and independent schema.
Additive optional fields can be introduced within schema 1; consumers should
ignore unknown fields and compare schema_version before interpreting known fields.
Consumers must not assume object key order is semantically significant, despite
deterministic producer bytes. Enum additions need explicit compatibility review;
unknown future values must not silently mean a clean result. Scoring-policy
changes separately require a new policy ID. Package version changes neither
implicitly authorize policy changes nor silently change JSON schema semantics.

## Console and HTML

Console is full, plain text, without colors, emoji requirements or terminal-width
probing. It shows repository/policy, availability/value, finding count, category
states/memberships/deductions, analyzer states/reasons, every finding's identifier,
category, severity, source, observation, evidence/location and recommendation,
followed by scope/limitations. Findings use canonical identifier order, not a
severity-only sort; INFO is never hidden. Unicode control/format/surrogate code
points are printed as visible escapes so filenames/reasons cannot inject terminal
controls or fake extra report lines. No first-N summary or silent truncation exists.

HTML is one standalone document with semantic main/header/sections, ordered
headings, a category table with caption and row/column headers, full finding
articles and evidence. Every dynamic value passes html.escape(..., quote=True)
after controls are made visible, even normally controlled metadata. Values are
text, never executable markup or target-selected attributes/templates. Generated
article IDs are numeric, not raw finding IDs. There is no JavaScript, CDN, font,
external image, CSS or other network resource. CSS is embedded and supports narrow
screens, printable output, text status labels and a visible focus outline for the
keyboard-scrollable table region. Evidence paths are text, not active file links.

HTML escaping prevents active markup, not secret disclosure. Current analyzer
producers redact source/tool values before they reach Finding/Evidence/reason;
ordinary exceptions and invalid results become controlled Phase 3 failure reasons.
Tests retain secret-bearing target/tool/exception regression coverage. Programmatic
callers and future trusted analyzers are responsible for producer redaction of
their own free text; reporting cannot identify arbitrary secrets reliably. It
does not independently redact one format while another leaks the same value.

Repository.name is a permissive domain display value, so one common lexical guard
rejects `.`, `..`, slash/backslash, colon or @ shaped identities before any format
is emitted. This excludes host paths/transport credentials without filesystem
inspection. Valid basenames may contain markup characters; those are escaped for
HTML and controls shown literally in human formats. A local basename can disclose
the project name; choose a suitable public identity for programmatic reports.
Names containing colon/@ on a permissive filesystem currently cannot be published
through this guard; failure is explicit, never silently replaced with a new name.

100 means no deductive findings in the completed supported scope, not perfection
or certification. Testing is not execution/effectiveness and security is not
dependency auditing. Documentation/maintainability remain outside the default
policy scope. The full policy, states, findings and limitation text are essential
context, as described in [calibration](scoring-calibration.md).

## Output publication and resource boundary

--output never creates missing parents or silently overwrites existing paths.
File, directory, symlink and dangling-link destinations are rejected by lstat.
The existing parent is canonicalized during preflight before acquisition. Output
uses explicit UTF-8/LF. A private same-directory temporary sibling is written,
flushed, fsynced and closed, then published by an atomic hard link that fails if
the destination exists—even if another writer created it after preflight.
No replace/force fallback can overwrite user or target files. Temporary siblings
are cleaned on success/failure; OS diagnostics and temporary names are not echoed.

Publication requires same-directory hard-link support (ordinary NTFS/POSIX local
filesystems provide it). Filesystems that do not support it fail safely with exit 2
rather than receive a weaker overwrite-prone fallback. The user-owned parent must
remain stable; this is not isolation from a hostile concurrent directory owner.
If cleanup fails after publication, exit 2 can accompany an already complete
destination; the report is never deliberately published partially. Cleanup failure
is surfaced, not reported as unconditional success.

All serialized formats have a **64 MiB UTF-8 artifact ceiling**, checked while
collecting serialization chunks. Exceeding it fails explicitly before stdout or
publication; no findings are silently removed. Python AST patterns can produce
many occurrences even within 4 MiB source data, and vendor output can also contain
many observations. A generous finite artifact ceiling bounds output growth while
keeping normal reports useful. It is a serialized-size bound, not an OS memory
quota: domain findings, JSON projection and individual escaping operations already
occupy memory. Report consumers cannot treat it as a hostile-writer sandbox.

Stdout serialization completes before one UTF-8 binary write and flush, avoiding
Windows newline and locale conversion. I/O errors are sanitized output failures;
stdout cannot be rolled back after a transport failure. File publication provides
the stronger complete/no-overwrite guarantee. No atomicity beyond the underlying
filesystem or stdout transport is claimed.
