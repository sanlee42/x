from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from x_state_common import *
from x_state_directives import lane_work_directive_failures, merge_ready_directive_failures
from x_state_execution import lane_display_id, lane_for_attempt, lane_status_summary, lane_worktree, latest_execution_plan_for_run
from x_state_integration import lane_integration_base, untracked_files
from x_state_mailbox import open_mailbox_summary
from x_state_discussion import (
    compact,
    discussion_summary,
    latest_accepted_intake_for_discussion,
    normalize_role_reference,
    require_interaction_writable,
    resolve_discussion,
    role_card_content,
    role_briefs_for_discussion,
)


def project_context(root: Path) -> str:
    candidates = [
        root / "PROJECT_CONSTRAINTS.md",
        root / "AGENTS.md",
        root / ".x/project/profile.md",
    ]
    lines = ["Load these files in order before answering:"]
    for path in candidates:
        label = path.relative_to(root)
        if path.exists():
            lines.append(f"- `{label}`")
        else:
            lines.append(f"- `{label}` (not present)")
    lines.append("")
    lines.append("If project context conflicts with the x package, stop and report the conflict instead of guessing.")
    return "\n".join(lines)


def recent_state_summary(root: Path, run_id: str) -> str:
    lines: list[str] = []
    for kind in (
        "discussions",
        "role-briefs",
        "architect-intakes",
        "briefs",
        "contracts",
        "execution-plans",
        "lanes",
        "tasks",
        "attempts",
        "reviews",
        "architect-reviews",
        "directives",
        "decisions",
        "risks",
    ):
        items = files_for_run(root, kind, run_id)
        if not items:
            continue
        lines.append(f"{kind}:")
        for path in items[-5:]:
            text = path.read_text(encoding="utf-8")
            status = header_value(text, "Status") or "n/a"
            recommendation = header_value(text, "Recommendation")
            suffix = f", recommendation={recommendation}" if recommendation else ""
            title = text.splitlines()[0].lstrip("# ").strip() if text.splitlines() else path.stem
            lines.append(f"- {path.stem}: {status}{suffix}; {title}")
    return "\n".join(lines) if lines else "No prior x state records for this run."


def architect_control_board(root: Path, run: Path) -> str:
    run_text = run.read_text(encoding="utf-8")
    lines = [
        f"Run: {run.stem}",
        f"Status: {header_value(run_text, 'Status') or 'unknown'}",
        f"Phase: {header_value(run_text, 'Current Phase') or 'unknown'}",
        f"Needs User: {header_value(run_text, 'Needs User') or 'unknown'}",
        f"Execution: {header_value(run_text, 'Execution Status') or UNMATERIALIZED}",
        f"Architect Gate: {header_value(run_text, 'Architect Gate Status') or 'not-run'}",
    ]
    plan = latest_execution_plan_for_run(root, run.stem)
    if plan:
        plan_text = plan.read_text(encoding="utf-8")
        lines.append(
            f"Plan: {plan.stem}; status={header_value(plan_text, 'Status') or 'unknown'}; "
            f"final={header_value(plan_text, 'Final Verification Status') or 'unknown'}"
        )
    else:
        lines.append("Plan: none")
    lines.append("Lanes:")
    lanes = files_for_run(root, "lanes", run.stem)
    if lanes:
        for lane in lanes:
            lines.append(f"- {lane_status_summary(lane)}")
    else:
        lines.append("- none")
    lines.append("Open Directives:")
    directives = [
        directive
        for directive in files_for_run(root, "directives", run.stem)
        if header_value(directive.read_text(encoding="utf-8"), "Status") == "open"
    ]
    if directives:
        for directive in directives:
            text = directive.read_text(encoding="utf-8")
            lines.append(
                f"- {directive.stem}: action={header_value(text, 'Action')}; "
                f"target={header_value(text, 'Target')}; lane={header_value(text, 'Linked Lane') or 'none'}; "
                f"blocking={header_value(text, 'Blocking') or 'no'}"
            )
    else:
        lines.append("- none")
    lines.append("Open Mailbox:")
    lines.append(open_mailbox_summary(root, run.stem))
    merge_blocks = merge_ready_directive_failures(root, run.stem)
    if merge_blocks:
        lines.append("Merge Blocking Directives:")
        lines.extend(f"- {failure}" for failure in merge_blocks)
    return "\n".join(lines)


