# Architect Room Workflow

Use this when `$x architect` starts or `$x resume` needs to continue execution work. The state helper owns durable records; do not hand-write run files.

## Contents

- Optional Interaction Handoff
- Main Flow
- Role Thread Lifecycle
- Mailbox

## Optional Interaction Handoff

Root-facing interaction is an advisory layer before architect execution. Use it when root asks for product, technical, strategy, challenger, or custom role discussion before committing to an architecture direction.

Typical interaction state helper flow:

```bash
python ~/.codex/skills/x/scripts/x_state.py role-list
python ~/.codex/skills/x/scripts/x_state.py interaction-start --mode joint --title "<topic>" --agenda "<root thesis or question>" --participants product technical strategy
python ~/.codex/skills/x/scripts/x_state.py interaction-turn --interaction-id "<interaction-id>" --actor root --turn-kind statement --body "<root thesis>"
python ~/.codex/skills/x/scripts/x_state.py package --role councilor --interaction-id "<interaction-id>" --council-role technical
python ~/.codex/skills/x/scripts/x_state.py role-brief --interaction-id "<interaction-id>" --role technical --title "<brief>" --recommendation "<stance>" --rationale "<why>" --rejected-options "<rejected>" --risks "<risks>" --decisions-needed "<root decisions>" --implications-for-architect "<handoff notes>" --strongest-objection "<objection>" --weakest-assumption "<assumption>" --evidence-to-change "<evidence>"
python ~/.codex/skills/x/scripts/x_state.py interaction-summarize --interaction-id "<interaction-id>" --agreements "<agreements>" --conflicts "<conflicts>" --rejected-options "<rejected>" --root-decisions-needed "<decisions>" --recommended-direction "<proposal>" --architect-intake-draft "<draft>" --strongest-objection "<objection>" --weakest-assumption "<assumption>" --evidence-to-change "<evidence>"
python ~/.codex/skills/x/scripts/x_state.py decision --interaction-id "<interaction-id>" --title "<decision>" --decision "<accepted direction>"
python ~/.codex/skills/x/scripts/x_state.py architect-intake --interaction-id "<interaction-id>" --decision-id "<decision-id>" --status accepted --title "<intake>" --accepted-direction "<accepted direction>" --architecture-input "<architect input>" --scope-boundaries "<scope>" --non-goals "<non-goals>" --root-decisions "<decisions>" --risks "<risks>" --handoff-to-architect "<handoff>"
```

Compatibility commands and fields still use `discussion` naming in some places because runtime state is stored under `discussions/<id>.md`, but new root-facing docs and examples should prefer `interaction-*` and `--interaction-id`.

Interaction role views must not create Engineer Tasks, start attempts, manage lanes, assign reviewers, or issue architect directives. They produce compressed advisory state only. Accepted architect intake is the handoff into the architect room.

## Main Flow

1. Create a run:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py start --goal "<optional goal>" --directive "<root directive>" --success "<success criteria>" --constraints "<constraints>"
   ```
   `--goal` is optional. Without it, open an architect room whose goal is discovered through root/architect co-creation.
2. Do minimal repo/context intake and write `Repo Intake` plus `Codebase Findings`:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py section --name "Repo Intake" --content "<repo intake>"
   python ~/.codex/skills/x/scripts/x_state.py section --name "Codebase Findings" --content "<findings>"
   ```
3. Generate an architect package, then spawn `architect` for root/architect co-creation:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py package --role architect --run-id "<run-id>" --title "<architect package>" --notes "<known context>"
   ```
   If there are multiple accepted architect intakes, select one explicitly:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py package --role architect --run-id "<run-id>" --architect-intake-id "<intake-id>" --title "<architect package>" --notes "<known context>"
   ```
4. Discuss with root if the architect response has open questions, options, root decisions, or naming choices. Record the result as an Architecture Brief:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py brief --title "<brief>" --package-id "<package-id>" --status accepted --architect-questions "<questions>" --options "<options>" --recommendation "<recommendation>" --risks "<risks>" --root-decisions-needed "<root decisions>" --accepted-direction "<accepted direction>"
   ```
5. If the brief is `draft` or `blocked`, continue root/architect discussion. Do not create a Technical Contract.
6. From an accepted brief, materialize the integration worktree:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py materialize --run-id "<run-id>" --scope "<scope>"
   ```
   This creates `.dev/<scope>` and `feat/<scope>` by default. Use the scope/branch/worktree naming agreed with root and architect.
