# ADR 0004: immutable path data for initial hygiene analysis

Status: accepted, 2026-10-06

## Context

Phase 3 deliberately supplied only repository display identity to analyzers.
Phase 4's first concrete hygiene rules need file-path presence and spelling,
but need no content reads, filesystem handles or Git commands. Acquisition owns
temporary workspaces and traversal enforces exclusions and bounds.

## Decision

Add a bounded immutable FileInventory to the pure domain and an optional inventory
field to AnalysisContext. A small infrastructure composition function consumes
the existing traversal completely during an open lease, normalizes relative
paths, and publishes only validated data. Domain and analyzer code import no
infrastructure. The Phase 3 analyzer protocol and orchestration remain unchanged.

Use unavailable None separately from an available empty inventory. Propagate
acquisition/traversal failures instead of producing partial or empty contexts.
Bound direct value construction to 20,000 paths as well as enforcing traversal's
existing bounds. Store exact case-sensitive sorted strings, without filesystem
capabilities. Detached data can outlive cleanup but cannot read the former source.

Rejected alternatives: passing raw roots/leases into analyzers would enable
unchecked reads and blur lifetime ownership; making analyzers independently walk
files would bypass traversal guarantees; a universal file-service interface would
anticipate unsupported content-analysis requirements. Neither content reads nor
tracked-file signals are needed for the selected observations.

## Consequences

The initial rules can be deterministic pure computations and tested independently
of platform I/O. Existing identity-only callers remain valid, but hygiene analysis
requires explicitly available inventory. Eligibility omissions and non-atomic
traversal still limit observations; rule language and documentation must state
those limits rather than treating inventory as proof of tracking or complete
physical absence. Future content analysis requires its own justified capability
and decoding/size/lifetime design. This decision introduces no default scoring
policy, plugin framework, target execution or Phase 5 functionality.
