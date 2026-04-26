from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from x_state_common import *


BLOCKING_ACTIONS = {"pause-lane", "replan", "root-decision"}
LANE_ACTIONS = {"pause-lane", "resume-lane"}


def command_architect_directive(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    run_id = run.stem
    plan = resolve_directive_plan(root, run_id, args.plan_id, args.action, args.target)
    lane = resolve_directive_lane(root, run_id, args.lane_id, args.action, args.target)
    lane_id = lane_display_id(lane) if lane else "none"
    plan_id = plan.stem if plan else "none"
    status = args.status or default_directive_status(args.action)
    blocking = "yes" if status == "open" and args.action in BLOCKING_ACTIONS else "no"
    directive_id = args.directive_id or f"{today()}-{slug(args.title, 'architect-directive')}"
    directive_path = unique_path(state_dirs(root)["directives"], directive_id)
    created_at = now()
    next_action = args.next_action or directive_next_action(args.action, lane_id)
    content = read_template(DIRECTIVE_TEMPLATE).format(
        directive_id=directive_path.stem,
        status=status,
        action=args.action,
        target=args.target,
        blocking=blocking,
        date=dt.date.today().isoformat(),
        run_id=run_id,
        plan_id=plan_id,
        lane_id=lane_id,
        created_at=created_at,
        updated_at=created_at,
        summary=args.summary,
        instructions=args.instructions,
        acceptance=args.acceptance,
        next_action=next_action,
    )
    write(directive_path, content, args.dry_run)
    apply_directive_effect(root, run, plan, lane, directive_path, args, next_action)


def default_directive_status(action: str) -> str:
    if action in {"continue", "resume-lane"}:
        return "accepted"
    return "open"


def resolve_directive_plan(
    root: Path,
    run_id: str,
    plan_id: str | None,
    action: str,
    target: str,
) -> Path | None:
    if plan_id:
        plan = resolve_state_file(root, "execution-plans", plan_id)
        if header_value(plan.read_text(encoding="utf-8"), "Linked Run") != run_id:
            raise SystemExit(f"execution plan {plan_id} is not linked to run {run_id}")
        return plan
    if action == "replan" or target == "plan":
        plan = latest_plan_for_run(root, run_id)
        if plan is None:
            raise SystemExit(f"architect directive requires an Architect Execution Plan for run {run_id}")
        return plan
    return latest_plan_for_run(root, run_id)


def resolve_directive_lane(
    root: Path,
    run_id: str,
    lane_id: str | None,
    action: str,
    target: str,
) -> Path | None:
    if action in LANE_ACTIONS and target != "lane":
        raise SystemExit(f"{action} directive must target lane")
    if target == "lane" and not lane_id:
        raise SystemExit("lane directive requires --lane-id")
    if not lane_id:
        return None
    lane = lane_path_for(root, run_id, lane_id)
    if not lane.exists():
        raise SystemExit(f"lane not found for run {run_id}: {lane_id}")
    return lane


def apply_directive_effect(
    root: Path,
    run: Path,
    plan: Path | None,
    lane: Path | None,
    directive: Path,
    args: argparse.Namespace,
    next_action: str,
) -> None:
    action = args.action
    if action == "pause-lane":
        assert lane is not None
        pause_lane(lane, directive.stem, args.dry_run)
    elif action == "resume-lane":
        assert lane is not None
        resume_lane(root, run, lane, args.dry_run)
    elif action == "replan":
        if plan is None:
            raise SystemExit("replan directive requires an Architect Execution Plan")
        mark_plan_replan_required(plan, args.dry_run)
        mark_run_lanes_replan_required(root, run.stem, directive.stem, args.dry_run)
    run_text = update_header(run, phase="Architect Directive")
    if action == "replan":
        run_text = upsert_line_after(run_text, "Architect Gate Status: ", "failed", "Gate Status: ")
    run_text = append_bullet(
        run_text,
        "Architect Directives",
        f"{directive.stem}: {action} target={args.target} lane={lane_display_id(lane) if lane else 'none'}",
    )
    if action == "root-decision":
        run_text = append_bullet(run_text, "Root Decisions", f"{directive.stem}: {args.summary}")
    run_text = replace_section(run_text, "Next Action", next_action)
    run_text = append_event_text(run_text, f"Architect directive recorded: {directive.stem} ({action})")
    save(run, run_text, args.dry_run)


def pause_lane(lane: Path, directive_id: str, dry_run: bool) -> None:
    text = lane.read_text(encoding="utf-8")
    status = header_value(text, "Status") or "active"
    if header_value(text, "Integrated") == "yes":
        raise SystemExit(f"lane {lane_display_id(lane)} is already integrated")
    if status != "architect-paused":
        text = upsert_line_after(text, "Paused From Status: ", status, "Status: ")
    text = replace_line(text, "Status: ", "architect-paused")
    text = append_event_text(text, f"Lane paused by architect directive: {directive_id}")
    save(lane, text, dry_run)


def resume_lane(root: Path, run: Path, lane: Path, dry_run: bool) -> None:
    plan = latest_plan_for_run(root, run.stem)
    if plan is None:
        raise SystemExit(f"Architect Execution Plan required before resuming lane for run {run.stem}")
    plan_text = plan.read_text(encoding="utf-8")
    if header_value(plan_text, "Architect Gate Status") != "passed":
        raise SystemExit(f"Architect readiness gate must pass before resuming lane for run {run.stem}")
    if header_value(plan_text, "Status") not in {"active", "accepted"}:
        raise SystemExit(f"Architect Execution Plan {plan.stem} is not active")
    text = lane.read_text(encoding="utf-8")
    lane_id = lane_display_id(lane)
    if header_value(text, "Status") != "architect-paused":
        raise SystemExit(f"lane {lane_id} is not architect-paused")
    restored = header_value(text, "Paused From Status") or "active"
    if restored == "architect-paused":
        restored = "active"
    text = replace_line(text, "Status: ", restored)
    text = replace_line(text, "Paused From Status: ", "none")
    text = append_event_text(text, "Lane resumed by architect directive")
    save(lane, text, dry_run)
    mark_lane_pause_directives_addressed(root, run.stem, lane_id, dry_run)


def mark_plan_replan_required(plan: Path, dry_run: bool) -> None:
    text = plan.read_text(encoding="utf-8")
    text = replace_line(text, "Status: ", "replan-required")
    text = replace_line(text, "Architect Gate Status: ", "failed")
    text = replace_section(text, "Gate Result", "failed: architect directive requires a revised execution plan.")
    text = append_event_text(text, "Plan marked replan-required by architect directive")
    save(plan, text, dry_run)


def mark_run_lanes_replan_required(root: Path, run_id: str, directive_id: str, dry_run: bool) -> None:
    for lane in files_for_run(root, "lanes", run_id):
        text = lane.read_text(encoding="utf-8")
        if header_value(text, "Integrated") == "yes":
            continue
        text = replace_line(text, "Status: ", "replan-required")
        text = append_event_text(text, f"Lane stopped by architect replan directive: {directive_id}")
        save(lane, text, dry_run)


def mark_lane_pause_directives_addressed(root: Path, run_id: str, lane_id: str, dry_run: bool) -> None:
    for directive in open_directives(root, run_id):
        text = directive.read_text(encoding="utf-8")
        if header_value(text, "Action") == "pause-lane" and header_value(text, "Linked Lane") == lane_id:
            text = replace_line(text, "Status: ", "addressed")
            text = replace_line(text, "Blocking: ", "no")
            text = replace_line(text, "Updated At: ", now())
            text = append_event_text(text, "Addressed by resume-lane directive")
            save(directive, text, dry_run)


def mark_replan_directives_addressed(root: Path, run_id: str, plan_id: str, dry_run: bool) -> None:
    for directive in open_directives(root, run_id):
        text = directive.read_text(encoding="utf-8")
        if header_value(text, "Action") == "replan":
            text = replace_line(text, "Status: ", "addressed")
            text = replace_line(text, "Blocking: ", "no")
            text = replace_line(text, "Updated At: ", now())
            text = append_event_text(text, f"Addressed by gated execution plan: {plan_id}")
            save(directive, text, dry_run)


def mark_root_decision_directives_addressed(root: Path, run_id: str, decision_id: str, dry_run: bool) -> None:
    for directive in open_directives(root, run_id):
        text = directive.read_text(encoding="utf-8")
        if header_value(text, "Action") == "root-decision":
            text = replace_line(text, "Status: ", "addressed")
            text = replace_line(text, "Blocking: ", "no")
            text = replace_line(text, "Updated At: ", now())
            text = append_event_text(text, f"Addressed by root decision: {decision_id}")
            save(directive, text, dry_run)


def latest_plan_for_run(root: Path, run_id: str) -> Path | None:
    candidates = [
        path
        for path in files_for_run(root, "execution-plans", run_id)
        if header_value(path.read_text(encoding="utf-8"), "Status") != "superseded"
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def lane_path_for(root: Path, run_id: str, lane_id: str) -> Path:
    return state_dirs(root)["lanes"] / f"{run_id}--{lane_id}.md"


def lane_display_id(lane: Path) -> str:
    text = lane.read_text(encoding="utf-8")
    return header_value(text, "Lane ID") or lane.stem.split("--", 1)[-1]


def open_directives(root: Path, run_id: str) -> list[Path]:
    return [
        directive
        for directive in files_for_run(root, "directives", run_id)
        if header_value(directive.read_text(encoding="utf-8"), "Status") == "open"
    ]


def lane_work_directive_failures(root: Path, run_id: str, lane_id: str | None = None) -> list[str]:
    failures: list[str] = []
    for directive in open_directives(root, run_id):
        text = directive.read_text(encoding="utf-8")
        action = header_value(text, "Action")
        directive_lane = header_value(text, "Linked Lane")
        if action == "replan":
            failures.append(f"{directive.stem}: architect replan directive is open")
        elif action == "pause-lane" and (lane_id is None or directive_lane == lane_id):
            failures.append(f"{directive.stem}: lane {directive_lane} is paused by architect")
    return failures


def merge_ready_directive_failures(root: Path, run_id: str) -> list[str]:
    failures: list[str] = []
    for directive in open_directives(root, run_id):
        text = directive.read_text(encoding="utf-8")
        action = header_value(text, "Action")
        if action in BLOCKING_ACTIONS:
            lane = header_value(text, "Linked Lane") or "none"
            failures.append(f"{directive.stem}: open architect directive action={action} lane={lane}")
    return failures


def directive_next_action(action: str, lane_id: str) -> str:
    if action == "pause-lane":
        return f"Keep lane {lane_id} paused until architect issues resume-lane or replan."
    if action == "resume-lane":
        return f"Continue lane {lane_id} from its restored state."
    if action == "replan":
        return "Produce a revised Architect Execution Plan and rerun architect readiness gate."
    if action == "root-decision":
        return "Root must resolve the architect decision before accepted close."
    return "Continue from the architect directive."
