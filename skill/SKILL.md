---
name: x
description: Use for the repository CTO-to-code loop when the user says "$x cto", "$x status", "$x resume", "$x checkpoint", or "$x close" and wants Codex to replace manual CTO discussion, codebase investigation, technical design, implementation, review, fix loop, and merge-back recommendation.
---

# x

`x` is the repository CTO-to-code loop. It turns a root directive into CTO co-creation, an accepted CTO Intake Brief, a Technical Contract, Engineer Tasks, implementation/fix iterations, subagent input packages, review findings, decisions, risks, and a merge-back recommendation.

This is a prompt protocol, not a shell command or slash command. The bundled script is only the state machine.

## Trigger

Use this skill when the user says:

- `$x cto: <goal>` or `x cto`
- `$x status`, `$x resume`, `$x checkpoint`, `$x close`

Do not use `$x start engineering` as the user-facing entry. `Engineering Loop` is the lower execution layer behind the CTO entry.

## Required context

Read these first:

1. `PROJECT_CONSTRAINTS.md`
2. `AGENTS.md`
3. `.x/project/profile.md` if it exists
4. `~/.codex/skills/x/references/engineering-loop-principles.md`
5. `~/.x/projects/<project-key>/ledger/current.md` if it exists
6. The current run file under `~/.x/projects/<project-key>/runs/` when resuming, checking status, checkpointing, or closing

## State tool

Use the bundled script instead of hand-writing run files:

```bash
python ~/.codex/skills/x/scripts/x_state.py --help
```

The script owns:

- `.x/project/profile.md`
- `~/.x/projects/<project-key>/runs/<run-id>.md`
- `~/.x/projects/<project-key>/briefs/<brief-id>.md`
- `~/.x/projects/<project-key>/contracts/<contract-id>.md`
- `~/.x/projects/<project-key>/tasks/<task-id>.md`
- `~/.x/projects/<project-key>/iterations/<iteration-id>.md`
- `~/.x/projects/<project-key>/reviews/<review-id>.md`
- `~/.x/projects/<project-key>/packages/<package-id>.md`
- `~/.x/projects/<project-key>/decisions/<decision-id>.md`
- `~/.x/projects/<project-key>/ledger/current.md`
- `~/.x/projects/<project-key>/risks/<risk-id>.md`

## Roles

- `root`: the user; owns direction, final merge authority, and irreversible decisions.
- `main agent`: orchestrates, does repo/context intake, spawns subagents, writes `.x` state, runs gates, and reports to root.
- `cto`: co-creates the CTO Intake Brief with root, then converts an accepted direction into technical boundaries.
- `engineer`: implements only a bounded Engineer Task and returns patch evidence.
- `reviewer`: independently reviews patch evidence against the contract, task, diff, tests, and repo constraints.

Subagents must not spawn child agents or write final ledger state.

All roles load project context before answering: `PROJECT_CONSTRAINTS.md`, `AGENTS.md`, optional `.x/project/profile.md`, then their x package. If they conflict, earlier files win; if the package conflicts with project context, the role reports the conflict instead of guessing.

## CTO Start

For `$x cto: <goal>`:

1. Create a run:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py start --goal "<goal>" --directive "<root directive>" --success "<success criteria>" --constraints "<constraints>"
   ```
2. Do minimal repo/context intake and write `Repo Intake` plus `Codebase Findings`:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py section --name "Repo Intake" --content "<repo intake>"
   python ~/.codex/skills/x/scripts/x_state.py section --name "Codebase Findings" --content "<findings>"
   ```
3. Generate a CTO package, then spawn `cto` for root/CTO co-creation:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py package --role cto --title "<cto package>" --notes "<known context>"
   ```
4. Discuss with root if the CTO response has open questions, options, or root decisions. Record the result as a CTO Intake Brief:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py brief --title "<brief>" --package-id "<package-id>" --status accepted --cto-questions "<questions>" --options "<options>" --recommendation "<recommendation>" --risks "<risks>" --root-decisions-needed "<root decisions>" --accepted-direction "<accepted direction>"
   ```
