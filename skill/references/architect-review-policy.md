# Architect Review Policy

Reviewer `ready` is not integration approval. Architect review must evaluate the lane harder than code review and must not return `merge-ok` without evidence across all relevant dimensions.

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

High-risk lanes require a second architect review pass before integration. High risk includes shared infrastructure, cross-lane contracts, data migrations, auth/security/privacy, public APIs, performance-sensitive paths, or files modified by more than one lane.