7. Create the Technical Contract:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py contract --brief-id "<brief-id>" --title "<contract>" --goal "<goal>" --repo-intake "<intake>" --codebase-findings "<findings>" --allowed-boundaries "<scope>" --forbidden-boundaries "<scope>" --reversible-path "<path>" --verification "<tests>" --loopback "<conditions>"
   ```
8. Main agent creates one or more Engineer Tasks from the contract:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py task --title "<task>" --goal "<goal>" --allowed-scope "<scope>" --forbidden-scope "<scope>" --requirements "<requirements>" --verification "<tests>" --done-evidence "<evidence>"
   ```
9. Architect produces an Architect Execution Plan for long-run parallel execution, then main runs the readiness gate:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py execution-plan --run-id "<run-id>" --title "<plan>" --objective "<objective>" --parallel-lanes "<lane table>" --dependency-graph "<graph>" --lane-ownership "<ownership>" --allowed-scope "<scope>" --forbidden-scope "<scope>" --expected-artifacts "<artifacts>" --verification-matrix "<matrix>" --reviewer-criteria "<criteria>" --architect-merge-criteria "<criteria>" --integration-order "<order>" --known-risks "<risks>" --loopback-triggers "<triggers>" --blocked-recovery "<recovery>" --root-decisions "<root decisions>"
   python ~/.codex/skills/x/scripts/x_state.py architect-gate --run-id "<run-id>"
   ```
   The plan must be decision-complete for every lane. Its `Parallel Lanes` table must include `Lane ID`, `Task ID`, `Allowed Scope`, `Forbidden Scope`, `Worktree Scope`, `Verification`, `Done Evidence`, `Risk Level`, `Concurrent Group`, `Serial Only`, and `Shared Files`. `Risk Level` is `standard` or `high`; `Serial Only` is `yes` or `no`; `Concurrent Group` is a group name or `none`; `Shared Files` is a file/module list or `none`. Shared files require `Risk Level` `high`, and serial-only lanes must use `Concurrent Group` `none`. It must include exact lane/task scope, verification, done evidence, runbook, loop policy, review criteria, architect merge criteria, integration order, concurrent lane groups, serial-only lanes, shared-file conflict risks, blocked-state recovery, and root escalation boundaries. Unresolved `TBD`, `figure out`, `use best judgment`, or `decide later` language fails the readiness gate unless explicitly recorded as a root decision.
10. Start lane sessions/worktrees from the gated plan:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py lane-start --run-id "<run-id>" --lane-id "<lane-id>" --task-id "<task-id>"
    python ~/.codex/skills/x/scripts/x_state.py lane-update --run-id "<run-id>" --lane-id "<lane-id>" --actor main --session "<session-id>" --heartbeat-status active --activity "<current work>" --blocker "None." --next-action "<next>"
    python ~/.codex/skills/x/scripts/x_state.py lane-status --run-id "<run-id>"
    ```
    Use `lane-update` whenever main hands off work, receives progress, records a blocker, or prepares an architect package. Heartbeats are observation state; they do not change canonical lane `Status` or bypass gates.
11. Start one implementation attempt inside a lane:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py attempt-start --task-id "<task-id>" --lane-id "<lane-id>" --kind implementation --title "<attempt title>"
    ```
12. Generate an engineer package, then start the engineer role with that package:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py package --role engineer --task-id "<task-id>" --attempt-id "<attempt-id>"
    ```
    The engineer must work only inside the package's `Lane Worktree`.
13. After implementation, record attempt evidence:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py attempt-result --attempt-id "<attempt-id>" --changed-files "<files>" --summary "<summary>" --verification "<observed results>" --residual-risk "<risk>"
    ```
14. Generate a reviewer package only after attempt evidence exists, then spawn `reviewer`:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py package --role reviewer --task-id "<task-id>" --attempt-id "<attempt-id>"
    ```
    If `--diff` and `--diff-stat` are omitted, the script captures the lane worktree diff from the lane/integration merge-base. Reviewer packages reject untracked lane files because they would not be captured in the review or integration diff.
    `--reviewer-backend codex-native` is an opt-in alternative that runs `codex review --base <lane-base> -` from the lane worktree and records the review output directly without embedding the full raw diff in a package.
