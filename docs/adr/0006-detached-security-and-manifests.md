# ADR 0006: Detached security tooling and root dependency manifests

Status: accepted for Phase 7.

## Context

Bandit needs files but target directories/configuration are untrusted. Dependency
parsing needs non-Python text, while executing pip against target project inputs
can invoke resolution/build providers. Existing analyzers consume detached data.

## Decision

Keep analyzer code dependent on data and a narrow BanditScan contract. A dedicated
infrastructure BanditRunner materializes bounded Python data into owned temporary
storage and launches the exact reviewed optional installed Bandit using isolated
trusted Python, fixed owned controls, filtered environment and bounded capture.
Infrastructure composition supplies canonical origin metadata solely to reject
temporary storage inside that origin before allocation. No root/lease enters
the domain or Bandit command; detached scans do not require the origin to remain
live. Explicit None is reserved for synthetic data without a target tree.
No general process/plugin framework or GitRunner generalization is justified.

Add optional immutable snapshots of two exact root dependency manifests, each
64 KiB and together at most 128 KiB. Extract Phase 5's existing verified-read code
into a private infrastructure primitive shared by whitelisted snapshot builders;
retain protections and default source behavior. A combined opt-in snapshot uses
one inventory and no partial publication. Pure exact-pin subset parsing does not
resolve dependencies or evaluate host markers.

Defer pip-audit target execution: a safe no-pip exact-pin mode exists, but the
reviewed advisory JSON has no impact severity compatible with Finding. Unsupported
audit states preserve score uncertainty rather than inventing severity/cleanliness.

## Consequences

No mandatory runtime dependencies or target execution are introduced. Trusted
installed tools/plugins remain outside the hostile-target threat boundary; this
is not an OS sandbox. Tool availability/version, syntax, resource/diagnostic and
schema failures cannot masquerade as completed scans. Dependency auditing remains
unavailable even after successful declaration parsing, with that limitation
visible in results. Tool upgrades require compatibility/security review.
