# x

`x` is a lightweight CTO-to-code workflow for Codex. It keeps the reusable workflow and role contracts outside any single product repo, while each product repo owns its project constraints and profile.

## Layout

- `skill/`: Codex skill, state helper scripts, templates, and workflow reference.
- `agents/`: generic `cto`, `engineer`, and `reviewer` agent prompts.
- `scripts/install-local.sh`: installs this checkout into the local Codex home with symlinks.

Runtime state is written outside product repos:

```text
~/.x/projects/<project-key>/
```

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

The installer links:

- `~/.codex/skills/x -> ~/workspace/x/skill`
- `~/.codex/agents/cto.toml -> ~/workspace/x/agents/cto.toml`
- `~/.codex/agents/engineer.toml -> ~/workspace/x/agents/engineer.toml`
- `~/.codex/agents/reviewer.toml -> ~/workspace/x/agents/reviewer.toml`

Restart Codex after installing if the current session does not discover new skills or agents.

## Use

From a product repo:

```bash
python ~/.codex/skills/x/scripts/x_state.py doctor
python ~/.codex/skills/x/scripts/x_state.py status
```

In Codex, use:

```text
$x cto: <goal>
```

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
