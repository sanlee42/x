---
name: x
description: Use for the repository architect-to-code loop when the user says "$x", "$x help", "$x architect", "$x status", "$x resume", "$x checkpoint", or "$x close" and wants Codex to show x commands or replace manual architecture direction work, codebase investigation, technical design, implementation, review, fix loop, and merge-back recommendation.
---

# x

`x` is the repository architect-to-code loop. It turns optional root-facing council rooms into durable participant briefs, proposals, root decisions, and architect intakes, then turns a root/architect room into an accepted Architecture Brief, materialized integration worktree, Technical Contract, Architect Execution Plan, gated lane worktrees, advisory lane heartbeats, implementation/fix attempts, input packages, code reviews, architect directives and integration reviews, lane integrations, decisions, risks, and a merge-back recommendation.

This is a prompt protocol, not a shell command or slash command. The bundled script is the internal state helper; users should not need to memorize its lower-level commands.

The execution model is:

```text
interaction -> root decision -> architect intake -> run -> Architect Execution Plan -> readiness gate -> lanes -> lane heartbeats -> attempt -> code review -> architect directives/review -> integrate -> merge-ready gate
```

## Trigger

Use this skill when the user says:

- `$x`, `$x help`, `$x commands`, or `$x ?`
- `$x architect`, `$x architect: <goal>`, or `x architect`
- `$x status`, `$x resume`, `$x checkpoint`, `$x close`
- `$x council` or `$x council with <participant1>, <participant2>` for root-facing direction rooms before architecture

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

$x council: <topic>         company council with founder/cto/product-lead/market-intelligence/gtm/challenger
$x council with <participants>: <topic> discuss with selected participants
```

Mention that `x_state.py` commands are internal state tools, not root-facing commands.

## Fresh Instruction Reload

At the start of every non-help `$x architect`, `$x council`, `$x council with <participants>`, `$x status`, `$x resume`, `$x checkpoint`, or `$x close` turn, main agent must reread the currently installed `~/.codex/skills/x/SKILL.md` before deciding what to do. Do not rely on stale remembered x workflow rules.

For `$x architect`, execution-oriented `$x resume`, lane work, reviews, integration, or close decisions, main agent must also reread the relevant installed execution role prompts from `~/.codex/agents/` (`architect.toml`, `engineer.toml`, `reviewer.toml`) before using those roles.

For `$x council` and `$x council with <participants>`, the participant views are configurable markdown participant cards, not global agent prompt files. Main agent must read the configured participant cards from runtime state or default skill assets. Do not look for `founder.toml`, `cto.toml`, `product-lead.toml`, `market-intelligence.toml`, `gtm.toml`, `challenger.toml`, or `councilor.toml` under `~/.codex/agents/`; their absence is expected and is not an install failure.

Newly spawned architect, engineer, and reviewer agents must use the latest installed prompts. If a role agent was spawned before the latest x instruction change, treat its output as potentially stale for changed workflow behavior and use a fresh role package/subagent for decisions affected by the change.

## Interaction Room Continuity

Once root starts a `$x council` room, main must treat it as an active room until root explicitly asks to synthesize, decide, close, supersede, or switch rooms.

If root sends a follow-up in natural language and exactly one active interaction exists, continue that interaction even if root omits `$x`. If multiple active interactions exist, ask which interaction to continue before answering as participants.

Every room response must keep identities visible:

```text
Room: <interaction-id>
Participants: root, main, founder, cto, ...
Speaking:
- founder -> root: ...
- cto -> founder/all: ...
- main -> root: facilitator note only, if needed.
```

Do not answer a room turn as an undifferentiated main agent unless root asks for main-only logistics. In council rooms, include named participant turns in the normal assistant reply, then record the visible turns with `interaction-turn --actor <participant> --to <root|participant|all>`. Summary/synthesis is a separate explicit step and must not replace participant turns.

## Council Depth Contract

`$x council` is a structured working room, not a one-round summary. Unless root explicitly asks for a quick take, main must make the council useful enough that root would not need to open a separate freeform session to get real debate.

For the first substantive council response on a topic, use this shape:

```text
Room: <interaction-id>
Participants: root, main, founder, cto, ...

Decision Frame:
- what root is actually deciding
- what would make the answer change

Round 1 - Initial Positions:
- <participant> -> root: stance, reasons, evidence/assumptions, risk, decision implication

Round 2 - Cross-Examination:
- <participant> -> <participant/all>: named challenge to a specific claim
- <participant> -> <participant/all>: response or refinement

Options:
- A: ...
- B: ...
- C: ...

Evidence Needed:
- test/interview/data that would change the recommendation