def package_payload(
    root: Path,
    *,
    role: str,
    run: Path,
    task: Path | None,
    attempt: Path | None,
    review: Path | None,
    lane: Path | None,
    diff_stat: str,
    diff: str,
    verification: str,
    notes: str,
    architect_intakes: list[Path] | None = None,
) -> tuple[str, str, str]:
    run_text = run.read_text(encoding="utf-8")
    execution = execution_summary(run, lane)
    ledger = ledger_path(root)
    ledger_text = ledger.read_text(encoding="utf-8") if ledger.exists() else "No x ledger found."
    contract = latest_for_run(root, "contracts", run.stem)
    execution_plan = latest_execution_plan_for_run(root, run.stem)
    contract_text = contract.read_text(encoding="utf-8") if contract else "No Technical Contract found."
    execution_plan_text = execution_plan.read_text(encoding="utf-8") if execution_plan else "No Architect Execution Plan found."
    lane_text = lane.read_text(encoding="utf-8") if lane else "No lane provided."
    task_text = task.read_text(encoding="utf-8") if task else "No Engineer Task provided."
    attempt_text = attempt.read_text(encoding="utf-8") if attempt else "No attempt provided."
    review_text = review.read_text(encoding="utf-8") if review else "No source review provided."
    source_architect_review_text = "No source architect review provided."
    if attempt is not None:
        source_architect_review_id = header_value(attempt_text, "Source Architect Review")
        if source_architect_review_id and source_architect_review_id != "none":
            source_architect_review = resolve_state_file(root, "architect-reviews", source_architect_review_id)
            source_architect_review_text = source_architect_review.read_text(encoding="utf-8")
    if role == "architect":
        purpose = "Co-create or revise the Architecture Brief, Technical Contract, or Architect Execution Plan for the current x run."
        payload = f"""Run:
{run_text}

Execution:
{execution}

Architect Control Board:
{architect_control_board(root, run)}

Ledger:
{ledger_text}

Recent x state:
{recent_state_summary(root, run.stem)}

Accepted architect intakes:
{accepted_intakes_summary(root, architect_intakes)}

Relevant repo rules:
- Project context files are listed above.

Notes:
{notes}
"""
        expected = "Return architect questions, options considered, recommended direction, risks, root decisions needed, recommended scope/branch/worktree when known, and whether the brief should be draft, blocked, or accepted. After accepted direction and contract, return an Architect Execution Plan with complete lanes, scopes, verification matrix, review criteria, integration order, risks, loopbacks, and blocked-state recovery. During execution, use the Architect Control Board heartbeat and attention signals as context; if execution should change, return an Architect Directive with action, target, instructions, and acceptance condition."
    elif role == "engineer":
        if task is None or attempt is None:
            raise SystemExit("engineer package requires --task-id and --attempt-id")
        purpose = "Implement exactly one x engineering attempt."
        payload = f"""Technical Contract:
{contract_text}

Architect Execution Plan:
{execution_plan_text}

Lane:
{lane_text}

Execution Boundary:
{execution}

Engineer Task:
{task_text}

Attempt:
{attempt_text}

Source Review:
{review_text}

Source Architect Review:
{source_architect_review_text}

Notes:
{notes}
"""
        expected = "Return changed files, implementation summary, verification commands and observed results, blockers, and residual risk for x_state.py attempt-result."
    elif role == "reviewer":
        if task is None or attempt is None:
            raise SystemExit("reviewer package requires --task-id and --attempt-id")
        attempt_text = attempt.read_text(encoding="utf-8")
        if not attempt_has_result(attempt_text):
            raise SystemExit(f"attempt has no result evidence: {attempt.stem}")
        purpose = "Review one attempt against the Technical Contract, Engineer Task, diff, verification, and repo constraints."
        payload = f"""Technical Contract:
{contract_text}

Architect Execution Plan:
{execution_plan_text}

Lane:
{lane_text}

Execution Boundary:
{execution}

Engineer Task:
{task_text}

Attempt Result:
{attempt_text}

Diff Stat:
{diff_stat}

Diff:
{diff}

Verification:
{verification}

Notes:
{notes}
"""
        expected = "Return recommendation ready, changes-requested, or blocked; blocking findings; non-blocking findings; verification assessment; residual risk; and next action."
    else:
        raise SystemExit(f"unsupported package role: {role}")
    return purpose, payload, expected


