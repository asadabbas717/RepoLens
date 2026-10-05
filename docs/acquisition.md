# Repository acquisition contract

Phase 2 adds source acquisition and path inventory only. There is no analyzer,
CLI, target-tool adapter, configuration loader or report renderer. The domain
remains unchanged. RepositorySource returns a RepositoryLease within a context;
the lease contains domain display identity, resolved root, source kind, optional
commit SHA and, for GitHub sources, canonical URL.

## Local semantics

Pass a pathlib.Path to RepositorySource.local. The existing directory is resolved
strictly; subdirectories resolve to Git's working-tree root. Input path aliases
and symlinks resolve to their actual directory. Normal and linked Git worktrees
are supported; Git's .git indirection file is legitimate for linked worktrees.
Symlinked/junction Git metadata is rejected. Files, missing/inaccessible paths,
non-Git directories, bare repositories and invalid root metadata are rejected.
Git's ownership protections are preserved; we do not inject safe.directory
exceptions for target repositories. Git metadata must be UTF-8-decodable.

Local sources are live working-tree views, not copied snapshots: tracked,
modified, untracked and Git-ignored files are eligible for inventory unless
RepoLens excludes them. Acquisition never stages, commits, refreshes the index,
or modifies global configuration. Metadata operations prohibit transport and
lazy fetching, so missing partial-clone objects cannot trigger acquisition.

A verified HEAD commit yields its 40- or 64-character lowercase hexadecimal SHA.
An unborn or otherwise unavailable commit returns None when Git's quiet verify
reports no object; other metadata command failures are errors. A SHA is not a
claim that all objects are intact, or that working files match that commit.
This layer does not run fsck or certify repository integrity.

## GitHub URLs

Only HTTPS URLs with the literal authority github.com and exactly owner/repo
path components are accepted. One trailing slash and one .git suffix are
accepted; canonical output is https://github.com/owner/repo.git. Owner names
use ASCII alphanumerics and interior hyphens, length 1..39, without consecutive
hyphens. Repository names use ASCII alphanumerics, underscore, dot and hyphen,
length 1..100; '.', '..', empty names and leading hyphens are rejected.

Reject other schemes/hosts, userinfo, all explicit ports, encoded components,
whitespace/control characters, queries/fragments (including empty markers),
and extra path components such as issues, pull requests or files. Invalid
values are not repeated in diagnostics. Private authentication is unsupported;
URL validation cannot establish whether a syntactically valid repository is
public or exists. Clone errors report that acquisition failed without revealing
raw Git output. Renamed repositories requiring redirects are deliberately
unsupported: use their current canonical location.

## Git execution controls

GitExecution.run(arguments, cwd, timeout) is the narrow external seam. GitRunner
resolves the installed Git executable from trusted PATH to an absolute path;
trusted, maintained Git/OS installations are prerequisites. Application-built
argument arrays are the contract, not arbitrary user-supplied Git commands.

| Control | Purpose |
| --- | --- |
| No shell; user URL follows -- | Separate data from command syntax |
| depth=1, single-branch, no-tags, quiet | Avoid unnecessary history and output |
| Empty init.templateDir and core.hooksPath | Avoid inherited templates and hook execution |
| System/global config disabled; empty HOME/USERPROFILE/XDG home | Isolate aliases, filters, URL rewrites, .netrc and user settings |
| Allowlisted OS environment | Remove ambient Git-dir, askpass, trace, credential and proxy overrides |
| core.fsmonitor=false | Prevent configured filesystem-monitor execution |
| Empty credential.helper; GIT_TERMINAL_PROMPT=0 | No credential helper execution or interactive auth |
| protocol.allow=never; HTTPS enabled only for clone | Reject file, SSH, external and other transports |
| http.followRedirects=false; sslVerify=true | Remain on validated transport authority with TLS verification |
| submodule.recurse=false; no recurse-submodules | Do not fetch or execute submodule acquisition |
| core.protectNTFS/HFS=true | Enable Git's filesystem-name collision protections |
| GIT_OPTIONAL_LOCKS=0 | Avoid optional local lock/write operations |
| GIT_NO_LAZY_FETCH=1; no HTTPS on metadata commands | Keep metadata inspection local, including partial clones |
| GIT_NO_REPLACE_OBJECTS=1 | Verify actual objects rather than replacement refs |

Local config is still read by Git for repository structure; the selected metadata
commands do not execute filters, hooks or project scripts. Remote config is not
downloaded with a Git tree. Clone checkout materializes files with an empty
template and isolated filter configuration; it does not install dependencies,
run tests, import Python, invoke builds or start target scripts. LFS pointers
remain pointers; submodules are not populated. Windows may materialize Git
symlinks as ordinary link-text files depending on Git/OS settings.

