# Root Interaction Design

This document describes the root-facing interaction layer above the current `x` architect-to-code loop. `discussion` remains acceptable root-facing language and a compatibility command prefix, but the underlying concept is an `interaction`: one or more configurable roles challenge a root thesis, respond to each other, and help main produce a proposal.

The active flow is:

```text
root interaction -> optional role briefs -> interaction summary/proposal -> root decision -> architect intake
  -> Architecture Brief -> Technical Contract -> Architect Execution Plan
  -> lanes -> reviews -> merge-back recommendation
```

The design keeps `x` generic. Product-specific policy still belongs in the target repository's `PROJECT_CONSTRAINTS.md`, `AGENTS.md`, and `.x/project/profile.md`.

Interactions are visible conversations first. In `with`, `joint`, and `council` flows, main must show root the actual role turns as the normal assistant response and must record those turns with speaker and audience metadata. A synthesis/proposal is a later artifact; it must not replace the conversation transcript.

An active interaction is a room, not a one-shot answer. After root starts a room, main keeps routing follow-up natural language into that same room until root explicitly asks to synthesize, decide, close, supersede, or switch rooms. Main may add facilitator notes, but it must not silently collapse back into unlabeled main-agent conversation.

## Intent

Root-facing interaction preserves why a direction was chosen, what tradeoffs were rejected, which assumptions were challenged, what root decided, and what the architect may use as decision-complete input. It must not turn root into the manager of engineer and reviewer sessions.

Root still primarily talks to main in natural language. Main records durable state, reads role cards, generates role packages when useful, synthesizes conflicts, asks root for decisions, and hands accepted architect intake to the existing architect room. The CLI is main's state tool, not root's day-to-day interface.

## Roles

- `root`: final authority for direction, priority, irreversible decisions, and merge authorization.
- `main`: interaction facilitator, state recorder, synthesis/proposal writer, and package creator.
- `strategy`: business value, priority, sequencing, non-goals, and stop conditions.
- `technical`: technical investment, system boundaries, architecture risk, shared platform direction.
- `product`: what to build, user path, v1 feature shape, unacceptable experience, and product tradeoffs.
- `architect`: execution architect. Converts accepted architect intake into Architecture Brief, Technical Contract, Architect Execution Plan, lane integration policy, and root-facing checkpoints.
- `challenger`: optional role view for high-risk or root-requested critique.
- `engineer` and `reviewer`: remain lower-layer execution roles and are not managed by interaction roles.

Interaction role views must not directly create Engineer Tasks, start attempts, manage lanes, assign reviewers, or issue architect directives. They produce turns, optional formal role briefs, and findings for root and architect.

## Role Cards

Roles are configurable markdown cards under runtime state:

```text
~/.x/projects/<project-key>/roles/<role>.md
```

Default role-card templates are provided for `strategy`, `technical`, `product`, `challenger`, and `architect`. These interaction role cards are distinct from the installed execution agent prompts under `~/.codex/agents/`. Council and interaction turns should not expect global `product.toml`, `technical.toml`, `strategy.toml`, `challenger.toml`, or `councilor.toml` files; those roles are loaded from markdown role cards.

Root can ask main to add or modify roles such as `ops`, `data`, `growth`, or `support`; main records them with:

```bash
python ~/.codex/skills/x/scripts/x_state.py role-list
python ~/.codex/skills/x/scripts/x_state.py role-show product
python ~/.codex/skills/x/scripts/x_state.py role-set ops --body-file ops-role.md
```

Each role card should cover responsibilities, use/avoid conditions, inputs to inspect, focus, must-challenge questions, operating posture, evidence standard, handoff value, failure modes, out-of-bounds behavior, and output format. Role outputs may use role-specific formats, but must still include stance, reasons, objections, weakest assumption, evidence that would change the stance, and questions needing root decision.

## Interaction Modes

Use `interaction-start --mode with` when root wants one role view:

```bash
python ~/.codex/skills/x/scripts/x_state.py interaction-start --mode with --title "Technical direction" --agenda "Evaluate reusable read contracts" --participants technical
```

Use `interaction-start --mode joint` when root and several roles should share one meeting record:

```bash
python ~/.codex/skills/x/scripts/x_state.py interaction-start --mode joint --title "Direction alignment" --agenda "Align product and technical direction" --participants strategy technical product
python ~/.codex/skills/x/scripts/x_state.py interaction-turn --interaction-id "<interaction-id>" --actor root --to all --turn-kind statement --body "<root thesis>"
python ~/.codex/skills/x/scripts/x_state.py interaction-turn --interaction-id "<interaction-id>" --actor product --to all --turn-kind viewpoint --body "<product turn>"
```

Use `interaction-start --mode independent` when root needs unpolluted first-pass role views:

```bash
python ~/.codex/skills/x/scripts/x_state.py interaction-start --mode independent --title "Direction choice" --agenda "Compare next initiative options" --participants strategy technical product
python ~/.codex/skills/x/scripts/x_state.py package --role councilor --interaction-id "<interaction-id>" --council-role technical
```

