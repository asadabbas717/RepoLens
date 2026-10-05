# Repository hygiene rules

RepositoryHygieneAnalyzer has stable analyzer ID `repository-hygiene` and uses
only FileInventory paths. The immutable HygieneRule catalog contains the two
public compatibility identifiers below, in rule-ID order. Metadata validates
ID shape, severity, category ownership and nonblank title/rationale/remediation.
The catalog is a fixed tuple, not a configurable or generic rule engine.

| ID | Severity | Observation |
| --- | --- | --- |
| RH001 | INFO | No exact root .gitignore path in analyzed inventory |
| RH002 | LOW | Distinct ASCII file paths differ only by letter case |

## RH001: root ignore-policy path observation

Match only the exact root regular-file inventory path `.gitignore`. Nested
`.gitignore`, `.gitignore.example`, `something.gitignore` and `.GITIGNORE` do
not satisfy this particular convention. A root directory named `.gitignore`
is not the required regular-file inventory entry. No contents are read or parsed.

An emitted finding says only that this path was not observed in the eligible
inventory. Evidence is repository-level, with no invented filename or line.
The recommendation is to review whether a shared root ignore policy would help
collaborators. Nested, local or global policies can be intentional, and tiny or
artifact-only repositories may need no root policy. Omitted oversized files and
links may exist physically. This advisory therefore uses INFO, with no deduction
under the existing scoring contract, rather than claiming an engineering defect.

It does not prove ignored/untracked/tracked/committed status, or assert that no
ignore policy exists. A matching filename satisfies the path observation even
if empty or containing unusable policy; effectiveness is outside this rule.

Finding ID is exactly `repository-hygiene:RH001`.

## RH002: ASCII case-collision groups

For entirely ASCII relative file paths, group distinct spellings by their ASCII
lowercase full path. Groups with at least two paths produce one finding each.
For example `src/File` and `src/file`, or `Src/file` and `src/file`, qualify.
Different directories, extensions, suffixes and distinct full lowercase spellings
do not. Exact duplicates are invalid inventory, not separate collision findings.

Evidence lists the group's actual relative file paths, canonically ordered,
without file contents or fabricated lines. This proves a collision of ASCII
spellings in the inventory. It warns only of potential cross-platform checkout
difficulties on case-insensitive filesystems. It does not claim those paths are
committed, currently broken, or unsupported on a case-sensitive host. If such
checkout portability is intended, rename paths to differ by more than letter case.
LOW reflects this limited, reversible portability risk rather than a security or
runtime-correctness issue. Intentional case-sensitive-only repositories may retain
these paths knowingly.

Unicode paths are excluded from this rule: Unicode case folding does not establish
filesystem equivalence. Directory-only collisions with different full file paths
(such as `Src/a` and `src/b`), Unicode normalization, trailing spaces/dots, reserved
names, omitted files and other platform filename restrictions are not assessed.
The rule deliberately implements no comprehensive portability or security scan.

Finding ID is `repository-hygiene:RH002:` followed by the full hexadecimal SHA-256
of the ASCII lowercase collision key. This deterministic occurrence identity
contains no absolute host root, temporary-directory path, timestamp or randomness.
Adding another spelling to the same group does not change its finding ID.
Final findings are sorted by exact finding ID, not filesystem enumeration order.

## Lifecycle and integration

An available inventory always yields COMPLETED, including zero findings. Missing
inventory yields FAILED with the fixed safe reason "File inventory is unavailable".
Acquisition/traversal failures prevent context publication before analysis; they
never become fake empty success. No SKIPPED/UNSUPPORTED/NOT_APPLICABLE outcome is
invented for this simple universally observable inventory contract.

Register the analyzer explicitly with AnalyzerPlan and pass snapshot_context's
result to execute_analyzers. Orchestration ownership and exception isolation are
unchanged. AnalysisReport composition still requires an explicit scoring policy;
no product penalties, weights, calibrated scores or default registration are added.
All policies in the test suite are synthetic.

The analyzer builds in-memory membership and collision indexes over the bounded
inventory, with canonical sorting for deterministic output. It does not rewalk
the filesystem, execute target code, run Git, install dependencies, read target
configuration or invoke external tools. Readme quality, licensing interpretation,
test analysis, security and CI checks are outside these two rules.
