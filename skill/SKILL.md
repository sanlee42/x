---
name: x
description: Use for the repository architect-to-code loop when the user says "$x", "$x help", "$x architect", "$x status", "$x resume", "$x checkpoint", or "$x close" and wants Codex to show x commands or replace manual architecture discussion, codebase investigation, technical design, implementation, review, fix loop, and merge-back recommendation.
---

# x

`x` is the repository architect-to-code loop. It turns optional root-facing interactions into durable role briefs, proposals, root decisions, and architect intakes, then turns a root/architect room into an accepted Architecture Brief, materialized integration worktree, Technical Contract, Architect Execution Plan, gated lane worktrees, advisory lane heartbeats, implementation/fix attempts, role input packages, code reviews, architect directives and integration reviews, lane integrations, decisions, risks, and a merge-back recommendation.

This is a prompt protocol, not a shell command or slash command. The bundled script is the internal state helper; users should not need to memorize its lower-level commands.

The execution model is:

```text
interaction/discussion -> root decision -> architect intake -> run -> Architect Execution Plan -> readiness gate -> lanes -> lane heartbeats -> attempt -> code review -> architect directives/review -> integrate -> merge-ready gate
```

## Trigger

Use this skill when the user says:

- `$x`, `$x help`, `$x commands`, or `$x ?`
- `$x architect`, `$x architect: <goal>`, or `x architect`
- `$x status`, `$x resume`, `$x checkpoint`, `$x close`
- `$x discussion`, `$x with <role>`, `$x council`, `$x product`, `$x technical`, `$x strategy`, or another configured interaction role for root-facing direction interaction before architecture

Do not use `$x start engineering` as the user-facing entry. `Engineering Loop` is the lower execution layer behind the architect room.

## Fast Root Help

When root says exactly `$x`, `$x help`, `$x commands`, or `$x ?`, answer from this section only. Do not read references, role prompts, repo files, runtime state, or run tools. Do not create or mutate workflow state.

Reply with this concise root-facing command menu:

```text
$x architect[: <goal>]      start or continue architect-to-code work
$x status                   show current x state
$x resume                   resume the current run
$x checkpoint               write a progress checkpoint
$x close                    close with gates and recommendation

$x discussion: <topic>      discuss direction before architecture
$x council: <topic>         synthesize multiple role views
$x with <role>: <question>  ask one configured role
$x product: <question>      product shape and user path
$x technical: <question>    technical boundary and risk
$x strategy: <question>     priority, sequencing, stop conditions
$x challenger: <question>   challenge assumptions
```

Mention that `x_state.py` commands are internal state tools, not root-facing commands.

## Fresh Instruction Reload

At the start of every non-help `$x architect`, `$x discussion`, `$x with <role>`, `$x council`, `$x product`, `$x technical`, `$x strategy`, `$x status`, `$x resume`, `$x checkpoint`, or `$x close` turn, main agent must reread the currently installed `~/.codex/skills/x/SKILL.md` before deciding what to do. Do not rely on stale remembered x workflow rules.

For `$x architect`, execution-oriented `$x resume`, lane work, reviews, integration, or close decisions, main agent must also reread the relevant installed execution role prompts from `~/.codex/agents/` (`architect.toml`, `engineer.toml`, `reviewer.toml`) before using those roles.

For `$x discussion`, `$x with <role>`, `$x council`, `$x product`, `$x technical`, `$x strategy`, `$x challenger`, and other root-facing interaction turns, the role sources are configurable markdown role cards, not global agent prompt files. Main agent must read the configured interaction role cards from runtime state or default skill assets. Do not look for `product.toml`, `technical.toml`, `strategy.toml`, `challenger.toml`, or `councilor.toml` under `~/.codex/agents/`; their absence is expected and is not an install failure.

Newly spawned architect, engineer, and reviewer agents must use the latest installed prompts. If a role agent was spawned before the latest x instruction change, treat its output as potentially stale for changed workflow behavior and use a fresh role package/subagent for decisions affected by the change.

## Required Context

Read these first:

