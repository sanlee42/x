from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from x_state_common import *
from x_state_directives import lane_work_directive_failures, merge_ready_directive_failures
from x_state_execution import (
    lane_display_id,
    lane_deep_review_required,
    architect_merge_ok_required_for_lane,
    lane_row_for_id,
    lane_path_for,
    lane_worktree,
    merge_ok_architect_reviews_for_attempt,
    ready_review_for_attempt,
    require_architect_gate_passed,
)


def command_integrate(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    lane = resolve_lane_for_integration(root, run.stem, args.lane_id)
    lane_text = lane.read_text(encoding="utf-8")
    lane_id = lane_display_id(lane)
    require_architect_gate_passed(root, run)
    directive_failures = lane_work_directive_failures(root, run.stem, lane_id)
    if directive_failures:
        raise SystemExit("integrate blocked: " + "; ".join(directive_failures))
    lane_tree = lane_worktree(lane)
    failures = lane_integration_failures(root, lane, lane_tree)
    if failures:
        raise SystemExit("integrate failed: " + "; ".join(failures))
    integration_tree = require_materialized_run(run, "integrate")
    patch = lane_patch(lane_tree, lane_text)
    if patch.strip():
        apply_patch_to_integration(integration_tree, patch, args.dry_run)
    lane_text = lane.read_text(encoding="utf-8")
    lane_text = replace_line(lane_text, "Status: ", "integrated")
    lane_text = replace_line(lane_text, "Integrated: ", "yes")
    lane_text = replace_section(lane_text, "Integration Notes", args.notes or "Applied lane diff to integration worktree.")
    lane_text = append_event_text(lane_text, "Lane integrated into integration worktree")
    save(lane, lane_text, args.dry_run)
    run_text = update_header(run, phase="Integration")
    run_text = append_bullet(run_text, "Integrated Lanes", lane_id)
    run_text = replace_section(run_text, "Next Action", args.next_action or "Continue integration order or run final verification matrix.")
    run_text = append_event_text(run_text, f"Lane integrated: {lane_id}")
    save(run, run_text, args.dry_run)


def resolve_lane_for_integration(root: Path, run_id: str, lane_id: str) -> Path:
    lane = lane_path_for(root, run_id, lane_id)
    if not lane.exists():
        raise SystemExit(f"lane not found for run {run_id}: {lane_id}")
    return lane


def lane_integration_failures(root: Path, lane: Path, lane_tree: Path) -> list[str]:
    text = lane.read_text(encoding="utf-8")
    lane_id = lane_display_id(lane)
    failures: list[str] = []
    if header_value(text, "Integrated") == "yes":
        failures.append(f"{lane_id}: already integrated")
    if header_value(text, "Status") not in {"integration-ready", "architect-merge-ok"}:
        failures.append(f"{lane_id}: lane is not integration-ready")
    attempt_id = header_value(text, "Last Attempt")
    if not attempt_id or attempt_id == "none":
        failures.append(f"{lane_id}: missing attempt")
        return failures
    if ready_review_for_attempt(root, attempt_id) is None:
        if lane_deep_review_required(text):
            failures.append(f"{lane_id}: deep review required; missing ready code review for latest attempt")
        else:
            failures.append(f"{lane_id}: missing ready code review for latest attempt")
    failures.extend(architect_review_failures(root, lane_id, text, attempt_id))
    untracked = untracked_files(lane_tree)
    if untracked:
        failures.append(f"{lane_id}: untracked files are not captured by integration diff: {', '.join(untracked)}")
    return failures


def architect_review_failures(root: Path, lane_id: str, lane_text: str, attempt_id: str) -> list[str]:
    failures = []
    risk_level, risk_failures = lane_risk_level(root, lane_id, lane_text)
    failures.extend(risk_failures)
    required = architect_reviews_required_for_integration(root, lane_id, lane_text)
    if required == 0:
        return failures
    merge_ok_reviews = merge_ok_architect_reviews_for_attempt(root, lane_text, lane_id, attempt_id)
    if len(merge_ok_reviews) < required:
        failures.append(architect_review_requirement_message(lane_id, risk_level, required, len(merge_ok_reviews)))
    return failures


def architect_reviews_required_for_integration(root: Path, lane_id: str, lane_text: str) -> int:
    run_id = header_value(lane_text, "Linked Run")
    lane = lane_path_for(root, run_id, lane_id)
    if not lane.exists():
        return 1
    return architect_merge_ok_required_for_lane(root, lane)


def architect_review_requirement_message(lane_id: str, risk_level: str, required: int, found: int) -> str:
    if risk_level == "critical":
        return (
            f"{lane_id}: critical-risk lane requires 2 distinct architect merge-ok review records "
            f"for latest attempt (found {found})"
        )
    if risk_level == "high":
        return (
            f"{lane_id}: high-risk lane requires 1 architect merge-ok review record "
            f"for latest attempt (found {found})"
        )
    return (
        f"{lane_id}: standard lane selected for architect sampling requires 1 architect merge-ok "
        f"review record for latest attempt (found {found})"
    )


def lane_risk_level(root: Path, lane_id: str, lane_text: str) -> tuple[str, list[str]]:
    plan_id = header_value(lane_text, "Linked Plan")
    if plan_id:
        try:
            plan = resolve_state_file(root, "execution-plans", plan_id)
            risk_level = normalized_state_value(lane_row_for_id(plan, lane_id).get("risk-level", ""))
        except SystemExit as error:
            return "", [f"{lane_id}: cannot read risk level from linked execution plan {plan_id}: {error}"]
        if not risk_level:
            return "", [f"{lane_id}: linked execution plan {plan_id} is missing risk level"]
        return risk_level, []
    return normalized_state_value(header_value(lane_text, "Risk Level")), []


def normalized_state_value(value: str) -> str:
    return " ".join(value.strip().split()).lower()


def lane_patch(lane_tree: Path, lane_text: str) -> str:
    base = lane_integration_base(lane_tree, header_value(lane_text, "Integration Branch") or "HEAD")
    return git_raw_output(lane_tree, "diff", "--binary", base)


def lane_integration_base(lane_tree: Path, integration_branch: str) -> str:
    return git_raw_output(lane_tree, "merge-base", "HEAD", integration_branch).strip()


def untracked_files(root: Path) -> list[str]:
    output = git_raw_output(root, "ls-files", "--others", "--exclude-standard")
    return [line for line in output.splitlines() if line.strip()]


def apply_patch_to_integration(integration_tree: Path, patch: str, dry_run: bool) -> None:
    if dry_run:
        print(patch)
        return
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(patch)
        patch_path = Path(handle.name)
    try:
        subprocess.check_call(["git", "-C", str(integration_tree), "apply", "--3way", str(patch_path)])
    finally:
        patch_path.unlink(missing_ok=True)


def git_raw_output(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        raise SystemExit(f"git command failed: git -C {root} {' '.join(args)}")


def execution_plan_merge_ready_failures(root: Path, run: Path) -> list[str]:
    from x_state_execution import latest_execution_plan_for_run, parse_plan_lanes

    plan = latest_execution_plan_for_run(root, run.stem)
    failures: list[str] = []
    if plan is None:
        return ["missing Architect Execution Plan"]
    plan_text = plan.read_text(encoding="utf-8")
    if header_value(plan_text, "Architect Gate Status") != "passed":
        failures.append(f"{plan.stem}: architect readiness gate has not passed")
    if header_value(plan_text, "Final Verification Status") != "green":
        failures.append(f"{plan.stem}: final verification matrix is not green")
    if not has_content(section_content(plan_text, "Final Verification Evidence")):
        failures.append(f"{plan.stem}: missing final verification evidence")
    planned_lanes = parse_plan_lanes(plan_text)
    if not planned_lanes:
        failures.append(f"{plan.stem}: no validated lanes")
    for planned_lane in planned_lanes:
        failures.extend(planned_lane_failures(root, run, plan, planned_lane["lane-id"]))
    failures.extend(merge_ready_directive_failures(root, run.stem))
    failures.extend(unresolved_blocking_risks(root, run.stem))
    return failures


def planned_lane_failures(root: Path, run: Path, plan: Path, lane_id: str) -> list[str]:
    lane = lane_path_for(root, run.stem, lane_id)
    if not lane.exists():
        return [f"{plan.stem}: lane {lane_id} has not started"]
    lane_text = lane.read_text(encoding="utf-8")
    failures = []
    if header_value(lane_text, "Linked Plan") != plan.stem:
        failures.append(f"{lane_id}: lane is not linked to active plan {plan.stem}")
    if header_value(lane_text, "Integrated") != "yes":
        failures.append(f"{lane_id}: lane is not integrated")
    if header_value(lane_text, "Status") != "integrated":
        failures.append(f"{lane_id}: lane status is not integrated")
    attempt_id = header_value(lane_text, "Last Attempt")
    if not attempt_id or attempt_id == "none":
        failures.append(f"{lane_id}: missing latest attempt")
        return failures
    if ready_review_for_attempt(root, attempt_id) is None:
        if lane_deep_review_required(lane_text):
            failures.append(f"{lane_id}: deep review required; latest attempt lacks ready code review")
        else:
            failures.append(f"{lane_id}: latest attempt lacks ready code review")
    failures.extend(architect_review_failures(root, lane_id, lane_text, attempt_id))
    return failures


def unresolved_blocking_risks(root: Path, run_id: str) -> list[str]:
    failures = []
    for risk in files_for_run(root, "risks", run_id):
        text = risk.read_text(encoding="utf-8")
        marked_blocking = "blocking: yes" in text.lower() or "[blocking]" in text.lower()
        if header_value(text, "Status") not in {"closed", "accepted", "superseded"} and (header_value(text, "Severity") in {"high", "critical"} or marked_blocking):
            failures.append(f"{risk.stem}: unresolved blocking risk")
    return failures
