# Parallel Execution Policy

Default to aggressive safe parallelism. After `architect-gate` passes, main agent should fill the ready-lane queue instead of advancing one lane at a time. There is no fixed default cap on engineer or reviewer subagents; root/project instructions may set one, but otherwise main should launch every safe ready lane.

- Batch-start all dependency-satisfied, unpaused, unblocked, non-conflicting lanes.
- Do not serialize independent lanes merely because later review or integration gates are serial.
- Spawn reviewer roles as soon as attempt evidence exists.
- Keep each lane in its own worktree, attempt, package, and heartbeat; never let two engineers share one lane attempt.
- Use `mailbox-send` for cross-lane coordination events that need architect visibility, especially `artifact-ready`, `interface-change`, `blocker`, `request`, and `response`.
- Treat architect-declared concurrent lane groups as safe to launch together.
- Treat architect-declared serial-only lanes, shared-file conflict risks, open blockers, open pause/replan directives, and unmet dependencies as reasons not to launch that lane yet.
- Integration remains serial according to Integration Order unless root explicitly asks for a different merge strategy.
- If the ready set is very large, launch all safe lanes unless root/project instructions set a cap; if quota or context risk appears, stop spawning new work, collect completed subagent results, write lane heartbeats, checkpoint, and leave a resume-ready next action.
- After collecting any completed architect, engineer, or reviewer result and writing the corresponding x state, close that completed agent thread. If thread close fails, record the operational risk in checkpoint or heartbeat state and continue from the durable x state.
