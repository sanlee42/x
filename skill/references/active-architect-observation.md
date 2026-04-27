# Active Architect Observation

During execution, architect should act as an active control-plane observer, not only a final integration reviewer. Main agent should generate an architect package for observation when any of these signals appear:

- lane heartbeat is missing, stale, blocked, or contradictory
- safe parallelism is underused or ready lanes are not launched
- lane activity suggests scope drift, boundary drift, or wrong sequencing
- multiple lanes touch shared files, modules, interfaces, schemas, or external systems
- verification, product acceptance, rollback, or final verification evidence looks weak
- repeated review/fix loops suggest contract ambiguity or plan mismatch
- the first non-ready review points to wrong abstraction, public surface gaps, shared-interface uncertainty, or branchy conditional patching in shared logic
- an engineer fix plan adds narrow `if/else` patches around a public surface where a shared abstraction should probably exist
- open mailbox messages indicate cross-lane requests, interface changes, blockers, directives, or artifact handoffs that need control-plane awareness
- quota/context risk appears and main needs to checkpoint instead of spawning more work
- a large integration batch is about to proceed

Architect observation output may recommend `continue`, `parallelism-adjustment`, `verification-adjustment`, `pause-lane`, `resume-lane`, `replan`, `root-decision`, or `request-more-evidence`.

Three non-ready reviews for the same task are not an execution loop; they are evidence that the contract, lane boundary, or abstraction is wrong. Architect observation must return a `replan` directive or an explicit root-decision request before any further engineering work.

If execution should change, main records it as an `architect-directive` with concrete instructions and acceptance criteria. `parallelism-adjustment`, `verification-adjustment`, and `request-more-evidence` mean main should record and act on the observation without gating lower lane work or merge-ready by default. Use `pause-lane`, `replan`, or `root-decision` when the observation must block lane work, force a new gated plan, or require root input before accepted close. Architect still does not manage engineer/reviewer sessions directly.

Architect observation packages include the open mailbox summary. Treat mailbox messages as coordination signals; use architect directives for control changes that should gate lane work or accepted close.
