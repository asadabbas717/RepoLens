# Security policy

RepoLens is pre-release and has no supported released versions yet.
Report suspected vulnerabilities privately to the repository owner through
GitHub private vulnerability reporting if enabled. If it is unavailable, request
a private contact channel without disclosing exploit details in a public issue.
No response-time guarantee is established yet.

The core safety boundary is static analysis of untrusted input. Target code,
tests, dependency installation and build scripts must never execute by default.
Do not include real credentials in reports or reproductions. Security fixes
require regression tests and review of affected acquisition/tool/rendering paths.

Phase 2 uses isolated Git configuration and bounded capture with no target-code
execution. See [acquisition safety](docs/acquisition.md) for exact controls and
limits. Keep Git patched: its native parsers are part of the trusted boundary.
Local concurrent writers, disk exhaustion, lingering transport helpers and
OS-blocked cleanup are not fully isolated by this layer.
