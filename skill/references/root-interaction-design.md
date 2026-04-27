# Root Interaction Design

This document describes the root-facing council room layer above the current `x` architect-to-code loop. The only root-facing room entry is `$x council`; the underlying durable record is an `interaction`.

The active flow is:

```text
council room -> optional participant briefs -> Room Essence -> root decision -> architect intake
  -> Architecture Brief -> Technical Contract -> Architect Execution Plan
  -> lanes -> reviews -> merge-back recommendation
```

The design keeps `x` generic. Product-specific policy still belongs in the target repository's `PROJECT_CONSTRAINTS.md`, `AGENTS.md`, and `.x/project/profile.md`.

## Intent

Council rooms preserve why a direction was chosen, what tradeoffs were rejected, which assumptions were challenged, what root decided, and what the architect may use as decision-complete input. They must not turn root into the manager of engineer and reviewer sessions.

Root still primarily talks to main in natural language. Main records durable state, reads participant cards, generates participant packages when useful, synthesizes conflicts, asks root for decisions, and hands accepted architect intake to the existing architect room. The CLI is main's state tool, not root's day-to-day interface.

## Participants

- `root`: final authority for direction, priority, irreversible decisions, and merge authorization.
- `main`: interaction facilitator, state recorder, synthesis/proposal writer, and package creator.
- `founder`: company-level judgment, focus, opportunity cost, credibility, and root-owned tradeoffs.
- `cto`: company-level technical credibility, system boundary, delivery risk, and operability implications.
- `product-lead`: product leadership view for customer problem, v1 promise, product claims, and document-safe scope.
- `market-intelligence`: competitors, substitutes, market structure, customer evidence, pricing and packaging facts, and category dynamics. It informs the room; it does not decide.
- `gtm`: channel, sales motion, launch path, conversion, pricing action, packaging implications, and adoption risk.
- `challenger`: critique, pre-mortem, weakest assumptions, and disconfirming evidence.

Council participant views must not directly create Engineer Tasks, start attempts, manage lanes, assign reviewers, or issue architect directives. They produce visible turns, optional formal participant briefs, and findings for root and architect.

## Participant Cards

Participants are configurable markdown cards under runtime state:

```text
~/.x/projects/<project-key>/participants/<participant>.md
```

Default participant-card templates are provided for `founder`, `cto`, `product-lead`, `market-intelligence`, `gtm`, and `challenger`. These cards are distinct from installed execution agent prompts under `~/.codex/agents/`; council turns should not expect participant `.toml` files.

Main can inspect or configure participant cards with:

```bash
python ~/.codex/skills/x/scripts/x_state.py participant-list
python ~/.codex/skills/x/scripts/x_state.py participant-show product-lead
python ~/.codex/skills/x/scripts/x_state.py participant-set ops --body-file ops-participant.md
```

Participant cards should cover responsibilities, use/avoid conditions, inputs to inspect, focus, must-challenge questions, operating posture, evidence standard, handoff value, failure modes, out-of-bounds behavior, and output format.

## Interaction Modes

Root-facing `$x council: <topic>` uses the default participant roster:

```bash
python ~/.codex/skills/x/scripts/x_state.py interaction-start --mode joint --title "Company council" --agenda "<topic>" --participants council
```

The `council` preset expands to `founder`, `cto`, `product-lead`, `market-intelligence`, `gtm`, and `challenger`. It is only a room roster shortcut and does not create a separate workflow or grant company participants execution authority. `council` is reserved and cannot be registered as a participant.

Root-facing `$x council with founder, gtm, challenger: <topic>` uses explicit participants:

```bash
python ~/.codex/skills/x/scripts/x_state.py interaction-start --mode joint --title "Selected council" --agenda "<topic>" --participants founder gtm challenger
```

Single-participant rooms use the same syntax and mode:

```bash
python ~/.codex/skills/x/scripts/x_state.py interaction-start --mode joint --title "CTO direction" --agenda "<question>" --participants cto
```

Use `interaction-start --mode independent` only when root needs unpolluted first-pass participant views:

```bash
python ~/.codex/skills/x/scripts/x_state.py interaction-start --mode independent --title "Direction choice" --agenda "<topic>" --participants founder cto product-lead
python ~/.codex/skills/x/scripts/x_state.py package --role councilor --interaction-id "<interaction-id>" --participant cto
```

Independent synthesis requires a `ready` participant brief for every participant. Unresolved conflicts must be surfaced to root instead of being silently resolved by architect.

## Council Response Protocol

The council is useful only when it behaves like a real working room. The default response must be a structured deep discussion, not a compressed set of named blurbs.

