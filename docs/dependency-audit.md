# Static dependency declarations and audit limits

Phase 7 introduces a detached immutable DependencyManifestSnapshot, not a package
resolver. Only exact root `requirements.txt` and `pyproject.toml` are admitted.
Each raw/decoded manifest is at most 64 KiB; two unique whitelisted files imply an
aggregate ceiling of 128 KiB. UTF-8 (optional BOM) is decoded strictly. Other
encodings fail safely. Near matches, nested manifests, lock files, requirements-dev
and setup.py/setup.cfg are outside this content scope. Existing traversal inventory
eligibility remains in effect; excluded symlink/reparse entries are not read.

`snapshot_dependency_context` builds manifest-only context. Alternatively,
`snapshot_python_context(..., include_dependency_manifests=True)` inventories once
and publishes Python plus manifest snapshots together. The opt-in default preserves
Phase 5 behavior. Both use the private verified_read primitive factored from the
existing source implementation: active lease, normalized relative paths, root
containment, no link/reparse components, regular-file/descriptor identity,
pre/post size/mtime checks, limited reads and descriptor closure. Publication is
all-or-nothing, with sanitized decoding/resource errors. Context validates exact
manifest membership against the eligible inventory. No live root/handle reaches
an analyzer and text is omitted from default representations. Reads still have
Phase 5's documented filesystem race limitations; they are not atomic snapshots.

## Supported declaration subset

The pure `parse_declarations` function returns canonical names and exact declared
versions. It does not claim resolved, installed or transitive dependencies.
Requirements allow blank lines, full comments and whitespace-delimited inline
comments; remaining lines must match `name == version`. PEP 621 accepts a static
`[project].dependencies` string array. Other TOML fields are not executed/interpreted.
`dynamic` containing dependencies is unsupported. Invalid TOML or field types fail
structural parsing. Absent project/dependency fields yield an empty observed subset,
not knowledge of every provider's dependency graph.

Names use ASCII letters/digits with internal dot/underscore/hyphen, canonicalized
to lowercase and runs of those separators replaced with hyphens. Versions are a
restricted lowercase subset: numeric dotted releases, optional a/b/rc prerelease,
.postN, .devN and +local segments. Epochs, alternative PEP 440 spellings, ranges,
wildcards, arbitrary equality, extras, markers and unpinned names are unsupported.
Markers are not evaluated against RepoLens's host. This is intentionally not a
complete requirements/PEP 508 parser. At most 1,000 declarations are considered;
identical canonical pins merge, conflicting pins make the entire set unsupported.

Includes/constraints, editable/local/file/VCS/direct URLs, hash/index options,
credentials and environment expansion are never forwarded to pip or any tool.
One unsupported declaration prevents partial success; parser exceptions contain
controlled text, not the declaration/configuration or credentials. The normal test
suite has no advisory network dependency and never executes these fixtures.

## pip-audit decision

The inspected lock version is **2.10.1**. Local CLI help and a detached exact-pin
`--dry-run -r ... --no-deps --disable-pip -f json` confirmed a no-resolution/no-pip
mode. This dry run is capability evidence, not an audit or clean result.
[Official pip-audit documentation](https://github.com/pypa/pip-audit) describes
these flags. The installed JSON formatter exposes advisory id, fix_versions,
optional aliases and description, but **no structured severity**. The existing
Finding contract requires an impact Severity; choosing INFO/HIGH from presence or
prose would fabricate that impact. Target pip-audit execution is therefore deferred
until a trustworthy severity/advisory representation is designed explicitly.
No vulnerability rule IDs, CVE/GHSA severity mapping, advisories, percentages or
security score are invented. No domain severity or scoring semantics are changed.

`DependencyAuditAnalyzer` (`dependency-audit`, Category.SECURITY) implements static
manifest validation and audit availability, not vulnerability detection. Missing
snapshot or malformed structured content yields FAILED. Unsupported syntax,
unknown/no supported manifest scope, and valid exact declarations—including an
empty observed subset—yield UNSUPPORTED with a controlled limitation reason.
It never returns a clean audit or findings and thus cannot inflate a security score.
This analyzer can be independently registered beside python-security; the generic
orchestrator preserves both states with explicit caller-supplied policies,
including Phase 9's [product values](scoring-calibration.md). A declared audit
continues to block numeric security/overall scores; the policy cannot omit it
after execution to salvage a number.

There is **no target dependency network, install, download, build, resolution,
auto-fix or execution** in Phase 7. RepoLens's development pip-audit gate still
queries advisory services for RepoLens's own environment; that is a separate gate,
not target analysis. Future audited scope must distinguish direct exact packages
from a complete dependency graph and treat network/tool failure as unavailable.
