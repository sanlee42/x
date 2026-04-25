#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-$HOME/.codex}"

mkdir -p "$codex_home/skills" "$codex_home/agents"

ln -sfn "$repo_root/skill" "$codex_home/skills/x"
ln -sfn "$repo_root/agents/cto.toml" "$codex_home/agents/cto.toml"
ln -sfn "$repo_root/agents/engineer.toml" "$codex_home/agents/engineer.toml"
ln -sfn "$repo_root/agents/reviewer.toml" "$codex_home/agents/reviewer.toml"

printf 'installed x skill: %s -> %s\n' "$codex_home/skills/x" "$repo_root/skill"
printf 'installed x agents under: %s\n' "$codex_home/agents"