def execution_summary(run: Path, lane: Path | None = None) -> str:
    text = run.read_text(encoding="utf-8")
    lines = [
        f"Control Root: {header_value(text, 'Control Root') or 'unknown'}",
        f"Integration Status: {header_value(text, 'Execution Status') or UNMATERIALIZED}",
        f"Integration Worktree: {header_value(text, 'Execution Worktree') or UNMATERIALIZED}",
        f"Integration Branch: {header_value(text, 'Execution Branch') or UNMATERIALIZED}",
    ]
    if lane is None:
        lines.append("Rule: architect role must not edit files; engineer/reviewer roles require a lane package.")
        return "\n".join(lines)
    lane_text = lane.read_text(encoding="utf-8")
    lines.extend(
        [
            f"Lane ID: {lane_display_id(lane)}",
            f"Lane Worktree: {header_value(lane_text, 'Worktree') or 'unknown'}",
            f"Lane Branch: {header_value(lane_text, 'Branch') or 'unknown'}",
            "Rule: engineer and reviewer roles must operate only inside the Lane Worktree.",
        ]
    )
    return "\n".join(lines)


def accepted_intake_paths(root: Path) -> list[Path]:
    directory = state_dirs(root)["architect-intakes"]
    if not directory.exists():
        return []
    return [
        path
        for path in sorted(directory.glob("*.md"), key=state_file_sort_key)
        if header_value(path.read_text(encoding="utf-8"), "Status") == "accepted"
    ]


def selected_accepted_intake_paths(root: Path, intake_id: str | None) -> list[Path]:
    intakes = accepted_intake_paths(root)
    if intake_id:
        intake = resolve_state_file(root, "architect-intakes", intake_id)
        if header_value(intake.read_text(encoding="utf-8"), "Status") != "accepted":
            raise SystemExit(f"architect intake {intake_id} is not accepted")
        return [intake]
    if len(intakes) > 1:
        ids = ", ".join(path.stem for path in intakes)
        raise SystemExit(f"multiple accepted architect intakes found; pass --architect-intake-id ({ids})")
    return intakes


def accepted_intakes_summary(root: Path, intakes: list[Path] | None = None) -> str:
    if intakes is None:
        intakes = accepted_intake_paths(root)
    return accepted_intake_summary_lines(intakes)


def accepted_intake_summary_lines(intakes: list[Path]) -> str:
    if not intakes:
        return "- none"
    lines = []
    for intake in intakes[-5:]:
        text = intake.read_text(encoding="utf-8")
        lines.append(
            f"- {intake.stem}: decision={header_value(text, 'Linked Decision')}; "
            f"direction={compact(section_content(text, 'Accepted Direction'))}"
        )
    return "\n".join(lines)


