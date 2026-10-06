# Bounded Python source data

Phase 5 introduces detached PythonSourceFile(path, text) and PythonSourceSnapshot
values in the pure domain. Paths use the existing normalized relative POSIX
validation, now shared from domain.paths. Source paths must also be UTF-8
representable for stable occurrence
identities; undecodable filesystem-name surrogate escapes are rejected explicitly.
Source text is omitted from dataclass
representations; findings/errors never copy source lines, literals or decoding
diagnostics. Source text is still sensitive data accessible to the trusted analyzer,
not a redacted document or filesystem capability.

AnalysisContext gains optional python_sources, default None. Available source
paths must exactly match inventory paths ending in the selected suffixes. A
partial, duplicate, extra or malformed source set is rejected. Existing identity
and path-only contexts remain valid; None source data is unavailable rather than
an empty available set. No infrastructure types or handles enter the domain.

## Selection and limits

Select exact lowercase `.py` and `.pyi` suffixes, including hidden filenames with
those endings. `.PY`, `.PYI`, `.py.old`, notebooks and extensionless scripts are
not selected. There is no content sniffing or language inference.

| Hard ceiling | Value |
| --- | --- |
| Raw bytes per selected file | 256 KiB |
| UTF-8 representation per decoded file | 256 KiB |
| Selected source files | 512 |
| Aggregate raw bytes | 4 MiB |
| Aggregate decoded UTF-8 representation | 4 MiB |

PythonSourceLimits permits smaller positive bounds, never larger than these hard
ceilings. Direct domain construction also enforces text/file-count/aggregate
ceilings. This bounds input, not total Python heap, AST expansion, CPU time or
process resources. Decode buffers and AST objects require additional memory.

snapshot_python_context inventories once under an open lease, then reads selected
files in canonical path order. It reuses the bounded Phase 2 metadata walk
(repository_file_sizes), preserving entry/depth bounds, directory exclusions,
Git metadata omission and link/reparse protections. It does not rewalk for rules.
Every eligible Python candidate is admitted or rejected before source reads;
oversized selected files fail, including files larger than Phase 2's 2 MiB filter.
Non-Python oversize files retain their normal omission behavior.

repository_files still applies its original size filter for path-only consumers.
The Python snapshot additionally respects a caller's stricter traversal file-size
bound and fails if a selected source exceeds it. Excluded trees and initially
linked/reparse files are outside the eligible scope, not unsupported partial
source. Failed traversal, count/aggregate excess and read/decode failures publish
no context. The existing AcquisitionError family reports sanitized failures;
there is no fallback to a fake empty or successful partial snapshot.

## Read and encoding boundary

Only infrastructure reads bytes. It checks normalized locations, root containment,
every path component for links/reparse points, parent-directory shape/exclusions,
regular-file type, size and lease lifetime. It opens read-only with no-follow,
nonblocking and binary flags where the platform provides them, validates opened
descriptor identity/size/modification time against the checked file, and reads
at most the per-file ceiling plus one detection byte. It then checks descriptor
and pathname metadata again and requires the inventory-admitted byte size.
Descriptors close in finally on success or failure. Windows ctime can differ
between path and descriptor queries for an unchanged file, so comparison uses
device/inode, size and modification time instead.

Bounded bytes are decoded using tokenize.detect_encoding for the Python BOM and
first/two-line coding-cookie rules, followed by strict decoding. Default encoding
is UTF-8; a UTF-8 BOM is removed. Supported declared text codecs use the trusted
runtime's standard-library codec machinery. Unknown codecs, BOM/cookie conflicts
and invalid bytes produce fixed sanitized acquisition errors. UTF-8 text size is
checked after decoding too, so an expanding encoding cannot silently exceed the
snapshot budget. This performs no imports of target modules or target plugins.

References: [Python encoding detection](https://docs.python.org/3.13/library/tokenize.html#tokenize.detect_encoding),
[AST grammar selection](https://docs.python.org/3.14/library/ast.html#ast.parse).

## Lifetime and limitations

Lease lifetime is checked before reads, around path verification and before
publication. The detached inventory and text may outlive local lease closure or
remote cleanup, but cannot reopen the source. Callers still own acquisition.

Checks are not atomic across a concurrently modified tree. A same-size regular
replacement settled before its read can be accepted as current data. Detectable
identity/type/size or modification-time changes during reads fail, but adversarial
changes that evade metadata checks, intermediate directory races and hard-link
provenance cannot be fully excluded without stronger OS isolation. No filesystem
sandbox, atomic repository snapshot or hard CPU/memory quota is claimed.

AST parsing remains an in-process trusted-runtime operation. Input ceilings and
handled resource errors do not guarantee survival against every pathological
parser input or native-runtime fault. See the [Python rules](rules/python.md)
for fixed-grammar outcomes and the narrow strength of structural findings.
