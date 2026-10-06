# Explicit configuration schema 1

Configuration loads only through **--config PATH**. RepoLens never discovers it in
the target, cwd, home, XDG directories, environment or Git configuration. Hostile
target repolens.toml/.repolens.toml/pyproject.toml cannot alter their own assessment.
An operator may explicitly select a target-owned file, accepting that trust
decision; contents are validated data, never executable input.

Git Bash examples after development setup:

```bash
uv run --locked repolens scan "C:/projects/example" --config "C:/configs/repolens.toml"
uv run --locked repolens scan "C:/projects/example" --config policy.toml --fail-under 90 --fail-on-severity high --format json
uv run --locked repolens scan "C:/projects/example" --config policy.toml --format html --output report.html
```

## Complete TOML schema

```toml
schema_version = 1

[scan]
exclude = ["generated/", "vendor/", "src/generated.py"]

[rules]
disable = ["PY002", "CI003", "BANDIT-B602"]

[gate]
fail_under = "85.50"
fail_on_severity = "high"
```

schema_version is required and must be integer 1, not bool/string. The three
sections/fields are optional; defaults are empty arrays and no gates. The minimal
file is `schema_version = 1`. Unknown keys/sections, wrong types, duplicate entries,
malformed TOML and unsupported versions fail before acquisition with exit 2 and
controlled stderr. No config contents, absolute paths or OS diagnostics are echoed.
Breaking config semantics require a new config schema, independently of package,
JSON schema and scoring-policy versions.

No includes, environment interpolation, shell expansion, Python expressions,
plugins, credentials, Git arguments, timeouts, resource limits, analyzer classes,
templates, output/overwrite settings, penalties or weights are supported.
`${TOKEN}/` is a literal relative exclusion, never an environment lookup.

## Explicit-file boundary

Maximum input is **64 KiB**, sufficient for this bounded schema. Only an existing
regular file is accepted, using strict UTF-8 and one tomllib parse. BOM is not
accepted. Missing files, directories, parent-segment (`..`) spellings, UNC/device
paths and symlink/reparse components are rejected. Path components are checked
without resolving links; descriptor identity/type, size and mtime are compared
before/after bounded reads. Descriptors close on success/failure. Open/read/change/
close/parse errors become controlled ConfigurationError values.

Explicit relative paths use cwd to address the named file, not to search for
configuration. Mounted filesystem paths still use host filesystem access. Checks
are not atomic and do not provide isolation from a hostile concurrent writer.
Config paths/source TOML are not retained in reports.

## Literal exclusions

At most **128 entries**, each at most **256 UTF-8 bytes**, are accepted. They are
nonblank normalized POSIX-relative strings, matched exactly and case-sensitively
on every platform, sorted canonically with duplicates rejected.

- `src/generated.py` excludes only that regular-file path.
- `vendor/` prunes that directory and every descendant before descent/read.
- `vendorish/` and different-case spellings do not match `vendor/`.
- An entry without trailing slash does not prune a directory of the same name.

No glob/negation/include syntax: `* ? [ ] !`, absolute/drive paths, backslashes,
parent/dot/noncanonical slash spellings and Unicode control/format characters are
rejected, not normalized into acceptable entries. Literal spaces, Unicode and
markup characters in otherwise valid paths are data and escaped in reports.
Overlapping distinct entries are allowed; only identical entries are duplicates.

User scope can only narrow authoritative .git/venv/node_modules/build/dist/cache
and link/reparse safety exclusions. Visited root entries still count toward entry
limits; pruned descendants are never visited. Included files retain every entry,
depth, size/count/aggregate/verified-read limit. One remaining inventory drives
FileInventory, PythonSourceSnapshot and WorkflowSnapshot consistently. CLI scope
enters the combined builder/shared traversal; legacy standalone builders retain
their default behavior.

Empty selected Python scope uses existing NOT_APPLICABLE semantics. CI001 can
observe no workflows within configured eligible scope; it does not establish
absence outside that scope. Broad exclusions can increase score or remove
applicability. Compare scores only with matching effective scope, not policy alone.