First substantive response on a council topic:

- State the decision frame: what root is deciding, what is out of scope, and what evidence could change the answer.
- Round 1: each active participant gives a concrete position with reasons, evidence or assumptions, risk, and decision implication.
- Round 2: participants challenge named claims from other participants. `challenger` must attack the strongest live claim, and at least one domain participant must answer or narrow their stance.
- Options: list realistic paths root could choose, including a pause/validation path when evidence is weak.
- Evidence needed: list specific customer interviews, data checks, competitor proof, technical spikes, or sales tests that would change the recommendation.
- Main only facilitates. Main must not convert the room into `Room Essence`, root decision, or architect intake until root asks for that step.

Forbidden default behavior:

- One short paragraph per participant followed by a final conclusion.
- Generic objections that do not name the claim being challenged.
- Treating assumptions as facts.
- Skipping customer/market/technical evidence gaps because a narrative sounds plausible.
- Letting `Room Essence` replace the visible exchange.

## Durable State

Interaction state is explicit markdown under `~/.x/projects/<project-key>/`:

```text
interactions/<interaction-id>.md
participant-briefs/<brief-id>.md
architect-intakes/<intake-id>.md
participants/<participant>.md
boards/current.md
```

Existing `decisions/<decision-id>.md` remains the source of root authority.

The interaction file's `Turns` section is the canonical transcript. Each turn includes an actor, turn kind, audience (`To:`), and body. Recording a turn prints the current transcript so root can see the process without running a separate show command. `interaction-show` exists for resume/debug reads.

Root-facing assistant responses should mirror this shape:

```text
Room: <interaction-id>
Participants: root, main, founder, cto, ...
Speaking:
- founder -> root: ...
- cto -> founder/all: ...
- main -> root: facilitator note only, if needed.
```

Precedence:

```text
root decision > accepted architect intake > accepted Architecture Brief > participant brief > interaction turn
```

Record meanings:

- `interaction`: agenda/root thesis, participants, compressed turns, linked participant briefs, `Room Essence`, linked architect intake, linked root decisions, and packages.
- `participant brief`: one participant's formal view: recommendation, rationale, rejected options, risks, decisions needed, implications for architect, and required challenge fields.
- `decision`: root's accepted decision and consequences, optionally linked to an interaction and architect intake.
- `architect intake`: decision-complete input architect may use to create or revise Architecture Brief and Execution Plan.
- `board`: generated root-facing summary across active interactions, accepted intakes, root decisions, active runs, and risks.

## Room Essence

Every default council, selected-participant council, single-participant council, or independent room resolves into one `Room Essence` inside the existing interaction `Synthesis` section. It is the shared advisory source that main can later use to write a BRD, PRD, strategy document, sales strategy, or architect intake draft.

Required fields:

- core judgment
- recommended direction
- key arguments
- objections / conflicts
- rejected options
- weakest assumptions
- evidence to change
- open root decisions
- document-use notes

The `Room Essence` is not a root decision. It becomes execution-relevant only after root records a decision and, when needed, accepts an architect intake.

## Challenger Requirement

Challenger thinking is required in every participant brief and interaction summary. Participant briefs keep explicit challenge fields; interaction summaries carry them into `Room Essence`, with strongest objection folded into objections/conflicts.

Required challenge fields:

- strongest objection
- weakest assumption
- evidence that would change the recommendation

## Implemented V1

- `interaction-start`, `interaction-turn`, `interaction-summarize`, `participant-brief`, `architect-intake`, and `board`.
- Configurable participant cards with defaults for `founder`, `cto`, `product-lead`, `market-intelligence`, `gtm`, and `challenger`.
- `council` participant preset for `founder`, `cto`, `product-lead`, `market-intelligence`, `gtm`, and `challenger`.
- `package --role councilor --interaction-id ... --participant ...` for participant brief inputs.
- `decision` links to interaction and architect intake.
- Accepted architect intake requires an accepted root decision.
- Architect packages require `--architect-intake-id` when multiple accepted architect intakes exist.
- Closed or superseded interactions reject new turns, participant briefs, summaries, decisions, packages, and architect intakes.
- Reserved participant names such as `root`, `main`, `engineer`, `reviewer`, `councilor`, and `council` cannot be registered as configurable interaction participants.

## Non-Goals

- Do not introduce external services, GitHub, Notion, or MCP dependencies for this layer.
- Do not make council rooms mandatory for small tasks.
- Do not let council participants bypass architect and manage engineer/reviewer directly.
- Do not store only raw chat logs as durable state; always produce compressed, participant-scoped records.
- Do not add participant-specific overlay files until a second real project proves the need.