Main:
- concise facilitator note only; no final decision unless root asks to synthesize or decide
```

Depth requirements:

- Do not collapse participants into one-paragraph takes followed by a conclusion.
- Separate facts, assumptions, judgments, and open evidence gaps.
- Make `challenger` attack the strongest live claim by name, not just add a generic warning.
- Make `market-intelligence` distinguish known facts from assumptions and missing customer/competitor proof.
- Make `cto`, `product-lead`, and `gtm` respond to constraints raised by other participants when those constraints materially affect the decision.
- Do not write `Room Essence` or treat the room as resolved until root asks to synthesize, decide, close, or convert to architect intake.

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
- Root council/合议 room or Acceptance/QA room: read [`references/root-interaction-design.md`](references/root-interaction-design.md). Acceptance/QA gate behavior is still future-layer design.

## State Tool

Use the bundled script instead of hand-writing run files:

```bash
python ~/.codex/skills/x/scripts/x_state.py --help
```

The script owns `.x/project/profile.md` in the product repo and runtime markdown state under `~/.x/projects/<project-key>/`, including interactions, configurable participant cards, participant briefs, architect intakes, boards, runs, briefs, contracts, execution plans, lanes with heartbeat fields, tasks, attempts, reviews, architect reviews, directives, packages, messages, decisions, ledger, and risks.

## Roles

- `root`: the user; owns direction, final merge authority, irreversible decisions, and explicit merge/push/PR authorization.
- `main agent`: orchestrates, does repo/context intake, writes `.x` state, materializes the integration worktree, starts gated lane worktrees, runs gates, performs mechanical lane integration, and reports to root.
- `council participant views`: configurable upper-layer participant cards, with default templates for `founder`, `cto`, `product-lead`, `market-intelligence`, `gtm`, and `challenger`; they produce turns and optional formal participant briefs for root decision-making and must not manage execution. `product-lead` owns product shape and user path, not Acceptance/QA. `market-intelligence` provides external facts and does not decide. `gtm` owns channel, sales, launch, conversion, pricing, and packaging actions.
- `architect`: co-creates the Architecture Brief with root, converts accepted direction into technical boundaries, produces the Architect Execution Plan, observes execution, issues architect directives, and performs architect integration review.
- `engineer`: implements only one bounded lane attempt or fix attempt and returns patch evidence.
- `reviewer`: independently reviews patch evidence against the contract, execution plan, lane, task, diff, tests, and repo constraints.

Role package receivers must not spawn child agents or write final ledger state.

Main must not act as architect, engineer, or reviewer during normal x execution. Main may do sanity checks for missing fields, contradictions, repo-rule conflicts, and gate failures, but architecture/design judgment, Technical Contract direction, lane risk classification, and architect `merge-ok` decisions belong to the architect role/subagent. Main routes those decisions to architect and records the resulting durable state.

Native reviewer execution must run in a reviewer role/subagent, not inline in main during normal execution. Main records attempt evidence, spawns the reviewer subagent with the native reviewer command/package context, then continues orchestration while the reviewer runs `codex review --uncommitted`.
Native reviewer execution is background work. Main must not run auto/native review in the main process, and must not sit idle waiting on a reviewer unless the next critical-path action is blocked on that exact review result. The reviewer returns a structured result; main only records the normalized Review and routes loopback state.

Architect integration review and architect observation should run in an architect role/subagent whenever architect judgment is required. They are background control-plane work by default. Main should spawn architect with the lane/review/verification summary, continue safe independent orchestration, and write the returned `architect-review` or `architect-directive` state when the result arrives. Main must not immediately wait on an architect subagent unless the architect result is the current critical-path blocker and there is no other safe lane/review/package/state work to do.

All roles load project context before answering: `PROJECT_CONSTRAINTS.md`, `AGENTS.md`, optional `.x/project/profile.md`, then their x package. If they conflict, earlier files win; if the package conflicts with project context, the role reports the conflict instead of guessing.

The root control root normally starts on `master/main`. The run's materialized worktree under `.dev/<scope>` is the integration worktree. Engineer and reviewer role work happens only in lane worktrees under `.dev/<scope>-<lane-id>`.

## Core Boundaries

- No accepted Architecture Brief, no Technical Contract or materialized execution worktree.
- Main owns orchestration and state, not architecture/design authorship. If architecture input is needed, main spawns architect and records architect output instead of inventing the direction.
- Interaction outputs are advisory until root records a decision; accepted Architect Intakes require an accepted root decision.
- Root-facing council rooms are visible conversations first. Main must show the actual participant turns to root in the normal assistant reply and record them with `interaction-turn`; synthesis/proposal is a later step and must not replace the visible exchange.
- Every recorded interaction turn must have a clear speaker and audience. Use `interaction-turn --actor <participant> --to <root|participant|all>` so participants know whether they are answering root, another participant, or the whole room.
- Participant briefs must include strongest objection, weakest assumption, and evidence that would change the recommendation.
- Interaction synthesis/proposals must write a `Room Essence` inside the existing `Synthesis` section with core judgment, recommended direction, key arguments, objections/conflicts, rejected options, weakest assumptions, evidence to change, open root decisions, and document-use notes. This is the shared advisory source for later BRD, PRD, strategy, sales, or architect-intake writing; it is not a new workflow or execution authority.
- No materialized execution worktree and gated Architect Execution Plan, no lane work.
- Reviewer `ready` is code-review evidence only; architect `merge-ok` is required before integration.
- Engineer/reviewer role packages must be narrow. Do not feed every role full run context by default; package only the linked diff/evidence, contract summary, lane/task scope, verification, and loopback context needed for that role.
- The first non-ready review may produce a bounded engineer fix only when there is no architecture, contract, abstraction, shared-surface, or cross-lane signal. The second non-ready review for the same task requires architect loopback. The third non-ready review for the same task forces architect replan; do not keep patching the lane.
- If a review or fix approach exposes a wrong abstraction, public surface gap, repeated conditional patching, or shared-interface uncertainty, involve architect before the next engineer fix attempt, even if it is the first non-ready review.
- Architect directives are the control surface for pause, resume, replan, continue, parallelism/verification adjustments, requests for evidence, and root decisions.
- Merge-back recommendation is not a merge. Do not merge to `master/main`, push, open PR, or call GitHub unless root explicitly asks.
