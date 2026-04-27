# Architect Review Policy

Reviewer `ready` is not integration approval. Architect review must evaluate the lane harder than code review and must not return `merge-ok` without evidence across all relevant dimensions.

Architect review is architect-role work. Main should spawn an architect subagent with the lane, code review, verification, risk, and integration context, then record the architect's returned review. Main may reject incomplete or contradictory output, but must not substitute its own deep architecture judgment for the architect role.

## Review Dimensions

- architecture fit: respects the accepted brief, technical contract, execution plan, boundaries, ownership, dependency direction, and integration order
- code abstraction: uses the right local abstractions, avoids premature/generalized abstractions, avoids duplication that will matter, and keeps interfaces coherent
- maintainability: minimizes cognitive load, keeps names and module boundaries clear, keeps changes reversible, and avoids hidden coupling
- performance and scalability: avoids avoidable hot-path cost, excess I/O, unnecessary allocations, N+1 behavior, blocking work, or unbounded growth
- correctness and edge cases: handles error paths, empty/large inputs, concurrency where relevant, idempotency, and rollback/retry behavior
- security and privacy: avoids leaking secrets/data, validates trust boundaries, and preserves auth/permission assumptions
- observability and operability: leaves enough logs/errors/metrics/state evidence for support without noisy instrumentation
- test and verification quality: verification matches risk, includes meaningful negative/regression coverage where appropriate, and does not rely only on happy-path inspection
- product acceptance: satisfies the user-visible workflow, acceptance criteria, copy/API behavior, backwards compatibility, and migration/rollout expectations
- integration risk: identifies cross-lane conflicts, shared files, sequencing risk, and whether final verification needs extra coverage

## Outcomes

- `merge-ok`: all relevant dimensions pass or are explicitly not applicable with evidence
- `changes-requested`: issue is fixable within the lane
- `blocked`: evidence is missing or dependency is unresolved
- `replan`: implementation reveals that the execution plan or contract is wrong

Lane risk is declared by `Risk Level` `standard`, `high`, or `critical` in the gated execution plan. Critical risk is mandatory for public output/schema, shared interfaces/helpers, cross-lane contracts, data migrations, auth/security/privacy, public APIs, performance-sensitive paths, shared files, or files/modules modified by more than one lane.

Standard lanes enter the integration-ready queue after a ready native code review. Standard lanes selected for sampling require one latest-attempt `merge-ok`; unsampled standard lanes do not. High-risk lanes require one latest-attempt `merge-ok`. Critical lanes require two distinct architect review records with `Recommendation: merge-ok`, and both records must link the latest lane attempt. Older merge-ok reviews do not count after a fix attempt starts.