def command_package(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    if args.role == "councilor":
        command_councilor_package(root, args)
        return
    if args.architect_intake_id and args.role != "architect":
        raise SystemExit("--architect-intake-id is only valid for architect packages")
    run = resolve_run(root, args.run_id)
    task = resolve_state_file(root, "tasks", args.task_id) if args.task_id else None
    attempt = resolve_state_file(root, "attempts", args.attempt_id) if args.attempt_id else None
    review = resolve_state_file(root, "reviews", args.review_id) if args.review_id else None
    if attempt is not None:
        attempt_text = attempt.read_text(encoding="utf-8")
        task_id = header_value(attempt_text, "Linked Task")
        if task is None and task_id:
            task = resolve_state_file(root, "tasks", task_id)
        source_review_id = header_value(attempt_text, "Source Review")
        if review is None and source_review_id and source_review_id != "none":
            review = resolve_state_file(root, "reviews", source_review_id)
    lane = lane_for_attempt(root, attempt) if attempt is not None else None
    if task is not None and header_value(task.read_text(encoding="utf-8"), "Linked Run") != run.stem:
        raise SystemExit(f"task {task.stem} is not linked to run {run.stem}")
    if attempt is not None and header_value(attempt.read_text(encoding="utf-8"), "Linked Run") != run.stem:
        raise SystemExit(f"attempt {attempt.stem} is not linked to run {run.stem}")
    if review is not None and header_value(review.read_text(encoding="utf-8"), "Linked Run") != run.stem:
        raise SystemExit(f"review {review.stem} is not linked to run {run.stem}")
    if review is not None and task is not None and header_value(review.read_text(encoding="utf-8"), "Linked Task") not in {"", task.stem}:
        raise SystemExit(f"review {review.stem} is not linked to task {task.stem}")
    contract = latest_for_run(root, "contracts", run.stem)
    if args.role in {"engineer", "reviewer"} and contract is None:
        raise SystemExit(f"{args.role} package requires a Technical Contract")
    package_worktree: Path | None = None
    if args.role in {"engineer", "reviewer"}:
        if lane is None:
            raise SystemExit(f"{args.role} package requires an attempt linked to a lane")
        failures = lane_work_directive_failures(root, run.stem, lane_display_id(lane))
        if failures:
            raise SystemExit(f"{args.role} package blocked: " + "; ".join(failures))
        lane_status = header_value(lane.read_text(encoding="utf-8"), "Status")
        if lane_status in {"architect-paused", "replan-required"}:
            raise SystemExit(f"{args.role} package blocked: lane {lane_display_id(lane)} status is {lane_status}")
        package_worktree = lane_worktree(lane)
    diff_stat = optional_text_arg(args, "diff_stat", "")
    diff = optional_text_arg(args, "diff", "")
    if args.role == "reviewer" and package_worktree is not None:
        untracked = untracked_files(package_worktree)
        if untracked:
            raise SystemExit("reviewer package cannot capture untracked lane files: " + ", ".join(untracked))
        lane_base = lane_integration_base(package_worktree, header_value(lane.read_text(encoding="utf-8"), "Integration Branch") or "HEAD")
        if not has_content(diff_stat):
            diff_stat = git_output(package_worktree, "diff", "--stat", lane_base, default="Not provided.")
        if not has_content(diff):
            diff = git_output(package_worktree, "diff", lane_base, default="Not provided.")
    verification = optional_text_arg(args, "verification", section_content(attempt.read_text(encoding="utf-8"), "Verification") if attempt else "Not provided.")
    notes = optional_text_arg(args, "notes", "None.")
    architect_intakes = selected_accepted_intake_paths(root, args.architect_intake_id) if args.role == "architect" else None
    purpose, payload, expected_return = package_payload(
        root,
        role=args.role,
        run=run,
        task=task,
        attempt=attempt,
        review=review,
        lane=lane,
        diff_stat=diff_stat,
        diff=diff,
        verification=verification,
        notes=notes,
        architect_intakes=architect_intakes,
    )
    package_id = args.package_id or f"{today()}-{args.role}-{slug(args.title or purpose, 'package')}"
    package_path = unique_path(state_dirs(root)["packages"], package_id)
    execution_plan = latest_execution_plan_for_run(root, run.stem)
    lane_text = lane.read_text(encoding="utf-8") if lane else ""
    content = read_template(PACKAGE_TEMPLATE).format(
        package_id=package_path.stem,
        status="ready",
        role=args.role,
        date=dt.date.today().isoformat(),
        run_id=run.stem,
        contract_id=contract.stem if contract else "none",
        plan_id=execution_plan.stem if execution_plan else "none",
        lane_id=lane_display_id(lane) if lane else "none",
        task_id=task.stem if task else "none",
        attempt_id=attempt.stem if attempt else "none",
        review_id=review.stem if review else "none",
        control_root=header_value(run.read_text(encoding="utf-8"), "Control Root") or "unknown",
        execution_status=header_value(run.read_text(encoding="utf-8"), "Execution Status") or UNMATERIALIZED,
        execution_worktree=header_value(run.read_text(encoding="utf-8"), "Execution Worktree") or UNMATERIALIZED,
        execution_branch=header_value(run.read_text(encoding="utf-8"), "Execution Branch") or UNMATERIALIZED,
        lane_worktree=header_value(lane_text, "Worktree") if lane else "none",
        lane_branch=header_value(lane_text, "Branch") if lane else "none",
        purpose=purpose,
        project_context=project_context(root),
        payload=payload,
        expected_return=expected_return,
    )
    write(package_path, content, args.dry_run)
    if attempt is not None and args.role == "engineer":
        attempt_text = replace_line(attempt.read_text(encoding="utf-8"), "Input Package: ", package_path.stem)
        save(attempt, attempt_text, args.dry_run)
    run_text = update_header(run, phase="Package")
    run_text = append_bullet(run_text, "Packages", f"{package_path.stem}: {args.role}")
    run_text = replace_section(run_text, "Next Action", args.next_action or f"Hand package {package_path.stem} to {args.role}.")
    run_text = append_event_text(run_text, f"Package created: {package_path.stem}")
    save(run, run_text, args.dry_run)


def command_councilor_package(root: Path, args: argparse.Namespace) -> None:
    if not args.discussion_id:
        raise SystemExit("councilor package requires --discussion-id or --interaction-id")
    if not args.council_role:
        raise SystemExit("councilor package requires --council-role")
    discussion = resolve_discussion(root, args.discussion_id)
    require_interaction_writable(discussion, "create role package")
    text = discussion.read_text(encoding="utf-8")
    participants = {item.strip() for item in header_value(text, "Participants").split(",")}
    council_role = normalize_role_reference(root, args.council_role)
    if council_role not in participants:
        raise SystemExit(f"council role {council_role} is not a participant in interaction {discussion.stem}")
    notes = optional_text_arg(args, "notes", "None.")
    existing_briefs = role_briefs_for_discussion(root, discussion.stem)
    intake = latest_accepted_intake_for_discussion(root, discussion.stem)
    payload = "\n".join(
        [
            "Conversation Contract:",
            "\n".join(
                [
                    f"- You are `{council_role}` in a `{header_value(text, 'Mode')}` root interaction.",
                    f"- Participants: {header_value(text, 'Participants')}.",
                    "- Reply as this role in the ongoing conversation; do not collapse the exchange into a neutral summary.",
                    "- Name who you are answering and keep other participants visible when their views matter.",
                    "- Provide a visible conversational turn first; formal role-brief fields may follow.",
                    "- Do not close, synthesize, or exit the interaction unless root/main explicitly asks for that step.",
                ]
            ),
            "",
            "Discussion:",
            text,
            "",
            "Discussion Summary:",
            discussion_summary(discussion),
            "",
            "Role Card:",
            role_card_content(root, council_role),
            "",
            "Existing Role Briefs:",
            role_brief_summary(existing_briefs),
            "",
            "Accepted Architect Intake:",
            intake.read_text(encoding="utf-8") if intake else "None.",
            "",
            "Notes:",
            notes,
        ]
    )
    purpose = f"Produce a {council_role} role brief for the linked root interaction."
    expected_return = (
        "Return `Visible Turn` first: a conversational reply from this role addressed to root and/or named participants. "
        "Then follow the role card's `Output Format`, while still including role-brief fields: stance/recommendation, rationale, "
        "objections or rejected options, risks, decisions needed, implications for architect, strongest objection, weakest assumption, "
        "and evidence that would change the recommendation. "
        "Do not create execution tasks, manage lanes, or bypass architect."
    )
    package_id = args.package_id or f"{today()}-councilor-{council_role}-{slug(args.title or discussion.stem, 'package')}"
    package_path = unique_path(state_dirs(root)["packages"], package_id)
    content = read_template(PACKAGE_TEMPLATE).format(
        package_id=package_path.stem,
        status="ready",
        role="councilor",
        date=dt.date.today().isoformat(),
        run_id="none",
        contract_id="none",
        plan_id="none",
        lane_id="none",
        task_id="none",
        attempt_id="none",
        review_id="none",
        control_root=str(root),
        execution_status=UNMATERIALIZED,
        execution_worktree=UNMATERIALIZED,
        execution_branch=UNMATERIALIZED,
        lane_worktree="none",
        lane_branch="none",
        purpose=purpose,
        project_context=project_context(root),
        payload=payload,
        expected_return=expected_return,
    )
    write(package_path, content, args.dry_run)
    discussion_text = replace_line(text, "Updated At: ", now())
    discussion_text = append_bullet(discussion_text, "Packages", f"{package_path.stem}: councilor/{council_role}")
    discussion_text = append_event_text(discussion_text, f"councilor package created: {package_path.stem}")
    save(discussion, discussion_text, args.dry_run)


def role_brief_summary(briefs: list[Path]) -> str:
    if not briefs:
        return "- none"
    lines = []
    for brief in briefs[-10:]:
        text = brief.read_text(encoding="utf-8")
        lines.append(
            f"- {brief.stem}: role={header_value(text, 'Role')}; "
            f"status={header_value(text, 'Status')}; recommendation={compact(section_content(text, 'Recommendation'))}"
        )
    return "\n".join(lines)
