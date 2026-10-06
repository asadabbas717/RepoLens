# Analyzer-facing repository data

Phase 4 adds FileInventory: immutable, lexically validated, normalized relative
POSIX file path strings. It accepts an iterable, rejects duplicates, absolute
paths, Windows drives, backslashes, parent escapes, NULs and noncanonical forms,
and stores exact case-sensitive sorted paths. It consumes at most 20,001 values
before rejecting inventories above its 20,000-file cap. The same relative-path
validator serves Evidence locations; neither value performs filesystem I/O.

AnalysisContext gains optional inventory, defaulting to None for existing callers.
None means data is unavailable; FileInventory(()) means a successfully completed
inventory with zero eligible files. Invalid input is rejected, not repaired or
silently converted to empty data. The domain continues to depend only on the
standard library, with no acquisition or infrastructure references.

## Composition and lifetime

infrastructure.inventory.snapshot_context(lease, limits) consumes the existing
repository_files traversal while the lease is open. It translates Path values
to relative POSIX strings, validates the bounded inventory and checks lease
lifetime again before returning a context. It publishes nothing until traversal
and validation finish. Traversal failures and limits propagate as acquisition
errors; invalid snapshot data becomes a sanitized AcquisitionError. It neither
acquires a source nor changes ownership or traversal protections.

The snapshot's 20,000-file cap still applies when a caller requests higher
traversal bounds; streaming construction prevents unbounded materialization.
The Phase 2 defaults remain 20,000 visited entries, depth 32 and 2 MiB per file.
Files omitted by size limits, links/reparse points, Git metadata and default
excluded directories are not represented. Git ignore patterns are not parsed.

Snapshots retain only identity and relative strings, never an absolute root,
RepositoryLease, GitRunner, file handle or filesystem service. The immutable
data may be analyzed after lease exit, including after remote workspace deletion:
it grants no capability to reopen the repository. The caller still owns lease
cleanup. Building a new snapshot from a closed lease fails.

## Strength of evidence

This is a snapshot of eligible observed paths, not an atomic filesystem snapshot
or complete list of every physical entry. Phase 2 race limitations remain.
Presence proves neither Git tracking nor commitment, ignore status, file contents,
permissions, execution, or future availability. Absence means only that a path
was not observed in this inventory. In particular a large root .gitignore can
be omitted by the file-size bound; RH001 explicitly qualifies its observation.

Directly constructed FileInventory values are useful pure test inputs. Their
constructor validates lexical shape and bounds, not the physical existence,
file type or exclusion provenance of the caller's claims. Production composition
must use the acquired traversal boundary for those guarantees.

The hygiene analyzer consumes this data without rereading paths. Future content
analysis requires a separate justified bounded read/decoding/lifetime design;
relative strings are not authorization for unchecked later reads. Phase 4 introduced no content capability. Phase 5 now supplies detached bounded
Python text through a separately verified infrastructure boundary; see
[Python source](python-source.md). The path-only builder retains its original
size-omission contract; the Python builder fails on oversized selected sources.
