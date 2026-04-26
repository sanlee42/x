from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from x_state_common import *
from x_state_commands import update_source_review_addressed
from x_state_execution import lane_for_attempt, mark_lane_code_review


def command_review(args: argparse.Namespace) -> None:
    if args.recommendation == "ready" and blocking_present(args.blocking_findings):
        raise SystemExit("ready review cannot include blocking findings")
    root = repo_root(Path.cwd())
    attempt = resolve_state_file(root, "attempts", args.attempt_id)
    attempt_text = attempt.read_text(encoding="utf-8")
    run_id = header_value(attempt_text, "Linked Run")
    if not run_id:
        raise SystemExit(f"attempt missing Linked Run: {attempt.stem}")
    run = resolve_run(root, args.run_id or run_id)
    if run.stem != run_id:
        raise SystemExit(f"attempt {attempt.stem} is linked to run {run_id}, not {run.stem}")
    require_materialized_run(run, "review")
    if not attempt_has_result(attempt_text):
        raise SystemExit(f"attempt has no result evidence: {attempt.stem}")
    lane = lane_for_attempt(root, attempt)
    if lane is not None and header_value(lane.read_text(encoding="utf-8"), "Last Attempt") != attempt.stem:
        raise SystemExit(f"review must target latest lane attempt: {header_value(lane.read_text(encoding='utf-8'), 'Last Attempt')}")
    task_id = header_value(attempt_text, "Linked Task")
    if not task_id:
        raise SystemExit(f"attempt missing Linked Task: {attempt.stem}")
    task = resolve_state_file(root, "tasks", task_id)
    source_review_id = header_value(attempt_text, "Source Review") or "none"
    review_id = args.review_id or f"{today()}-{slug(args.title, 'review')}"
    review_path = unique_path(state_dirs(root)["reviews"], review_id)
    next_non_ready_count = non_ready_review_count(root, task.stem) + (0 if args.recommendation == "ready" else 1)
    loopback_target = review_loopback(args, next_non_ready_count)
    content = read_template(REVIEW_TEMPLATE).format(
        review_id=review_path.stem,
        status=args.status,
        recommendation=args.recommendation,
        date=dt.date.today().isoformat(),
        run_id=run_id,
        task_id=task.stem,
        attempt_id=attempt.stem,
        source_review_id=source_review_id,
        loopback_target=loopback_target,
        summary=args.summary,
        blocking_findings=args.blocking_findings or "- None.",
        non_blocking_findings=args.non_blocking_findings or "- None.",
        reviewed_diff=args.reviewed_diff,
        verification=args.verification,
        residual_risk=args.residual_risk or "Not specified.",
    )
    write(review_path, content, args.dry_run)
    next_action = apply_review_result(root, args, review_path, task, attempt, loopback_target)
    needs_user = review_needs_user(args, next_non_ready_count, loopback_target)
    if args.recommendation != "ready" and needs_user == "yes":
        next_action = f"Loop back to architect/root for {task.stem}: repeated non-ready reviews or root loopback."
    run_text = update_header(run, phase="Review", needs_user=needs_user)
    review_line = f"{review_path.stem}: {attempt.stem} {args.recommendation} - {args.summary}"
    run_text = append_bullet(run_text, "Review Findings", review_line)
    if args.recommendation == "ready" and source_review_id != "none":
        run_text = remove_bullet_containing(run_text, "Unresolved Reviews", source_review_id)
    if args.recommendation != "ready":
        run_text = append_bullet(run_text, "Fix Loop", f"{review_path.stem}: {args.recommendation}")
        run_text = append_bullet(run_text, "Unresolved Reviews", f"{review_path.stem}: {args.recommendation} -> {loopback_target}")
    run_text = replace_section(run_text, "Next Action", args.next_action or next_action)
    run_text = append_event_text(run_text, f"Review recorded: {review_path.stem}")
    save(run, run_text, args.dry_run)
    mark_lane_code_review(root, review_path, args.dry_run)


def review_loopback(args: argparse.Namespace, next_non_ready_count: int) -> str:
    if args.recommendation == "ready":
        return "none"
    if next_non_ready_count >= MAX_NON_READY_REVIEWS:
        if args.loopback_target in {"architect", "root"}:
            return args.loopback_target
        return "architect"
    if args.loopback_target:
        return args.loopback_target
    if args.recommendation == "changes-requested":
        return "engineer"
    if args.recommendation == "blocked":
        return "architect"
    return "none"


def apply_review_result(
    root: Path,
    args: argparse.Namespace,
    review_path: Path,
    task: Path,
    attempt: Path,
    loopback_target: str,
) -> str:
    if args.recommendation == "ready":
        attempt_text = replace_line(attempt.read_text(encoding="utf-8"), "Status: ", "reviewed")
        save(attempt, attempt_text, args.dry_run)
        task_text = replace_section(task.read_text(encoding="utf-8"), "Latest Ready Attempt", attempt.stem)
        task_text = replace_line(task_text, "Status: ", "done")
        save(task, task_text, args.dry_run)
        update_source_review_addressed(root, attempt_text, args.dry_run)
        return "Run merge-ready gate."
    if loopback_target == "engineer":
        return f"Start fresh fix attempt for {review_path.stem}."
    if loopback_target == "architect":
        return f"Loop back to architect before more engineering; review {review_path.stem} is blocked."
    return f"Escalate review {review_path.stem} to root."


def review_needs_user(args: argparse.Namespace, next_non_ready_count: int, loopback_target: str) -> str | None:
    if args.recommendation == "ready":
        return args.needs_user or "no"
    if next_non_ready_count >= MAX_NON_READY_REVIEWS or loopback_target == "root":
        return "yes"
    return args.needs_user
