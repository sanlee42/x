from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
from pathlib import Path

from x_state_common import *
from x_state_directives import lane_work_directive_failures, mark_replan_directives_addressed


BANNED_DEFERRED_DECISIONS = re.compile(r"\b(TBD|figure out|use best judgment|decide later)\b", re.IGNORECASE)
PLAN_REQUIRED_SECTIONS = (
    "Objective",
    "Parallel Lanes",
    "Task Dependency Graph",
    "Lane Session Ownership",
    "Scope Boundaries",
    "Expected Artifacts",
    "Verification Matrix",
    "Reviewer Criteria",
    "Architect Merge Criteria",
    "Integration Order",
    "Known Risks",
    "Loopback Triggers",
    "Blocked-State Recovery",
    "Root Decisions Needed",
)
LANE_TABLE_COLUMNS = ("lane-id", "task-id", "allowed-scope", "forbidden-scope", "worktree-scope", "verification", "done-evidence")
LANE_ACTIVE_STATUSES = {"active", "code-changes-requested", "architect-changes-requested"}
HEARTBEAT_STALE_MINUTES = 60


def command_execution_plan(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    run_id = run_id_from_path(run)
    plan = existing_execution_plan(root, args.plan_id) if args.plan_id else None
    if plan and is_plan_status_update(args):
        update_execution_plan_status(run, plan, args)
        return
    require_materialized_run(run, "execution-plan")
    title = args.title or "Architect Execution Plan"
    plan_id = args.plan_id or f"{today()}-{slug(title, 'execution-plan')}"
    plan_path = unique_path(state_dirs(root)["execution-plans"], plan_id)
    contract = latest_for_run(root, "contracts", run_id)
    run_text = run.read_text(encoding="utf-8")
    content = read_template(EXECUTION_PLAN_TEMPLATE).format(
        plan_id=plan_path.stem,
        status=args.status or "active",
        final_verification_status=args.final_verification_status or "pending",
        date=dt.date.today().isoformat(),
        run_id=run_id,
        contract_id=contract.stem if contract else "none",
        integration_worktree=header_value(run_text, "Execution Worktree") or UNMATERIALIZED,
        integration_branch=header_value(run_text, "Execution Branch") or UNMATERIALIZED,
        objective=args.objective or "Pending.",
        parallel_lanes=args.parallel_lanes or "Pending.",
        dependency_graph=args.dependency_graph or "Pending.",
        lane_ownership=args.lane_ownership or "Pending.",
        allowed_scope=args.allowed_scope or "Pending.",
        forbidden_scope=args.forbidden_scope or "Pending.",
        expected_artifacts=args.expected_artifacts or "Pending.",
        verification_matrix=args.verification_matrix or "Pending.",
        reviewer_criteria=args.reviewer_criteria or "Pending.",
        architect_merge_criteria=args.architect_merge_criteria or "Pending.",
        integration_order=args.integration_order or "Pending.",
        known_risks=args.known_risks or "Pending.",
        loopback_triggers=args.loopback_triggers or "Pending.",
        blocked_recovery=args.blocked_recovery or "Pending.",
        root_decisions=args.root_decisions or "Pending.",
        final_verification=optional_text_arg(args, "final_verification", "Pending."),
    )
    write(plan_path, content, args.dry_run)
    run_text = update_header(run, phase="Architect Execution Plan")
    run_text = upsert_line_after(run_text, "Architect Gate Status: ", "not-run", "Gate Status: ")
    run_text = replace_section(run_text, "Architect Execution Plan", f"{plan_path.stem}: {title}")
    run_text = replace_section(run_text, "Next Action", args.next_action or f"Run architect readiness gate for {plan_path.stem}.")
    run_text = append_event_text(run_text, f"Architect Execution Plan created: {plan_path.stem}")
    save(run, run_text, args.dry_run)


def required_execution_plan_args(args: argparse.Namespace) -> dict[str, str | None]:
    return {
        "--title": args.title,
        "--objective": args.objective,
        "--parallel-lanes": args.parallel_lanes,
        "--dependency-graph": args.dependency_graph,
        "--lane-ownership": args.lane_ownership,
        "--allowed-scope": args.allowed_scope,
        "--forbidden-scope": args.forbidden_scope,
        "--expected-artifacts": args.expected_artifacts,
        "--verification-matrix": args.verification_matrix,
        "--reviewer-criteria": args.reviewer_criteria,
        "--architect-merge-criteria": args.architect_merge_criteria,
        "--integration-order": args.integration_order,
        "--known-risks": args.known_risks,
        "--loopback-triggers": args.loopback_triggers,
        "--blocked-recovery": args.blocked_recovery,
        "--root-decisions": args.root_decisions,
    }


def is_plan_status_update(args: argparse.Namespace) -> bool:
    supplied = [
        value
        for key, value in required_execution_plan_args(args).items()
        if key != "--title" and has_content(value or "")
    ]
    has_final_verification = args.final_verification is not None or args.final_verification_file is not None
    return not supplied and (args.final_verification_status is not None or args.status is not None or args.next_action or has_final_verification)


def update_execution_plan_status(run: Path, plan: Path, args: argparse.Namespace) -> None:
    plan_text = plan.read_text(encoding="utf-8")
    if header_value(plan_text, "Linked Run") != run.stem:
        raise SystemExit(f"execution plan {plan.stem} is not linked to run {run.stem}")
    if args.status is not None:
        plan_text = replace_line(plan_text, "Status: ", args.status)
    final_verification = optional_text_arg(args, "final_verification", "")
    if has_content(final_verification):
        plan_text = replace_section(plan_text, "Final Verification Evidence", final_verification)
    if args.final_verification_status is not None:
        if args.final_verification_status == "green" and not has_content(section_content(plan_text, "Final Verification Evidence")):
            raise SystemExit("final verification evidence is required before marking final verification green")
        plan_text = replace_line(plan_text, "Final Verification Status: ", args.final_verification_status)
    save(plan, plan_text, args.dry_run)
    run_text = update_header(run, phase="Architect Execution Plan")
    if args.next_action:
        run_text = replace_section(run_text, "Next Action", args.next_action)
    run_text = append_event_text(run_text, f"Architect Execution Plan updated: {plan.stem}")
    save(run, run_text, args.dry_run)


def command_architect_gate(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    plan = latest_execution_plan_for_run(root, run.stem)
    failures = architect_gate_failures(root, run, plan)
    if plan is None:
        raise SystemExit("architect readiness gate failed: missing Architect Execution Plan")
    plan_text = plan.read_text(encoding="utf-8")
    run_text = update_header(run, phase="Architect Readiness Gate")
    if failures:
        result = "failed:\n" + "\n".join(f"- {failure}" for failure in failures)
        plan_text = replace_line(plan_text, "Architect Gate Status: ", "failed")
        plan_text = replace_section(plan_text, "Gate Result", result)
        run_text = upsert_line_after(run_text, "Architect Gate Status: ", "failed", "Gate Status: ")
        run_text = replace_section(run_text, "Architect Gate", result)
        run_text = replace_section(run_text, "Next Action", "Fix Architect Execution Plan readiness failures before starting lanes.")
        save(plan, plan_text, args.dry_run)
        save(run, run_text, args.dry_run)
        raise SystemExit("architect readiness gate failed: " + "; ".join(failures))
    result = f"passed: {now()}"
    plan_text = replace_line(plan_text, "Architect Gate Status: ", "passed")
    plan_text = replace_section(plan_text, "Gate Result", result)
    run_text = upsert_line_after(run_text, "Architect Gate Status: ", "passed", "Gate Status: ")
    run_text = replace_section(run_text, "Architect Gate", result)
    run_text = replace_section(run_text, "Next Action", "Start lane sessions from the accepted Architect Execution Plan.")
    run_text = append_event_text(run_text, "Architect readiness gate passed")
    save(plan, plan_text, args.dry_run)
    mark_replan_directives_addressed(root, run.stem, plan.stem, args.dry_run)
    save(run, run_text, args.dry_run)


def architect_gate_failures(root: Path, run: Path, plan: Path | None) -> list[str]:
    failures: list[str] = []
    try:
        require_materialized_run(run, "architect readiness gate")
    except SystemExit as error:
        failures.append(str(error))
    if plan is None:
        failures.append("missing Architect Execution Plan")
        return failures
    text = plan.read_text(encoding="utf-8")
    if header_value(text, "Linked Run") != run.stem:
        failures.append(f"{plan.stem}: not linked to run {run.stem}")
    status = header_value(text, "Status") or "active"
    if status not in {"active", "accepted"}:
        failures.append(f"{plan.stem}: status is {status}, expected active or accepted")
    for section in PLAN_REQUIRED_SECTIONS:
        content = section_content(text, section)
        if not has_content(content):
            failures.append(f"{plan.stem}: missing {section}")
    failures.extend(deferred_decision_failures(text, plan.stem))
    lanes = parse_plan_lanes(text)
    if not lanes:
        failures.append(f"{plan.stem}: Parallel Lanes must include a markdown table with lane/task/scope/verification columns")
    integration_order = section_content(text, "Integration Order")
    for lane in lanes:
        lane_id = lane["lane-id"]
        for column in LANE_TABLE_COLUMNS:
            if not has_content(lane.get(column, "")):
                failures.append(f"{plan.stem}: lane {lane_id} missing {column.replace('-', ' ')}")
        task_id = lane.get("task-id", "")
        try:
            task = resolve_state_file(root, "tasks", task_id)
        except SystemExit:
            failures.append(f"{plan.stem}: lane {lane_id} references missing task {task_id}")
            continue
        task_text = task.read_text(encoding="utf-8")
        if header_value(task_text, "Linked Run") != run.stem:
            failures.append(f"{plan.stem}: lane {lane_id} task {task_id} is not linked to run {run.stem}")
        if not has_content(section_content(task_text, "Required Verification")):
            failures.append(f"{task_id}: task missing required verification")
        if not has_content(section_content(task_text, "Expected Done Evidence")):
            failures.append(f"{task_id}: task missing expected done evidence")
        if lane_id not in integration_order:
            failures.append(f"{plan.stem}: Integration Order does not include lane {lane_id}")
    lane_ids = [lane["lane-id"] for lane in lanes]
    duplicates = sorted({lane_id for lane_id in lane_ids if lane_ids.count(lane_id) > 1})
    for lane_id in duplicates:
        failures.append(f"{plan.stem}: duplicate lane id {lane_id}")
    task_ids = [lane["task-id"] for lane in lanes]
    for task_id in sorted({task_id for task_id in task_ids if task_ids.count(task_id) > 1}):
        failures.append(f"{plan.stem}: duplicate lane task {task_id}")
    return failures


def deferred_decision_failures(text: str, plan_id: str) -> list[str]:
    failures = []
    current_section = ""
    for line in text.splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
        if not BANNED_DEFERRED_DECISIONS.search(line):
            continue
        if current_section == "Root Decisions Needed" and "root decision" in line.lower():
            continue
        failures.append(f"{plan_id}: unresolved deferred decision in {current_section or 'header'}: {line.strip()}")
    return failures


def parse_plan_lanes(plan_text: str) -> list[dict[str, str]]:
    section = section_content(plan_text, "Parallel Lanes")
    rows = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    if len(rows) < 2:
        return []
    headers = [normalize_table_header(cell) for cell in rows[0]]
    missing_headers = [column for column in LANE_TABLE_COLUMNS if column not in headers]
    if missing_headers:
        return []
    lanes: list[dict[str, str]] = []
    for row in rows[1:]:
        if len(row) != len(headers):
            continue
        item = {header: value.strip() for header, value in zip(headers, row)}
        if item.get("lane-id"):
            lanes.append(item)
    return lanes


def normalize_table_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")


def latest_execution_plan_for_run(root: Path, run_id: str) -> Path | None:
    candidates = [
        path
        for path in files_for_run(root, "execution-plans", run_id)
        if header_value(path.read_text(encoding="utf-8"), "Status") != "superseded"
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def existing_execution_plan(root: Path, plan_id: str) -> Path | None:
    path = state_dirs(root)["execution-plans"] / f"{plan_id}.md"
    return path if path.exists() else None


def require_architect_gate_passed(root: Path, run: Path) -> Path:
    plan = latest_execution_plan_for_run(root, run.stem)
    if plan is None:
        raise SystemExit(f"Architect Execution Plan required before lane/session work for run {run.stem}")
    text = plan.read_text(encoding="utf-8")
    if header_value(text, "Architect Gate Status") != "passed":
        raise SystemExit(f"Architect readiness gate must pass before lane/session work for run {run.stem}")
    if header_value(text, "Status") not in {"active", "accepted"}:
        raise SystemExit(f"Architect Execution Plan {plan.stem} is not active")
    return plan


def lane_row_for_id(plan: Path, lane_id: str) -> dict[str, str]:
    lanes = parse_plan_lanes(plan.read_text(encoding="utf-8"))
    for lane in lanes:
        if lane["lane-id"] == lane_id:
            return lane
    raise SystemExit(f"lane {lane_id} is not present in Architect Execution Plan {plan.stem}")


def lane_state_id(run_id: str, lane_id: str) -> str:
    return f"{run_id}--{lane_id}"


def lane_path_for(root: Path, run_id: str, lane_id: str) -> Path:
    return state_dirs(root)["lanes"] / f"{lane_state_id(run_id, lane_id)}.md"


def resolve_lane(root: Path, run_id: str, lane_id: str) -> Path:
    path = lane_path_for(root, run_id, lane_id)
    if not path.exists():
        raise SystemExit(f"lane not found for run {run_id}: {lane_id}")
    return path


def lane_display_id(lane: Path) -> str:
    text = lane.read_text(encoding="utf-8")
    return header_value(text, "Lane ID") or lane.stem.split("--", 1)[-1]


def require_active_lane(lane: Path) -> None:
    text = lane.read_text(encoding="utf-8")
    lane_id = lane_display_id(lane)
    if header_value(text, "Integrated") == "yes":
        raise SystemExit(f"lane {lane_id} is already integrated")
    status = header_value(text, "Status")
    if status not in LANE_ACTIVE_STATUSES:
        raise SystemExit(f"lane {lane_id} is not active for attempts (status: {status or 'unknown'})")
    if status == "active" and header_value(text, "Last Attempt") not in {"", "none"}:
        raise SystemExit(f"lane {lane_id} already has an active attempt: {header_value(text, 'Last Attempt')}")


def command_lane_start(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    task = resolve_state_file(root, "tasks", args.task_id)
    task_text = task.read_text(encoding="utf-8")
    run_id = header_value(task_text, "Linked Run")
    if not run_id:
        raise SystemExit(f"task missing Linked Run: {task.stem}")
    run = resolve_run(root, args.run_id or run_id)
    if run.stem != run_id:
        raise SystemExit(f"task {task.stem} is linked to run {run_id}, not {run.stem}")
    plan = require_architect_gate_passed(root, run)
    lane_id = args.lane_id
    lane_row = lane_row_for_id(plan, lane_id)
    if lane_row["task-id"] != task.stem:
        raise SystemExit(f"lane {lane_id} is linked to task {lane_row['task-id']}, not {task.stem}")
    lane_path = lane_path_for(root, run.stem, lane_id)
    if lane_path.exists():
        raise SystemExit(f"lane already exists: {lane_id}")
    integration_worktree = require_materialized_run(run, "lane-start")
    run_text = run.read_text(encoding="utf-8")
    integration_branch = header_value(run_text, "Execution Branch") or "HEAD"
    worktree = lane_worktree_default(integration_worktree, lane_row, args.worktree)
    branch = args.branch or f"{integration_branch}-{slug(lane_id, 'lane')}"
    create_lane_worktree(
        control_root=header_path(run_text, "Control Root") or root,
        worktree=worktree,
        branch=branch,
        base=integration_branch,
        reuse_worktree=args.reuse_worktree,
        dry_run=args.dry_run,
    )
    plan_text = plan.read_text(encoding="utf-8")
    content = read_template(LANE_TEMPLATE).format(
        lane_id=lane_id,
        status="active",
        date=dt.date.today().isoformat(),
        run_id=run.stem,
        plan_id=plan.stem,
        task_id=task.stem,
        worktree=worktree,
        branch=branch,
        integration_worktree=integration_worktree,
        integration_branch=integration_branch,
        objective=section_content(task_text, "Goal"),
        allowed_scope=lane_row["allowed-scope"],
        forbidden_scope=lane_row["forbidden-scope"],
        verification=lane_row["verification"],
        done_evidence=lane_row["done-evidence"],
        runbook=section_content(plan_text, "Lane Session Ownership"),
        loop_policy=section_content(plan_text, "Loopback Triggers"),
        expected_artifacts=section_content(plan_text, "Expected Artifacts"),
        failure_recovery=section_content(plan_text, "Blocked-State Recovery"),
        escalation_conditions=section_content(plan_text, "Root Decisions Needed"),
        created_at=now(),
    )
    write(lane_path, content, args.dry_run)
    run_text = update_header(run, phase="Lane Active", needs_user=args.needs_user)
    run_text = append_bullet(run_text, "Lanes", f"{lane_id}: {task.stem} active ({worktree})")
    run_text = replace_section(run_text, "Next Action", args.next_action or f"Start implementation attempt for lane {lane_id}.")
    run_text = append_event_text(run_text, f"Lane started: {lane_id}")
    save(run, run_text, args.dry_run)


def lane_worktree_default(integration_worktree: Path, lane_row: dict[str, str], explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit).expanduser()
        if not path.is_absolute():
            path = integration_worktree.parent / path
        return path.resolve()
    scope = slug(lane_row.get("worktree-scope") or lane_row["lane-id"], "lane")
    return (integration_worktree.parent / f"{integration_worktree.name}-{scope}").resolve()


def create_lane_worktree(
    *,
    control_root: Path,
    worktree: Path,
    branch: str,
    base: str,
    reuse_worktree: bool,
    dry_run: bool,
) -> None:
    if reuse_worktree:
        if not worktree.exists():
            raise SystemExit(f"--reuse-worktree requires an existing lane worktree: {worktree}")
        assert_same_git_common_dir(control_root, worktree)
        return
    if worktree.exists():
        raise SystemExit(f"lane worktree already exists: {worktree}; use --reuse-worktree or choose another --worktree")
    if git_branch_exists(control_root, branch):
        raise SystemExit(f"lane branch already exists: {branch}; choose another --branch")
    if not dry_run:
        subprocess.check_call(["git", "-C", str(control_root), "worktree", "add", str(worktree), "-b", branch, base])


def git_branch_exists(root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        check=False,
    )
    return result.returncode == 0


def assert_same_git_common_dir(first: Path, second: Path) -> None:
    expected = git_path(first, "rev-parse", "--git-common-dir")
    actual = git_path(second, "rev-parse", "--git-common-dir")
    if expected != actual:
        raise SystemExit(f"worktree belongs to a different git common dir: {second} ({actual} != {expected})")


def command_lane_status(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    lanes = files_for_run(root, "lanes", run.stem)
    print(f"# x Lanes: {run.stem}")
    if not lanes:
        print("- none")
        return
    for lane in lanes:
        print(f"- {lane_status_summary(lane)}")


def command_lane_update(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    lane = resolve_lane(root, run.stem, args.lane_id)
    timestamp = now()
    text = lane.read_text(encoding="utf-8")
    text = upsert_line_after(text, "Heartbeat At: ", timestamp, "Architect Review: ")
    text = upsert_line_after(text, "Heartbeat Actor: ", args.actor, "Heartbeat At: ")
    text = upsert_line_after(text, "Heartbeat Session: ", args.session, "Heartbeat Actor: ")
    text = upsert_line_after(text, "Heartbeat Status: ", args.heartbeat_status, "Heartbeat Session: ")
    text = replace_section(text, "Current Activity", args.activity)
    text = replace_section(text, "Current Blocker", args.blocker)
    text = replace_section(text, "Lane Next Action", args.next_action)
    text = append_event_text(text, f"Lane heartbeat: {args.actor}/{args.heartbeat_status} session={args.session}")
    save(lane, text, args.dry_run)


def lane_status_summary(lane: Path) -> str:
    text = lane.read_text(encoding="utf-8")
    parts = [
        lane_display_id(lane),
        f"status={header_value(text, 'Status') or 'unknown'}",
        f"task={header_value(text, 'Linked Task') or 'unknown'}",
        f"attempt={header_value(text, 'Last Attempt') or 'none'}",
        f"code-review={header_value(text, 'Code Review') or 'none'}",
        f"architect-review={header_value(text, 'Architect Review') or 'none'}",
        f"integrated={header_value(text, 'Integrated') or 'no'}",
        f"heartbeat={compact_state_value(header_value(text, 'Heartbeat Status'))}",
        f"actor={compact_state_value(header_value(text, 'Heartbeat Actor'))}",
        f"session={compact_state_value(header_value(text, 'Heartbeat Session'))}",
        f"at={compact_state_value(header_value(text, 'Heartbeat At'))}",
        f"activity={compact_state_value(section_content(text, 'Current Activity'))}",
        f"blocker={compact_state_value(section_content(text, 'Current Blocker'))}",
        f"next={compact_state_value(section_content(text, 'Lane Next Action'))}",
        f"attention={lane_attention(text)}",
    ]
    return "; ".join(parts)


def lane_heartbeats_summary(root: Path, run: Path) -> str:
    lanes = files_for_run(root, "lanes", run.stem)
    if not lanes:
        return "- none"
    lines = []
    for lane in lanes:
        text = lane.read_text(encoding="utf-8")
        lines.append(
            "- "
            + "; ".join(
                [
                    lane_display_id(lane),
                    f"status={header_value(text, 'Status') or 'unknown'}",
                    f"heartbeat={compact_state_value(header_value(text, 'Heartbeat Status'))}",
                    f"actor={compact_state_value(header_value(text, 'Heartbeat Actor'))}",
                    f"session={compact_state_value(header_value(text, 'Heartbeat Session'))}",
                    f"at={compact_state_value(header_value(text, 'Heartbeat At'))}",
                    f"activity={compact_state_value(section_content(text, 'Current Activity'))}",
                    f"blocker={compact_state_value(section_content(text, 'Current Blocker'))}",
                    f"next={compact_state_value(section_content(text, 'Lane Next Action'))}",
                    f"attention={lane_attention(text)}",
                ]
            )
        )
    return "\n".join(lines)


def lane_attention(lane_text: str) -> str:
    if blocking_present(section_content(lane_text, "Current Blocker")):
        return "blocker"
    heartbeat_at = header_value(lane_text, "Heartbeat At")
    if not state_value_present(heartbeat_at):
        return "no-heartbeat"
    parsed = parse_heartbeat_at(heartbeat_at)
    if parsed is None:
        return "stale"
    current = dt.datetime.now(parsed.tzinfo) if parsed.tzinfo else dt.datetime.now()
    if current - parsed > dt.timedelta(minutes=HEARTBEAT_STALE_MINUTES):
        return "stale"
    return "none"


def parse_heartbeat_at(value: str) -> dt.datetime | None:
    try:
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        return dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None


def compact_state_value(value: str, *, limit: int = 180) -> str:
    compacted = " ".join(value.strip().split())
    if not state_value_present(compacted):
        return "none"
    if len(compacted) > limit:
        return compacted[: limit - 3].rstrip() + "..."
    return compacted


def state_value_present(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized not in {
        "",
        "-",
        "pending.",
        "none",
        "none.",
        "- none",
        "- none.",
        "not specified.",
        "not provided.",
        "no heartbeat yet.",
    }


def lanes_for_task(root: Path, run_id: str, task_id: str) -> list[Path]:
    return [
        lane
        for lane in files_for_run(root, "lanes", run_id)
        if header_value(lane.read_text(encoding="utf-8"), "Linked Task") == task_id
    ]


def active_lane_for_task(root: Path, run_id: str, task_id: str, lane_id: str | None = None) -> Path:
    lanes = lanes_for_task(root, run_id, task_id)
    if lane_id:
        path = resolve_lane(root, run_id, lane_id)
        text = path.read_text(encoding="utf-8")
        if header_value(text, "Linked Run") != run_id or header_value(text, "Linked Task") != task_id:
            raise SystemExit(f"lane {lane_id} is not linked to task {task_id} in run {run_id}")
        failures = lane_work_directive_failures(root, run_id, lane_display_id(path))
        if failures:
            raise SystemExit("lane work blocked: " + "; ".join(failures))
        require_active_lane(path)
        return path
    active = [
        lane
        for lane in lanes
        if header_value(lane.read_text(encoding="utf-8"), "Status") in LANE_ACTIVE_STATUSES
        and header_value(lane.read_text(encoding="utf-8"), "Integrated") != "yes"
    ]
    if not active:
        failures = lane_work_directive_failures(root, run_id)
        if failures:
            raise SystemExit("lane work blocked: " + "; ".join(failures))
        raise SystemExit(f"attempt-start requires an active lane for task {task_id}")
    if len(active) > 1:
        ids = ", ".join(lane_display_id(lane) for lane in active)
        raise SystemExit(f"multiple active lanes for task {task_id}; pass --lane-id ({ids})")
    require_active_lane(active[0])
    return active[0]


def lane_for_attempt(root: Path, attempt: Path) -> Path | None:
    attempt_text = attempt.read_text(encoding="utf-8")
    lane_id = header_value(attempt_text, "Linked Lane")
    if not lane_id:
        return None
    run_id = header_value(attempt_text, "Linked Run")
    if not run_id:
        raise SystemExit(f"attempt missing Linked Run: {attempt.stem}")
    return resolve_lane(root, run_id, lane_id)


def lane_worktree(lane: Path) -> Path:
    value = header_value(lane.read_text(encoding="utf-8"), "Worktree")
    if not value:
        raise SystemExit(f"lane missing Worktree: {lane_display_id(lane)}")
    path = Path(value).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"lane worktree is missing: {path}")
    return path


def mark_lane_attempt_started(lane: Path, attempt_id: str, dry_run: bool) -> None:
    text = lane.read_text(encoding="utf-8")
    text = replace_line(text, "Status: ", "active")
    text = replace_line(text, "Last Attempt: ", attempt_id)
    text = append_event_text(text, f"Attempt started: {attempt_id}")
    save(lane, text, dry_run)


def mark_lane_attempt_result(root: Path, attempt: Path, dry_run: bool) -> None:
    lane = lane_for_attempt(root, attempt)
    if lane is None:
        return
    attempt_text = attempt.read_text(encoding="utf-8")
    status = "blocked" if attempt_has_blockers(attempt_text) else "attempt-done"
    lane_text = replace_line(lane.read_text(encoding="utf-8"), "Status: ", status)
    lane_text = append_event_text(lane_text, f"Attempt result recorded: {attempt.stem}")
    save(lane, lane_text, dry_run)


def mark_lane_code_review(root: Path, review: Path, dry_run: bool) -> None:
    review_text = review.read_text(encoding="utf-8")
    attempt = resolve_state_file(root, "attempts", header_value(review_text, "Linked Attempt"))
    lane = lane_for_attempt(root, attempt)
    if lane is None:
        return
    recommendation = header_value(review_text, "Recommendation")
    if recommendation == "ready":
        status = "code-review-ready"
    elif recommendation == "changes-requested":
        status = "code-changes-requested"
    else:
        status = "blocked"
    lane_text = lane.read_text(encoding="utf-8")
    lane_text = replace_line(lane_text, "Status: ", status)
    lane_text = replace_line(lane_text, "Code Review: ", review.stem)
    lane_text = append_event_text(lane_text, f"Code review recorded: {review.stem} ({recommendation})")
    save(lane, lane_text, dry_run)


def command_architect_review(args: argparse.Namespace) -> None:
    if args.recommendation == "merge-ok" and blocking_present(args.blocking_findings):
        raise SystemExit("merge-ok architect review cannot include blocking findings")
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    lane = resolve_lane(root, run.stem, args.lane_id)
    lane_text = lane.read_text(encoding="utf-8")
    lane_id = lane_display_id(lane)
    failures = lane_work_directive_failures(root, run.stem, lane_id)
    if failures:
        raise SystemExit("architect-review blocked: " + "; ".join(failures))
    plan = require_architect_gate_passed(root, run)
    if header_value(lane_text, "Linked Plan") != plan.stem:
        raise SystemExit(f"lane {lane_id} is linked to plan {header_value(lane_text, 'Linked Plan')}, not active plan {plan.stem}")
    attempt = resolve_state_file(root, "attempts", args.attempt_id)
    attempt_text = attempt.read_text(encoding="utf-8")
    lane_task_id = header_value(lane_text, "Linked Task")
    if header_value(attempt_text, "Linked Run") != run.stem:
        raise SystemExit(f"attempt {attempt.stem} is not linked to run {run.stem}")
    if header_value(attempt_text, "Linked Task") != lane_task_id:
        raise SystemExit(f"attempt {attempt.stem} is not linked to lane task {lane_task_id}")
    if header_value(attempt_text, "Linked Lane") != lane_id:
        raise SystemExit(f"attempt {attempt.stem} is not linked to lane {lane_id}")
    if header_value(lane_text, "Last Attempt") != attempt.stem:
        raise SystemExit(f"architect-review attempt must be latest lane attempt: {header_value(lane_text, 'Last Attempt')}")
    ready_review = ready_review_for_attempt(root, attempt.stem)
    if ready_review is None:
        raise SystemExit(f"architect-review requires a ready code review for attempt {attempt.stem}")
    review_id = args.review_id or f"{today()}-{slug(args.title, 'architect-review')}"
    review_path = unique_path(state_dirs(root)["architect-reviews"], review_id)
    source_architect_review_id = header_value(attempt_text, "Source Architect Review") or "none"
    next_action = architect_review_next_action(args.recommendation, lane_id)
    content = read_template(ARCHITECT_REVIEW_TEMPLATE).format(
        review_id=review_path.stem,
        status=args.status,
        recommendation=args.recommendation,
        date=dt.date.today().isoformat(),
        run_id=run.stem,
        plan_id=plan.stem,
        lane_id=lane_id,
        task_id=lane_task_id,
        attempt_id=attempt.stem,
        source_architect_review_id=source_architect_review_id,
        summary=args.summary,
        criteria=args.criteria,
        blocking_findings=args.blocking_findings or "- None.",
        integration_risk=args.integration_risk,
        verification=args.verification,
        next_action=args.next_action or next_action,
    )
    write(review_path, content, args.dry_run)
    apply_architect_review_result(root, run, plan, lane, review_path, attempt, args)


def ready_review_for_attempt(root: Path, attempt_id: str) -> Path | None:
    candidates = [
        review
        for review in files_for_header(root, "reviews", "Linked Attempt", attempt_id)
        if item_recommendation(review) == "ready"
    ]
    return candidates[-1] if candidates else None


def architect_review_next_action(recommendation: str, lane_id: str) -> str:
    if recommendation == "merge-ok":
        return f"Integrate lane {lane_id} into the integration worktree."
    if recommendation == "changes-requested":
        return f"Start a fix attempt for lane {lane_id} from this architect review."
    if recommendation == "replan":
        return "Stop lane integration and produce a revised Architect Execution Plan."
    return f"Resolve architect blocker for lane {lane_id}."


def apply_architect_review_result(
    root: Path,
    run: Path,
    plan: Path,
    lane: Path,
    review: Path,
    attempt: Path,
    args: argparse.Namespace,
) -> None:
    recommendation = args.recommendation
    lane_id = lane_display_id(lane)
    status_map = {
        "merge-ok": "architect-merge-ok",
        "changes-requested": "architect-changes-requested",
        "blocked": "blocked",
        "replan": "replan-required",
    }
    lane_text = lane.read_text(encoding="utf-8")
    lane_text = replace_line(lane_text, "Status: ", status_map[recommendation])
    lane_text = replace_line(lane_text, "Architect Review: ", review.stem)
    lane_text = append_event_text(lane_text, f"Architect review recorded: {review.stem} ({recommendation})")
    save(lane, lane_text, args.dry_run)
    if recommendation == "merge-ok":
        mark_source_architect_review_addressed(root, attempt, args.dry_run)
    if recommendation == "replan":
        plan_text = replace_line(plan.read_text(encoding="utf-8"), "Status: ", "replan-required")
        plan_text = replace_line(plan_text, "Architect Gate Status: ", "failed")
        save(plan, plan_text, args.dry_run)
    run_text = update_header(run, phase="Architect Integration Review", needs_user=args.needs_user)
    run_text = append_bullet(run_text, "Architect Reviews", f"{review.stem}: {lane_id} {recommendation}")
    if recommendation in {"changes-requested", "blocked", "replan"}:
        run_text = append_bullet(run_text, "Fix Loop", f"{review.stem}: architect {recommendation}")
    if recommendation == "replan":
        run_text = upsert_line_after(run_text, "Architect Gate Status: ", "failed", "Gate Status: ")
    run_text = replace_section(run_text, "Next Action", args.next_action or architect_review_next_action(recommendation, lane_id))
    run_text = append_event_text(run_text, f"Architect review recorded: {review.stem}")
    save(run, run_text, args.dry_run)


def mark_source_architect_review_addressed(root: Path, attempt: Path, dry_run: bool) -> None:
    source_id = header_value(attempt.read_text(encoding="utf-8"), "Source Architect Review")
    if not source_id or source_id == "none":
        return
    source = resolve_state_file(root, "architect-reviews", source_id)
    source_text = replace_line(source.read_text(encoding="utf-8"), "Status: ", "addressed")
    save(source, source_text, dry_run)