## Exact rule disabling

At most **128 IDs**, canonical sorted/unique, are supported. Static IDs are checked
against the shipped catalogs: RH001/RH002, PY001/PY002, TEST001/TEST002 and
CI001/CI002/CI003. PY099 is a configuration error. Vendor IDs must match exact
`BANDIT-B` plus three ASCII digits. Syntax is validated without copying Bandit's
catalog or requiring its installation; the syntax does not prove a vendor test
exists. Wildcards are not supported.

After unchanged analyzer execution, one immutable application step removes only
findings whose exact rule IDs are disabled. Normal AnalyzerResult constructors
preserve metadata, states, reasons and ownership. Remaining findings drive
deductions, counts, scores and severity gates. Suppressed bodies are not retained;
disabled IDs disclose the scope decision. Unrelated findings remain unchanged.
All default analyzers remain planned, even with all potential rules disabled.
Missing/FAILED/SKIPPED/UNSUPPORTED work still blocks scoring. Disabling a vendor
rule cannot bypass missing Bandit.

Analyzers never parse TOML; rule severity/category/text, generic scoring and
PYTHON_STATIC_V1 are unchanged. Report structural validation rejects active
findings contradicting declared disabled rules, without recalculating policy in
metadata validation or inventing capability.

## Gates and precedence

fail_under requires an ASCII plain decimal **string** in 0..100 with at most two
fractional digits. TOML floats/integers are rejected. The pure Decimal validator
is shared with --fail-under; metadata uses two-decimal strings. No binary float.
fail_on_severity is info/low/medium/high/critical, also accepted by the new
--fail-on-severity option. Any active finding at or above the selected enum impact
rank fails; no lexical comparison. INFO can intentionally gate observations while
remaining zero deduction. Disabled findings cannot trigger the gate.

Per-field precedence: **explicit CLI > explicit file > unset**. A CLI score gate
leaves file severity settings intact and vice versa; no max/min combination.
Either active gate failure yields exit 1. Equality satisfies the score gate.
Unavailable overall score always exits 1, including threshold zero or a met
severity gate. No findings means no severity trigger, not proof of availability.
Reports emit before exit 1; controlled config/input/output failures are 2 and
internal errors 3. Gate values never change the score. Console shows outcomes;
JSON/HTML keep effective settings distinct from assessment availability/value.

## Applied metadata and JSON schema compatibility

AnalysisReport retains optional immutable AppliedConfiguration: configuration
schema, normalized exclusions, disabled IDs and effective gates. Its domain values
contain no TOML/parser/catalog dependency. Product validation remains in the
application boundary, and all renderers read these same facts. No config path,
raw TOML, environment or fingerprint is recorded.

Phase 11 explicitly allows additive optional fields under JSON schema `"1"`.
Phase 12 appends this object without removing, renaming or retyping existing data:

```json
"configuration": {
  "schema_version": 1,
  "exclusions": ["generated/", "vendor/"],
  "disabled_rules": ["CI003", "PY002"],
  "gates": {"fail_under": "85.50", "fail_on_severity": "high"}
}
```

Explicit CLI-only gates use null configuration.schema_version and empty scope
arrays. No --config and no explicit gates means metadata is absent: default plan,
score semantics and default report bytes remain Phase 11-compatible. Existing
--fail-under semantics remain, with an additive metadata disclosure when supplied.
Old required-field goldens remain active; compatibility tests remove the new
object and compare all prior values/types/semantics. Schema-1 consumers should
ignore unknown optional fields as already documented.

## Limits and deferred capability

No automatic config trust, analyzer-level disabling, per-category gates, custom
severity/weights, plugin discovery or missing-capability enablement exists.
Dependency auditing remains outside the default plan; Documentation/Maintainability
remain unassessed. UTF-8/LF no-overwrite hard-link publication and the 64 MiB report
ceiling are unchanged. Producers retain redaction responsibility; do not put
secrets into visible relative exclusion names. No Phase 13 or release work occurs.
