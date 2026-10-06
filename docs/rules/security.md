# Detached Python security analysis

`PythonSecurityAnalyzer` (`python-security`, Category.SECURITY) receives a
`BanditScan` contract and immutable AnalysisContext. It never receives a lease,
root, callback, subprocess or file handle. Infrastructure composition supplies `BanditRunner(origin_root=lease.root)` while
the acquisition lease is active;
Phase 3 registration and execution remain generic. Only `.py` sources are
scanned; `.pyi` stubs are not runtime source. Required data missing means FAILED;
no `.py` files means NOT_APPLICABLE. Python 3.13 grammar preflight precedes the
vendor scan. Invalid/newer syntax means UNSUPPORTED; resource failure means FAILED.
This preserves acceptance policy, not a guarantee of identical host AST internals.

## Optional trusted tool

The reviewed version is Bandit **1.9.4**, already pinned in uv.lock for development.
It is not a mandatory runtime dependency. The adapter requires this exact installed
distribution in RepoLens's interpreter; absence or another version is UNSUPPORTED.
Review CLI/schema/behavior before updating that compatibility constant and lock.
The absolute Python executable entry is retained after resolving its parent, so
POSIX virtualenv symlinks preserve their environment. Python runs with `-I -B -X utf8`:
no target cwd imports, PYTHONPATH, user site or target plugins are loaded;
bytecode writes are disabled.
Bandit loads plugins installed in the trusted tool environment. Operators must
trust that environment; this is not isolation from malicious installed plugins,
sitecustomize or a compromised interpreter/tool. No tool auto-install occurs.

## Owned materialization and command

The runner retains only canonical origin metadata for an exclusion guard, not
a lease or target content capability. Before allocating files it resolves system
temporary storage and rejects storage contained by the origin, preventing target
tree mutation even when TMP points inside a checkout. The copied origin need not
exist during scanning; no original-source lookup occurs then. Synthetic data with
no target tree must explicitly use `origin_root=None`; callers must supply the
actual acquisition root for acquired data. Bandit never receives that root.

A checked system temporary `repolens-bandit-*` directory owns separate source/home/control
locations. Only detached `.py` data is written, preserving relative paths. Files
are created exclusively; incompatible filesystem names/collisions fail safely.
No live target directory or configuration is passed. Original coding cookies are
normalized to UTF-8 on eligible first/second comment lines because snapshot text
is already decoded; source bodies and line numbers are preserved. Literal text
merely resembling a coding cookie is unchanged. The original repository cannot
be mutated through this detached copy. Owned files are removed before scan returns;
allocation, capture or cleanup failure prevents a completed result.

The constructed argument array is equivalent to:

```text
<absolute trusted Python> -I -B -X utf8 -m bandit
-c <owned controls.toml> --ini <owned controls.ini>
-r . -x "" --ignore-nosec --severity-level all --confidence-level all
-f json -q -n 0
```

Cwd is the owned source directory. Both control files are RepoLens-created empty
Bandit configurations; target .bandit/TOML/config, caches, Git metadata and baseline
files are not copied. CLI excludes are explicitly empty. Target `# nosec` comments
cannot hide observations. Target code, tests, builds, hooks and dependencies are
never imported or executed. Standard Bandit scanning requires no network; no
network adapter is introduced, though this boundary is not an OS network sandbox.

## Process boundary

This is a single Bandit-specific runner, not a general executor and not a change
to GitRunner. It uses arrays, shell=False, explicit cwd, stdin=DEVNULL and a
filtered environment: only OS SYSTEMROOT/WINDIR survive. On Linux, LD_LIBRARY_PATH
is reconstructed solely from the trusted base interpreter's lib directory, never
from ambient values; LD_PRELOAD remains excluded. This supports runtimes requiring
a libpython search path, as illustrated by the repository's
[pinned setup-python implementation](https://github.com/actions/setup-python/blob/a26af69be951a213d495a4c3e4e4022e16d87065/src/find-python.ts#L130). HOME, USERPROFILE,
XDG config/cache, APPDATA/LOCALAPPDATA and TMP/TEMP/TMPDIR point to owned controls;
LC_ALL=C. PATH, Python overrides, proxy settings, tokens and registry credentials
are not forwarded. The direct process has a 30-second deadline, stdout admission
cap 2 MiB, stderr cap 64 KiB, polling every at most 10 ms, and kill/wait cleanup on
exception/timeout. Captures reside in the owned home directory, are file-backed, and bounded reads prevent unbounded
RAM use. Disk output can overshoot between polls; there is no OS disk/CPU quota or
process-tree sandbox. Temporary resources and capture failures are sanitized.
Any nonempty stderr makes completeness unavailable, even a benign vendor warning;
raw diagnostics are never forwarded. Operator-controlled system temporary storage
and the installed tool environment are trusted infrastructure, not target inputs.

## Normalization and identity

Exit 0 with no results and exit 1 with results are successful vendor outcomes.
Other exits, inconsistent result/exit combinations, nonempty errors, missing
per-source metrics, malformed/oversized JSON, invalid fields or duplicates fail
with no partial findings. Only exact native relative spellings generated from
selected snapshot paths map back to repository-relative POSIX paths. Absolute,
escaping or unknown output paths are rejected. Rule IDs must be `B` plus three
digits, line/column integers must locate the selected file, and confidence must
be LOW/MEDIUM/HIGH. Confidence does not alter severity. Structured severity maps
exactly LOW→LOW, MEDIUM→MEDIUM, HIGH→HIGH; unknown values never default.

RepoLens rule IDs use `BANDIT-Bnnn`, retaining vendor test identity without copying
Bandit's catalog. Findings have controlled generic descriptions/recommendations
and relative path/line evidence; vendor messages, code, URLs, secrets and timestamps
are discarded. Finding ID is `python-security:BANDIT-Bnnn:` plus SHA-256 of
`Bnnn + NUL + relative_path + NUL + line:column`. Ordering sorts exact finding IDs;
vendor ordering cannot affect it. Locations/tool version/rule changes can change
identity; IDs do not promise cross-version stability. Repeated identical vendor
locations for the same rule are rejected rather than silently merged.

Successful normalized scans yield COMPLETED, with or without findings. Operational,
timeout, diagnostic or validation failures yield sanitized FAILED, distinguished
through typed failure kinds and RepoLens-controlled reasons (timeout, output limit,
invalid output, diagnostics or execution/resources), never raw exception messages. Unsupported tool
availability yields UNSUPPORTED. All unavailable states retain incomplete scoring;
the analyzer selects no weights or penalties. Phase 9's separate explicit
[product policy](../scoring-calibration.md) preserves these states. A completed
static scan or a numeric score cannot establish that a repository is secure or exploitable.