1. `PROJECT_CONSTRAINTS.md`
2. `AGENTS.md`
3. `.x/project/profile.md` if it exists
4. `~/.codex/skills/x/references/engineering-loop-principles.md`
5. `~/.x/projects/<project-key>/ledger/current.md` if it exists
6. The current run file under `~/.x/projects/<project-key>/runs/` when resuming, checking status, checkpointing, or closing

## Reference Loading

Load only the references needed for the current action:

- `$x architect` or execution-oriented `$x resume`: read [`references/architect-room-workflow.md`](references/architect-room-workflow.md) and [`references/gates-and-close-policy.md`](references/gates-and-close-policy.md).
- After `architect-gate` passes or when scheduling lanes/reviewers: read [`references/parallel-execution-policy.md`](references/parallel-execution-policy.md). This preserves aggressive safe parallelism with no fixed default engineer/reviewer cap.
- Before architect integration review or merge-ok decisions: read [`references/architect-review-policy.md`](references/architect-review-policy.md).
- When lane heartbeat, underused parallelism, scope drift, weak verification, repeated fix loops, quota/context risk, or integration-batch signals appear: read [`references/active-architect-observation.md`](references/active-architect-observation.md).
- `$x status`, `$x checkpoint`, `$x close`, and pre-close checks: read [`references/gates-and-close-policy.md`](references/gates-and-close-policy.md).
- Root discussion/interaction, council/合议, strategy, technical, product, challenger, or Acceptance/QA discussion: read [`references/root-interaction-design.md`](references/root-interaction-design.md). Acceptance/QA gate behavior is still future-layer design.

## State Tool

Use the bundled script instead of hand-writing run files:

```bash
python ~/.codex/skills/x/scripts/x_state.py --help
```

The script owns `.x/project/profile.md` in the product repo and runtime markdown state under `~/.x/projects/<project-key>/`, including interactions/discussions, configurable role cards, role briefs, architect intakes, boards, runs, briefs, contracts, execution plans, lanes with heartbeat fields, tasks, attempts, reviews, architect reviews, directives, packages, messages, decisions, ledger, and risks.

## Roles

- `root`: the user; owns direction, final merge authority, irreversible decisions, and explicit merge/push/PR authorization.
- `main agent`: orchestrates, does repo/context intake, writes `.x` state, materializes the integration worktree, starts gated lane worktrees, runs gates, and reports to root.
- `interaction role views`: configurable upper-layer role cards, with default templates for `strategy`, `technical`, `product`, `architect`, and `challenger`; they produce turns and optional formal role briefs for root decision-making and must not manage execution. `product` owns product shape and user path, not Acceptance/QA.
- `architect`: co-creates the Architecture Brief with root, converts accepted direction into technical boundaries, produces the Architect Execution Plan, observes execution, issues architect directives, and performs architect integration review.
- `engineer`: implements only one bounded lane attempt or fix attempt and returns patch evidence.
- `reviewer`: independently reviews patch evidence against the contract, execution plan, lane, task, diff, tests, and repo constraints.

Role package receivers must not spawn child agents or write final ledger state.

All roles load project context before answering: `PROJECT_CONSTRAINTS.md`, `AGENTS.md`, optional `.x/project/profile.md`, then their x package. If they conflict, earlier files win; if the package conflicts with project context, the role reports the conflict instead of guessing.

The root control root normally starts on `master/main`. The run's materialized worktree under `.dev/<scope>` is the integration worktree. Engineer and reviewer role work happens only in lane worktrees under `.dev/<scope>-<lane-id>`.

## Core Boundaries

- No accepted Architecture Brief, no Technical Contract or materialized execution worktree.
- Interaction outputs are advisory until root records a decision; accepted Architect Intakes require an accepted root decision.
- Role briefs and interaction synthesis/proposals must include strongest objection, weakest assumption, and evidence that would change the recommendation.
- No materialized execution worktree and gated Architect Execution Plan, no lane work.
- Reviewer `ready` is code-review evidence only; architect `merge-ok` is required before integration.
- Architect directives are the control surface for pause, resume, replan, continue, parallelism/verification adjustments, requests for evidence, and root decisions.
- Merge-back recommendation is not a merge. Do not merge to `master/main`, push, open PR, or call GitHub unless root explicitly asks.
