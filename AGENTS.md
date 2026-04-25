# AGENTS.md

Rules for working on `x` itself.

## Source Layout

- `skill/` owns the Codex skill, workflow docs, state scripts, and templates.
- `agents/` owns generic role prompts.
- `scripts/` owns local install helpers.
- Runtime state does not belong in this repo. It lives under `~/.x/projects/<project-key>/`.

## Design

- Keep `x` generic. Product-specific constraints belong in the product repo's `PROJECT_CONSTRAINTS.md`, `AGENTS.md`, and `.x/project/profile.md`.
- Do not add role-specific overlay files until a second real project proves the need.
- Prefer explicit markdown state over hidden runtime state.
- Keep gates simple and checkable.
- Do not introduce external services, GitHub, Notion, MCP, or product/CEO roles unless explicitly requested.

## Verification

- Run `python -m py_compile skill/scripts/*.py` after script changes.
- Parse `agents/*.toml` after prompt changes.
- Smoke package generation for `cto`, `engineer`, and `reviewer` when package behavior changes.
- Keep hand-written Python files below 800 lines.