15. Record code review:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py review --title "<review>" --attempt-id "<attempt-id>" --summary "<summary>" --recommendation ready --reviewed-diff "<diff evidence>" --verification "<assessment>"
    ```
16. If code review requests changes, start a fresh fix attempt from that review:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py attempt-start --task-id "<task-id>" --lane-id "<lane-id>" --kind fix --source-review-id "<review-id>" --title "<fix title>"
    ```
17. Continue engineer package -> attempt-result -> reviewer package -> reviewer -> review until the lane has a ready code review.
18. Architect performs strong integration review. Reviewer `ready` alone is not integration permission:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py architect-review --lane-id "<lane-id>" --attempt-id "<attempt-id>" --title "<architect review>" --summary "<summary>" --recommendation merge-ok --criteria "<criteria>" --verification "<assessment>" --integration-risk "<risk>"
    ```
    Read `references/architect-review-policy.md` before architect review. High-risk lanes require two distinct `merge-ok` architect review records linked to the latest attempt before integration.
19. If architect needs to adjust execution before integration review, record an explicit directive:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py architect-directive --run-id "<run-id>" --title "<directive>" --target lane --lane-id "<lane-id>" --action pause-lane --summary "<why>" --instructions "<what main should do>" --acceptance "<clear condition>"
   ```
   Valid actions are `continue`, `parallelism-adjustment`, `verification-adjustment`, `pause-lane`, `resume-lane`, `replan`, `root-decision`, and `request-more-evidence`. `parallelism-adjustment`, `verification-adjustment`, and `request-more-evidence` are open but non-blocking by default; use `pause-lane`, `replan`, or `root-decision` when execution must be gated.
20. Integrate only after reviewer ready and architect `merge-ok`:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py integrate --lane-id "<lane-id>"
    ```
21. After all lanes are integrated, run the final verification matrix and mark it green:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py execution-plan --run-id "<run-id>" --plan-id "<plan-id>" --final-verification-status green --final-verification "<commands and observed output>"
    ```
22. Run the merge-ready gate:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py gate --mode merge-ready --run-id "<run-id>"
    ```
23. If the gate passes, create a local commit in the integration worktree when implementation changed code and write a close recommendation. Do not merge to `master/main`, push, open PR, or call GitHub unless root explicitly asks.

## Role Thread Lifecycle

When main receives a completed `architect`, `engineer`, or `reviewer` subagent result, main first records the durable state that result implies, such as `brief`, `execution-plan`, `attempt-result`, `review`, `architect-review`, `architect-directive`, `lane-update`, `mailbox-send`, `risk`, or `checkpoint`. After the state write succeeds, main must close the completed agent thread so stale role context does not remain active.

If closing a completed thread fails, main records the risk in a checkpoint, heartbeat, or risk record and continues from the durable state already written. A close failure must not block a completed attempt result, review, architect directive, or accepted state transition.

`x_state.py` does not directly operate Codex `/agent` runtime state. Agent spawning, waiting, and closing are Codex UI/runtime actions; the state helper only records durable x workflow state.

## Mailbox

Use the mailbox for lightweight cross-lane or role-to-main coordination that should be visible in status and architect observation packages:

```bash
python ~/.codex/skills/x/scripts/x_state.py mailbox-send --run-id "<run-id>" --kind request --from main --to engineer --summary "<summary>" --body "<message>"
python ~/.codex/skills/x/scripts/x_state.py mailbox-list --run-id "<run-id>"
python ~/.codex/skills/x/scripts/x_state.py mailbox-resolve --message-id "<message-id>" --status addressed --resolution "<what changed>"
```

Kinds are `request`, `response`, `artifact-ready`, `interface-change`, `blocker`, `directive`, and `ack`. Statuses are `open`, `addressed`, and `superseded`.

Mailbox messages may link a run, lane, task, attempt, review, from/to actor, session, summary, body, and related artifacts. Role package receivers still return evidence to main; they do not freely mutate x state or use mailbox records as permission to bypass gates.