Sources: [Git clone options](https://git-scm.com/docs/git-clone),
[Git environment controls](https://git-scm.com/docs/git), and
[Git configuration](https://git-scm.com/docs/git-config). Use a current patched
Git release. The local verification used Git 2.54.0.windows.1.

## Lifetime, output and limits

Git clone has a 120-second timeout; each metadata operation has 10 seconds.
Both streams use anonymous temporary file capture instead of unbounded memory.
The runner checks their size while waiting, stops Git on observed excess of
65,536 bytes per stream, and retains no more than that stdout bound. Stderr is
captured for flow control but never propagated. There is no command/output
logging. Git failures, timeouts and invalid metadata use sanitized messages. Allocation
and cleanup failures for Git control directories and capture files are sanitized
Git errors; raw OS diagnostics are suppressed. Cleanup failure can supersede
an earlier operation error, since cleanup itself did not complete.

Remote workspaces use TemporaryDirectory inside the acquisition context.
Remote metadata must resolve to the exact clone destination, not its parent or
another ancestor. Cleanup is attempted in finally on success, clone failure, timeout, metadata failure and
consumer exceptions; the lease closes before cleanup. Allocation/cleanup failures
are explicit AcquisitionError values, not hidden successes. Consumer exceptions
propagate unchanged when cleanup succeeds. Local context exit closes the lease
without deleting or modifying its repository. Accessing lease.root after exit
raises; a previously copied raw Path cannot be revoked.

Timeout kills/reaps the direct Git process. This is not OS process-tree isolation:
Git transport helpers may outlive their parent in pathological cases, especially
on Windows. OS denial, another process holding files, crashes or forced process
termination can prevent physical cleanup; errors are surfaced when observable.
Output checks impose a soft disk bound with polling overshoot, not a hard quota.
Shallow cloning is not a total disk/network/memory quota and does not limit the
size of the current tree. Do not use this layer as a hostile-process sandbox.

## Inventory and exclusions

repository_files yields relative pathlib.Paths and reads no target contents.
Every entry named exactly .git is excluded at any depth regardless of its type,
including repository-root and nested linked-worktree
indirection files and links/reparse points, without reading its contents.
At any depth, it excludes directories named .git, .venv, venv, env, node_modules, build,
and .venv-* directories,
dist, __pycache__, .pytest_cache, .mypy_cache, .ruff_cache, .uv-cache, htmlcov,
and directories containing a pyvenv.cfg marker. These are RepoLens performance
and safety exclusions, not Git ignore semantics or configurable user patterns.
The integration tests explicitly show that .gitignore alone does not remove a
file from inventory. Working-tree files such as .gitignore, .gitattributes and .gitmodules remain
eligible; the exclusion does not match name prefixes. No ignore
parser/dependency is introduced.

Default bounds are 20,000 visited entries, directory depth 32 (root depth 0),
and 2 MiB per regular file. Entry/depth excess raises TraversalLimitExceeded;
excluded trees are not descended, oversized and nonregular files are omitted.
TraversalLimits allows callers to select positive integer bounds directly,
without implementing configuration-file loading. Directory processing and path
ordering are deterministic for an unchanged tree; an iterator may yield paths
before a later limit error, so callers must not treat partial inventory as complete.

No directory or file symlink is followed; Windows reparse points/junctions are
also excluded. Scheduled directories are checked again before descent, including
root containment; detected directory changes fail rather than producing a clean
empty inventory. Closed leases cannot resume inventory. No file contents are
read for binary classification: a small binary file remains an inventory path.
Future content readers must impose decoding/type/size checks themselves.

Filesystem checks are not atomic. Concurrent renames/replacements can race
between lstat, resolve and scandir; local repositories should remain stable
during use. A returned path is not authorization for a later unchecked read.
Strong hostile-writer isolation requires an OS sandbox or stronger descriptor
based access, outside this phase. Default exclusions can hide legitimate source
directories with those names; future configuration should address this explicitly.

## Errors and verification

AcquisitionError is the base for InvalidSource, GitUnavailable, GitFailed and
TraversalLimitExceeded; GitTimedOut specializes GitFailed. Source input problems
are distinguishable from Git failures without a large per-message hierarchy.

Normal tests do not use live GitHub. Controlled temporary Git repositories test
working-tree resolution, linked worktrees, commit/unborn metadata and inventory.
Fake clone transport tests command shape, ownership and cleanup. Boundary tests
simulate spawn failures, timeout, output excess and secret-bearing diagnostics.
Windows accounts without symlink permission skip the real symlink fixture test;
separate metadata tests always cover symlink/reparse rejection on that platform.
