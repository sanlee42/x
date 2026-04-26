# x

`x` is a lightweight architect-to-code workflow for Codex. It keeps the reusable workflow and role contracts outside any single product repo, while each product repo owns its project constraints and profile.

The operating model is:

```text
master/main control root -> architect room -> accepted direction -> integration worktree -> Architect Execution Plan -> readiness gate -> lane worktrees -> lane heartbeats -> attempt/review/fix loops -> architect directives/reviews -> integrate -> merge-ready gate
```

## Layout

- `skill/`: Codex skill, state helper scripts, templates, and workflow reference.
- `agents/`: generic `architect`, `engineer`, and `reviewer` agent prompts.
- `scripts/install-local.sh`: installs this checkout into the local Codex home with symlinks.

Runtime state is written outside product repos:

```text
~/.x/projects/<project-key>/
```

The runtime tree holds markdown state for ledger, runs, interactions, role cards, role briefs, architect intakes, boards, briefs, contracts, execution plans, lanes, tasks, attempts, reviews, architect reviews, directives, packages, mailbox messages, decisions, risks, and optional run audits.

Project-specific context stays in the product repo:

```text
PROJECT_CONSTRAINTS.md
AGENTS.md
.x/project/profile.md
```

## Install

```bash
scripts/install-local.sh
```

The installer links this checkout, not a hard-coded `~/workspace/x` path:

- `~/.codex/skills/x -> <this-checkout>/skill`
- `~/.codex/agents/architect.toml -> <this-checkout>/agents/architect.toml`
- `~/.codex/agents/engineer.toml -> <this-checkout>/agents/engineer.toml`
- `~/.codex/agents/reviewer.toml -> <this-checkout>/agents/reviewer.toml`

Restart Codex after installing if it does not discover new skills or agents.

## Use

From a product repo, `x_state.py` is the internal state helper used by the `$x` workflow:

```bash
python ~/.codex/skills/x/scripts/x_state.py doctor
python ~/.codex/skills/x/scripts/x_state.py status
```

In Codex, use:

```text
$x
$x help
$x commands
$x architect
$x architect: <goal>
$x status
$x resume
$x checkpoint
$x close
```

`$x`, `$x help`, `$x commands`, and `$x ?` return a static root-facing command menu without reading repo/runtime state or mutating workflow state.

For root-facing direction work before architecture, `$x` also supports a durable interaction layer. Root normally asks in natural language:

```text
$x product: I think ChatBI should work like this; push on the product shape.
$x technical: challenge this technical boundary.
$x strategy: is this direction worth doing now?
$x challenger: find the weak assumption in this plan.
$x with architect: pressure-test this execution shape.
$x council: compare these two directions from product, technical, and strategy angles.
$x discussion: bring product, technical, and strategy together on this direction.
```

`x_state.py` is the internal state helper main uses behind that conversation:

```bash
python ~/.codex/skills/x/scripts/x_state.py role-list
python ~/.codex/skills/x/scripts/x_state.py role-show product
python ~/.codex/skills/x/scripts/x_state.py role-set ops --body-file ops-role.md
python ~/.codex/skills/x/scripts/x_state.py interaction-start --mode independent --title "<topic>" --agenda "<question>" --participants strategy technical product
python ~/.codex/skills/x/scripts/x_state.py role-brief --interaction-id <interaction-id> --role strategy ...
python ~/.codex/skills/x/scripts/x_state.py interaction-summarize --interaction-id <interaction-id> ...
python ~/.codex/skills/x/scripts/x_state.py decision --interaction-id <interaction-id> --title "<decision>" --decision "<accepted direction>"
python ~/.codex/skills/x/scripts/x_state.py architect-intake --interaction-id <interaction-id> --decision-id <decision-id> --status accepted ...
python ~/.codex/skills/x/scripts/x_state.py board
```

Interaction modes are `with`, `joint`, and `independent`. Participants come from configurable markdown role cards under `~/.x/projects/<project-key>/roles`, with default templates for `strategy`, `technical`, `product`, `challenger`, and `architect`. These interaction role cards are distinct from installed execution agent prompts; `product.toml`, `technical.toml`, `strategy.toml`, `challenger.toml`, and `councilor.toml` are not expected under `~/.codex/agents/`. The old `discussion-*` commands remain as compatibility aliases, and `product-acceptance` is accepted as a legacy alias for `product`; Acceptance/QA remains a later execution validation layer, not the product role.

Role briefs and summaries must include challenger fields: strongest objection, weakest assumption, and evidence that would change the recommendation. Interaction state is advisory until root records a decision; the accepted Architect Intake must link that accepted decision and is then handed to the existing architect room.

`$x architect` can start without a goal. It opens an architect room for root/architect co-creation. After the Architecture Brief is accepted, materialize an integration worktree:

```bash
python ~/.codex/skills/x/scripts/x_state.py materialize --run-id <run-id> --scope <scope>
```