Independent synthesis requires a `ready` role brief for every participant. Unresolved conflicts must be surfaced to root instead of being silently resolved by architect.

The legacy `discussion-start`, `discussion-turn`, and `discussion-synthesize` commands remain compatible wrappers for existing state.

## Durable State

Interaction state is explicit markdown under `~/.x/projects/<project-key>/`:

```text
discussions/<discussion-id>.md
role-briefs/<brief-id>.md
architect-intakes/<intake-id>.md
roles/<role>.md
boards/current.md
```

Existing `decisions/<decision-id>.md` remains the source of root authority.

The interaction file's `Turns` section is the canonical transcript. Each turn includes an actor, turn kind, audience (`To:`), and body. Recording a turn prints the current transcript so root can see the process without running a separate show command. `interaction-show` / `discussion-show` exist for resume/debug reads, not as a required user step.

The transcript renderer includes a room roster:

```text
root: direction owner
main: facilitator and recorder
<role>: active role view
```

Root-facing assistant responses should mirror this shape with labeled lines such as `product -> root:` or `technical -> product/all:`. This prevents the user from losing track of who is speaking.

Precedence:

```text
root decision > accepted architect intake > accepted Architecture Brief > role brief > interaction turn
```

Record meanings:

- `interaction`: agenda/root thesis, participants, compressed turns, linked role briefs, synthesis/proposal, linked architect intake, linked root decisions, and packages.
- `role brief`: one role's formal view: recommendation, rationale, rejected options, risks, decisions needed, implications for architect, and required challenge fields.
- `decision`: root's accepted decision and its consequences, optionally linked to an interaction and architect intake.
- `architect intake`: decision-complete input architect may use to create or revise Architecture Brief and Execution Plan.
- `board`: generated root-facing summary across active interactions, accepted intakes, root decisions, active runs, and risks.

## Challenger Requirement

Challenger thinking is required in every role brief and interaction summary. The required fields are:

- strongest objection
- weakest assumption
- evidence that would change the recommendation

`challenger` is a normal optional role card that can be invited into any interaction. Other roles must still include challenger fields in their formal conclusions.

## Root Board

`board` prints a derived root-facing observation surface:

```bash
python ~/.codex/skills/x/scripts/x_state.py board
python ~/.codex/skills/x/scripts/x_state.py board --write
```

The board is not a second source of truth. It summarizes active interactions, accepted architect intakes, root decisions, active runs, and risks from existing state files.

## Acceptance/QA

Acceptance is still separate from code review, but full Acceptance/QA gates are not implemented in interaction v1.

Reviewer checks:

- code correctness
- contract compliance
- diff scope
- test relevance

Future Acceptance checks:

- product or business intent
- user path
- acceptance evidence
- explainability of unsupported or unresolved cases
- docs, examples, smoke output, or API/report evidence
- residual risk that root must understand

Future Acceptance `changes-requested` must return to architect. Acceptance must not directly assign engineer work. Architect decides whether the response is a fix lane, replan, product scope change, or root decision.

## Roadmap

### Done: Stabilized Execution Foundation

- Lane state is scoped by run.
- `attempt-start` rejects integrated or inactive lanes.
- Latest attempt/review selection handles numbered attempts deterministically.
- Merge-ready requires recorded final verification evidence.
- Mailbox messages provide lightweight role/main coordination for active execution.

### Implemented V1: Root Interaction

- `interaction-start`, `interaction-turn`, `interaction-summarize`, plus compatibility `discussion-start`, `discussion-turn`, `discussion-synthesize`, `role-brief`, `architect-intake`, and `board`.
- Configurable role cards with defaults for `strategy`, `technical`, `product`, `architect`, and `challenger`.
- `package --role councilor --interaction-id ... --council-role ...` for role brief inputs.
- `decision` links to interaction and architect intake.
- Accepted architect intake requires an accepted root decision.
- Architect packages require `--architect-intake-id` when multiple accepted architect intakes exist.
- Closed or superseded interactions reject new turns, role briefs, summaries, decisions, packages, and architect intakes.
- Reserved role names such as `root`, `main`, `engineer`, `reviewer`, and `councilor` cannot be registered as configurable interaction roles.

### Future: Acceptance Gate

- Acceptance plan from product intent and architect intake.
- Acceptance review record.
- Merge-ready gate requires accepted acceptance review when an acceptance plan exists.
- Acceptance `changes-requested` routes back through architect.

### Future: Multi-Direction Board

- Direction-level state across multiple active initiatives.
- Explicit dependencies between directions.
- Close/reopen rules for direction-level state.

## Non-Goals

- Do not introduce external services, GitHub, Notion, or MCP dependencies for this layer.
- Do not make interaction roles permanent requirements for small tasks.
- Do not let upper-layer roles bypass architect and manage engineer/reviewer directly.
- Do not store only raw chat logs as durable state; always produce compressed, role-scoped records.
- Do not add role-specific overlay files until a second real project proves the need.