5. If the brief is `draft` or `blocked`, continue root/CTO discussion. Do not create a Technical Contract.
6. From an accepted brief, create the Technical Contract:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py contract --brief-id "<brief-id>" --title "<contract>" --goal "<goal>" --repo-intake "<intake>" --codebase-findings "<findings>" --allowed-boundaries "<scope>" --forbidden-boundaries "<scope>" --reversible-path "<path>" --verification "<tests>" --loopback "<conditions>"
   ```
7. Main agent creates one or more Engineer Tasks from the contract:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py task --title "<task>" --goal "<goal>" --allowed-scope "<scope>" --forbidden-scope "<scope>" --requirements "<requirements>" --verification "<tests>" --done-evidence "<evidence>"
   ```
8. Start one implementation iteration:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py iteration-start --task-id "<task-id>" --kind implementation --title "<iteration title>"
   ```
9. Generate an engineer package, then spawn a fresh `engineer` with that package:
   ```bash
   python ~/.codex/skills/x/scripts/x_state.py package --role engineer --task-id "<task-id>" --iteration-id "<iteration-id>"
   ```
10. After implementation, record iteration evidence:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py iteration-result --iteration-id "<iteration-id>" --changed-files "<files>" --summary "<summary>" --verification "<observed results>" --residual-risk "<risk>"
    ```
11. Generate a reviewer package only after iteration evidence exists, then spawn `reviewer`:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py package --role reviewer --task-id "<task-id>" --iteration-id "<iteration-id>" --diff-stat "<git diff --stat>" --diff "<git diff>"
    ```
12. Record review:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py review --title "<review>" --task-id "<task-id>" --iteration-id "<iteration-id>" --summary "<summary>" --recommendation ready --reviewed-diff "<diff evidence>" --verification "<assessment>"
    ```
13. If review requests changes, start a fresh fix iteration from that review:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py iteration-start --task-id "<task-id>" --kind fix --source-review-id "<review-id>" --agent-policy fresh --title "<fix title>"
    ```
14. Continue engineer package -> fresh engineer -> iteration-result -> reviewer package -> reviewer -> review until the task has a ready review.
15. Run the merge-ready gate:
    ```bash
    python ~/.codex/skills/x/scripts/x_state.py gate --mode merge-ready
    ```
16. If the gate passes, create a local commit when the implementation changed code and write a close recommendation. Do not merge to `master/main`, push, open PR, or call GitHub unless root explicitly asks.

## Status and Resume

For `x status`, do not re-plan. Read state only:

```bash
python ~/.codex/skills/x/scripts/x_state.py status
```

For `x resume`, continue from `Next Operating Actions` / `Next Action`:

```bash
python ~/.codex/skills/x/scripts/x_state.py resume
```

Before resumed work, use the resume output to choose the next phase and checkpoint after finishing that phase.

## Checkpoint and Close

For `x checkpoint`, compress current state:

```bash
python ~/.codex/skills/x/scripts/x_state.py checkpoint --summary "<summary>" --next-action "<next action>"
```

For `x close --status accepted`, the merge-ready gate must pass first:

```bash
python ~/.codex/skills/x/scripts/x_state.py close --status accepted --summary "<merge-back recommendation>"
```

## Gates

- No accepted CTO Intake Brief, no Technical Contract.
- No Technical Contract, no Engineer Task.
- No Engineer Task, no iteration.
- No iteration, no engineer package.
- No iteration result / patch evidence, no reviewer package.
- `review --recommendation ready` cannot include blocking findings.
- Blocking or unresolved review means no accepted close.
- Any active task without a latest ready reviewed iteration fails the merge-ready gate.
- Three non-ready reviews for the same task require CTO/root loopback.
- Missing required verification means no merge-ready gate.
- Merge-back recommendation is not a merge. Root must explicitly authorize merge, push, PR, or GitHub integration.

## Future Upper Layer

CEO/Product/Growth may later produce root-ready CTO inputs, but they are not active roles in this MVP. The active boundary is:

```text
root -> CTO co-creation -> accepted CTO Intake Brief -> Technical Contract -> Engineer Task -> implementation/review/fix loop -> merge-back recommendation
```
