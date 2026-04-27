# Gates and Close Policy

Use this for `$x status`, `$x resume`, `$x checkpoint`, `$x close`, and any pre-integration or pre-close decision.

## Status and Resume

For `x status`, do not re-plan. Read state only:

```bash
python ~/.codex/skills/x/scripts/x_state.py status
```

`status` includes a computed `Lane Heartbeats` section for the selected run. Attention labels mean: `blocker` has a current blocker, `no-heartbeat` has no lane update yet, `stale` is older than 60 minutes, and `none` has no heartbeat attention signal.

`status` also includes an `Open Mailbox` section for the selected run. Open mailbox messages are coordination context, not gates by themselves.

For `x doctor`, check project binding, active runs, and local install diagnostics:

```bash
python ~/.codex/skills/x/scripts/x_state.py doctor
```

For `x resume`, continue from `Next Operating Actions` / `Next Action`. If multiple active runs exist in the control root, pass `--run-id`:

```bash
python ~/.codex/skills/x/scripts/x_state.py resume --run-id "<run-id>"
```

Before resumed work, use the resume output to choose the next phase and checkpoint after finishing that phase.

## Checkpoint and Close

For `x checkpoint`, compress current state:

```bash
python ~/.codex/skills/x/scripts/x_state.py checkpoint --run-id "<run-id>" --summary "<summary>" --next-action "<next action>"
```

For `x close --status accepted`, the merge-ready gate must pass first:

```bash
python ~/.codex/skills/x/scripts/x_state.py close --run-id "<run-id>" --status accepted --summary "<merge-back recommendation>"
```

After accepted close or when cleaning up a completed run, lane worktrees may be removed only through an explicit cleanup dry-run followed by `--apply`:

```bash
python ~/.codex/skills/x/scripts/x_state.py cleanup-worktrees --run-id "<run-id>"
python ~/.codex/skills/x/scripts/x_state.py cleanup-worktrees --run-id "<run-id>" --apply
```

Cleanup v1 only removes lane worktrees whose lane state is `Integrated: yes`, lane `Status: integrated`, path exists, git status is clean, and git common dir matches the run. It does not remove the integration worktree and does not remove active, paused, blocked, dirty, missing, or mismatched lane worktrees.

## Gates

- No accepted Architecture Brief, no materialized integration worktree.
- No accepted Architecture Brief, no Technical Contract.
- No materialized integration worktree, no Architect Execution Plan.
- No Architect Execution Plan, no lane.
- Unresolved `TBD`, `figure out`, `use best judgment`, or `decide later` language fails the architect readiness gate unless explicitly recorded as a root decision.
- No passed architect readiness gate, no lane-start, engineer/reviewer package, attempt, integration, merge-ready gate, or accepted close.
- No Technical Contract, no Engineer Task.
- No Engineer Task and active lane, no attempt.
- No attempt, no engineer package.
- No attempt result / patch evidence, no reviewer package.
- `review --recommendation ready` cannot include blocking findings.
- Review severity order is `p0 > p1 > p2 > p3 > none`; `ready` cannot use `p0`, `p1`, or `p2`.
- Native review output that cannot be normalized must use `Escalation Reason: unstructured-native-output` and must not auto-start a fix attempt.
- Reviewer `ready` alone does not allow integration.
- No architect `merge-ok`, no `integrate`; architect `merge-ok` requires evidence across architecture fit, abstraction, maintainability, performance, correctness, security/privacy, observability, verification, product acceptance, and integration risk.
- Unsampled standard lanes may integrate after ready review. Standard lanes selected for sampling and high-risk lanes require one `merge-ok`; critical lanes require two distinct `merge-ok` architect review records linked to the latest attempt before `integrate` or `gate --mode merge-ready` can pass. Older reviews do not count after a fix attempt starts.
- Architect `changes-requested` starts a lane fix loop; architect `replan` blocks lane work until a new plan is accepted and gated.
- Open architect `pause-lane` directives block new attempts, role packages, architect review, and integration for that lane until `resume-lane`.
- Open architect `replan` directives mark the plan `replan-required` and block lower lane work until a new plan passes readiness.
- Open architect `root-decision` directives block accepted close until root records or clears the decision.
- Blocking or unresolved review means no accepted close.
- Any planned lane without a latest ready reviewed attempt, architect `merge-ok`, integration, green final verification status, and recorded final verification evidence fails the merge-ready gate.
- Three non-ready reviews for the same task require architect/root loopback.
- Missing required verification means no merge-ready gate.
- Merge-back recommendation is not a merge. Root must explicitly authorize merge, push, PR, or GitHub integration.
