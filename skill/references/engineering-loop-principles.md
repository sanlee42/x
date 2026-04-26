# x Architect-to-Code Loop Principles

- `x` is first an architect-to-code execution loop, not a company operating system.
- Root may start with a clear directive or an open architect room, and keeps final merge authority.
- The active roles are `architect`, `engineer`, and `reviewer`; the main agent orchestrates, writes state, materializes the integration worktree, starts lane worktrees after readiness, and hands bounded packages to roles.
- All roles load repository project context before package-specific instructions.
- Architect co-creation is the execution entry. The Engineering Loop is the lower layer after an accepted Architecture Brief, materialized integration worktree, and gated Architect Execution Plan.
- Optional root-facing interactions may happen before architect execution. Configurable interaction role cards such as `founder`, `cto`, `product-lead`, `market-intelligence`, `gtm`, `challenger`, or project-defined roles produce advisory turns, formal role briefs, and proposals for root decision-making.
- Interaction outputs are not execution authority. Accepted architect intake must be linked to an accepted root decision before it is handed to architect; engineer/reviewer work still requires the normal accepted Architecture Brief, Technical Contract, materialized worktree, gated Architect Execution Plan, and lane gates.
- Every run must move through repo intake, codebase investigation, accepted Architecture Brief, materialized integration worktree, Technical Contract, Architect Execution Plan, readiness gate, lane worktrees, attempt evidence, code review, architect integration review, integration, final verification, and merge-back recommendation.
- If multiple accepted architect intakes exist, main must explicitly choose one with `package --role architect --architect-intake-id <intake-id>` when creating an architect package.
- Do not create a Technical Contract without an accepted Architecture Brief.
- Do not start a lane without an Architect Execution Plan that passes the readiness gate.
- Do not start an implementation attempt without a materialized integration worktree, Technical Contract, Engineer Task, passed Architect Execution Plan, and active lane.
- Do not start review without patch evidence and verification evidence.
- Reviewer `ready` is code-review evidence only; architect `merge-ok` is required before lane integration.
- Do not close accepted while required verification is missing, a planned lane is not integrated, an architect review is not `merge-ok`, or review/risk state has blocking findings.
- Merge-back means recommendation only; do not merge, push, or open PR unless root explicitly asks.