This creates and binds the integration worktree `.dev/<scope>` with branch `feat/<scope>` by default.

Before engineer sessions can start, the architect must produce an Architect Execution Plan and the readiness gate must pass:

```bash
python ~/.codex/skills/x/scripts/x_state.py execution-plan --run-id <run-id> ...
python ~/.codex/skills/x/scripts/x_state.py architect-gate --run-id <run-id>
```

The plan must define parallel lanes, task dependencies, lane ownership, exact allowed/forbidden scope, expected artifacts, verification matrix, reviewer criteria, architect merge criteria, integration order, concurrent lane groups, serial-only lanes, shared-file conflict risks, loopbacks, blocked-state recovery, and root-decision boundaries. The `Parallel Lanes` table must include `Lane ID`, `Task ID`, `Allowed Scope`, `Forbidden Scope`, `Worktree Scope`, `Verification`, `Done Evidence`, `Risk Level`, `Concurrent Group`, `Serial Only`, and `Shared Files`. `Risk Level` is `standard` or `high`; `Serial Only` is `yes` or `no`; `Concurrent Group` is a group name or `none`; `Shared Files` is a file/module list or `none`. Shared files require `Risk Level` `high`, and serial-only lanes must use `Concurrent Group` `none`. Any unresolved `TBD`, `figure out`, `use best judgment`, or `decide later` language fails the readiness gate unless it is explicitly a root decision.

After the readiness gate passes, `$x` defaults to aggressive safe parallelism: main should batch-start every dependency-satisfied, unpaused, unblocked, non-conflicting ready lane and start reviewers as soon as attempt evidence exists. There is no fixed default engineer/reviewer cap unless root or project instructions set one. Integration still stays serial according to the plan's integration order.

Start lane worktrees from the gated plan:

```bash
python ~/.codex/skills/x/scripts/x_state.py lane-start --run-id <run-id> --lane-id <lane-id> --task-id <task-id>
python ~/.codex/skills/x/scripts/x_state.py lane-update --run-id <run-id> --lane-id <lane-id> --actor main --session "<session-id>" --heartbeat-status active --activity "<current work>" --blocker "None." --next-action "<next>"
python ~/.codex/skills/x/scripts/x_state.py lane-status --run-id <run-id>
```

Lane worktrees default to `.dev/<scope>-<lane-id>`, while lane state is stored as `lanes/<run-id>--<lane-id>.md` so lane names can be reused across runs. Engineer and reviewer packages are only valid for attempts linked to a lane and must operate inside the lane worktree, not the integration worktree.

`lane-update` records advisory heartbeat state only. It surfaces current activity, blocker, next action, and architect attention labels in `lane-status`, `status`, and architect packages, but it does not change canonical lane `Status`.

Use the mailbox for lightweight cross-lane or cross-role coordination that should be visible to main and architect:

```bash
python ~/.codex/skills/x/scripts/x_state.py mailbox-send --run-id <run-id> --kind request --from main --to architect --summary "<summary>" --body "<details>"
python ~/.codex/skills/x/scripts/x_state.py mailbox-list --run-id <run-id>
python ~/.codex/skills/x/scripts/x_state.py mailbox-resolve --run-id <run-id> --message-id <message-id> --status addressed --resolution "<resolution>"
```

Mailbox message kinds are `request`, `response`, `artifact-ready`, `interface-change`, `blocker`, `directive`, and `ack`. `status` includes open mailbox messages for the selected run; mailbox messages are coordination context, not gates by themselves.

Start an implementation attempt and generate the engineer package:

```bash
python ~/.codex/skills/x/scripts/x_state.py attempt-start --task-id <task-id> --lane-id <lane-id> --kind implementation --title "<attempt>"
python ~/.codex/skills/x/scripts/x_state.py package --role engineer --run-id <run-id> --task-id <task-id> --attempt-id <attempt-id>
```

After attempt evidence is recorded, generate the reviewer package and record the review:

```bash
python ~/.codex/skills/x/scripts/x_state.py attempt-result --attempt-id <attempt-id> --changed-files "<files>" --summary "<summary>" --verification "<results>" --residual-risk "<risk>"
python ~/.codex/skills/x/scripts/x_state.py package --role reviewer --run-id <run-id> --task-id <task-id> --attempt-id <attempt-id>
python ~/.codex/skills/x/scripts/x_state.py review --run-id <run-id> --attempt-id <attempt-id> --title "<review>" --summary "<summary>" --recommendation ready --reviewed-diff "<diff>" --verification "<assessment>"
```

Reviewer `ready` is not integration approval. The architect must review the ready attempt against the execution plan, architecture fit, code abstraction, maintainability, performance, correctness, security/privacy, observability, verification quality, product acceptance, and integration risk before the main agent integrates the lane:

```bash
python ~/.codex/skills/x/scripts/x_state.py architect-review --run-id <run-id> --lane-id <lane-id> --attempt-id <attempt-id> --title "<review>" --summary "<summary>" --recommendation merge-ok --criteria "<criteria>" --verification "<assessment>" --integration-risk "<risk>"
python ~/.codex/skills/x/scripts/x_state.py integrate --run-id <run-id> --lane-id <lane-id>
python ~/.codex/skills/x/scripts/x_state.py execution-plan --run-id <run-id> --plan-id <plan-id> --final-verification-status green --final-verification "<commands and observed output>"
python ~/.codex/skills/x/scripts/x_state.py gate --mode merge-ready --run-id <run-id>
```

High-risk lanes, including shared infrastructure, cross-lane contracts, data migrations, auth/security/privacy, public APIs, performance-sensitive paths, or files modified by more than one lane, must be marked `Risk Level` `high`. They require two distinct architect review records with `merge-ok`, and both records must link the latest lane attempt before `integrate` or `gate --mode merge-ready` can pass.

The merge-ready gate requires all planned lanes to be started, reviewer-ready, architect `merge-ok`, integrated, and covered by green final verification status plus recorded final verification evidence, with no unresolved blocking reviews or risks.

During execution, root should keep discussion at the architect layer. When the architect needs to adjust direction, record an explicit directive:

```bash
python ~/.codex/skills/x/scripts/x_state.py architect-directive --run-id <run-id> --title "<title>" --target lane --lane-id <lane-id> --action pause-lane --summary "<why>" --instructions "<what main should do>" --acceptance "<how this clears>"
```

Directive actions are `continue`, `parallelism-adjustment`, `verification-adjustment`, `pause-lane`, `resume-lane`, `replan`, `root-decision`, and `request-more-evidence`. `parallelism-adjustment`, `verification-adjustment`, and `request-more-evidence` default to open, non-blocking directives. Open `pause-lane` and `replan` directives block lower lane work; open `root-decision` directives block accepted close. Architect packages include a control board with run, plan, lane, review, lane heartbeat, attention, and open directive state.

Architect should also observe execution before final review. Main should generate architect observation packages when heartbeats are stale or blocked, safe parallelism is underused, lane activity suggests scope drift, multiple lanes touch shared files or interfaces, verification/product acceptance evidence is weak, repeated fix loops suggest plan mismatch, quota/context risk appears, or a large integration batch is about to proceed. Architect responds with continue, parallelism or verification adjustments, directives, replan/root-decision, or requests for more evidence.

## Run Audit

`audit` is a read-only run report by default. It combines existing `x` markdown state with local Codex thread usage from `~/.codex/state_5.sqlite`:

```bash
python ~/.codex/skills/x/scripts/x_state.py audit --run-id <run-id>
python ~/.codex/skills/x/scripts/x_state.py audit --run-id <run-id> --json
python ~/.codex/skills/x/scripts/x_state.py audit --run-id <run-id> --write
```

The report includes run status and duration, gate status, base/head scale, commit count, diff shortstat, changed-file count, workflow counts, lane integration counts, and token totals by package role. `--write` stores the Markdown report at `~/.x/projects/<project-key>/audits/<run-id>.md`; otherwise audit does not mutate runtime state. `--codex-state <path>` can point at a test or alternate Codex sqlite file.

Token accounting is strict. A package is counted only when exactly one Codex thread title or first user message matches the full package path, `/packages/<package-id>.md`, or the complete package id with boundaries. Missing or ambiguous matches are listed as unresolved and are not included in token totals.

## Root Interaction And Acceptance

The root-facing interaction layer is documented in [`skill/references/root-interaction-design.md`](skill/references/root-interaction-design.md). The implemented v1 covers durable interactions, configurable role cards, role briefs, summaries/proposals, root decisions, architect intakes, and the root board. Acceptance/QA remains future-layer design.

## Project Key

By default, `x` uses the git repository name. For git worktrees, it resolves the main repository name instead of the worktree directory name.

Override when needed:

```bash
X_PROJECT_KEY=my-project python ~/.codex/skills/x/scripts/x_state.py status
```

Override the runtime root:

```bash
X_HOME=/tmp/x-runtime python ~/.codex/skills/x/scripts/x_state.py status
```

`status` prints the current repo root, project key, runtime directory, and project profile path before showing run state. `doctor` prints the same binding plus install diagnostics for the global skill and agent symlinks.

After accepted close or a completed integration, clean lane worktrees with an explicit dry-run followed by apply:

```bash
python ~/.codex/skills/x/scripts/x_state.py cleanup-worktrees --run-id <run-id>
python ~/.codex/skills/x/scripts/x_state.py cleanup-worktrees --run-id <run-id> --apply
```

Cleanup only removes integrated, clean, registered lane worktrees whose git common dir matches the run. It does not remove the integration worktree or any active, paused, blocked, dirty, missing, duplicate, or mismatched lane worktree.
