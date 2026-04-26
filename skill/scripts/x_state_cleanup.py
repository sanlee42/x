from __future__ import annotations

import argparse
import subprocess
from dataclasses import dataclass
from pathlib import Path

from x_state_common import *


@dataclass
class CleanupCandidate:
    lane_id: str
    worktree: Path | None
    removable: bool
    reasons: list[str]


def command_cleanup_worktrees(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    candidates = cleanup_candidates(root, run)
    mode = "apply" if args.apply else "dry-run"
    print(f"# x Cleanup Worktrees: {run.stem}")
    print(f"Mode: {mode}")
    print()
    if not candidates:
        print("- none")
        return
    for candidate in candidates:
        action = "remove" if candidate.removable else "keep"
        path = str(candidate.worktree) if candidate.worktree else "none"
        reason = "; ".join(candidate.reasons)
        prefix = "will" if args.apply and candidate.removable else "would" if candidate.removable else "skip"
        print(f"- {prefix} {action} {candidate.lane_id}: {path} ({reason})")
    if not args.apply:
        return
    control_root = header_path(run.read_text(encoding="utf-8"), "Control Root") or root
    for candidate in candidates:
        if not candidate.removable or candidate.worktree is None:
            continue
        subprocess.check_call(["git", "-C", str(control_root), "worktree", "remove", str(candidate.worktree)])
        print(f"removed {candidate.lane_id}: {candidate.worktree}")


def cleanup_candidates(root: Path, run: Path) -> list[CleanupCandidate]:
    run_text = run.read_text(encoding="utf-8")
    integration_worktree = header_path(run_text, "Execution Worktree")
    expected_common_dir = expected_git_common_dir(root, run_text)
    control_root = header_path(run_text, "Control Root") or root
    registered_worktrees = git_registered_worktrees(control_root)
    duplicate_worktrees = duplicate_lane_worktrees(root, run)
    candidates: list[CleanupCandidate] = []
    for lane in files_for_run(root, "lanes", run.stem):
        lane_text = lane.read_text(encoding="utf-8")
        lane_id = header_value(lane_text, "Lane ID") or lane.stem.split("--", 1)[-1]
        worktree = lane_worktree_path(lane_text)
        reasons = cleanup_reasons(
            lane_text,
            worktree=worktree,
            control_root=control_root,
            integration_worktree=integration_worktree,
            expected_common_dir=expected_common_dir,
            registered_worktrees=registered_worktrees,
            duplicate_worktrees=duplicate_worktrees,
        )
        candidates.append(
            CleanupCandidate(
                lane_id=lane_id,
                worktree=worktree,
                removable=not reasons,
                reasons=reasons or ["integrated, clean lane worktree"],
            )
        )
    return candidates


def cleanup_reasons(
    lane_text: str,
    *,
    worktree: Path | None,
    control_root: Path,
    integration_worktree: Path | None,
    expected_common_dir: Path | None,
    registered_worktrees: set[Path],
    duplicate_worktrees: set[Path],
) -> list[str]:
    reasons: list[str] = []
    status = header_value(lane_text, "Status") or "unknown"
    if header_value(lane_text, "Integrated") != "yes":
        reasons.append("not integrated")
    if status != "integrated":
        reasons.append(f"status={status}")
    if worktree is None:
        reasons.append("missing worktree path")
        return reasons
    if worktree == control_root:
        reasons.append("control root")
    if integration_worktree is not None and worktree == integration_worktree:
        reasons.append("integration worktree")
    if worktree in duplicate_worktrees:
        reasons.append("duplicate lane worktree path")
    if not worktree.exists():
        reasons.append("worktree path missing")
        return reasons
    if worktree not in registered_worktrees:
        reasons.append("not a registered git worktree")
    actual_common_dir = git_common_dir(worktree)
    if actual_common_dir is None:
        reasons.append("not a git worktree")
    elif expected_common_dir is not None and actual_common_dir != expected_common_dir:
        reasons.append("git common dir mismatch")
    status_output = git_command_output(worktree, "status", "--porcelain")
    if status_output is None:
        reasons.append("git status unavailable")
    elif status_output.strip():
        reasons.append("dirty worktree")
    return reasons


def lane_worktree_path(lane_text: str) -> Path | None:
    value = header_value(lane_text, "Worktree")
    if value in {"", "none", "Pending.", UNMATERIALIZED}:
        return None
    return Path(value).expanduser().resolve()


def expected_git_common_dir(root: Path, run_text: str) -> Path | None:
    value = header_value(run_text, "Git Common Dir")
    if value:
        return Path(value).expanduser().resolve()
    control_root = header_path(run_text, "Control Root") or root
    return git_common_dir(control_root)


def git_common_dir(worktree: Path) -> Path | None:
    value = git_command_output(worktree, "rev-parse", "--git-common-dir")
    if not value:
        return None
    path = Path(value.strip())
    if not path.is_absolute():
        path = worktree / path
    return path.resolve()


def git_command_output(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def git_registered_worktrees(root: Path) -> set[Path]:
    output = git_command_output(root, "worktree", "list", "--porcelain")
    if output is None:
        return set()
    worktrees = set()
    for line in output.splitlines():
        if not line.startswith("worktree "):
            continue
        worktrees.add(Path(line[len("worktree ") :]).expanduser().resolve())
    return worktrees


def duplicate_lane_worktrees(root: Path, run: Path) -> set[Path]:
    counts: dict[Path, int] = {}
    for lane in files_for_run(root, "lanes", run.stem):
        worktree = lane_worktree_path(lane.read_text(encoding="utf-8"))
        if worktree is None:
            continue
        counts[worktree] = counts.get(worktree, 0) + 1
    return {worktree for worktree, count in counts.items() if count > 1}
