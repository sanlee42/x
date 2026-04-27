from __future__ import annotations

import argparse
import datetime as dt
import subprocess
from pathlib import Path

from x_state_common import *
from x_state_directives import lane_work_directive_failures, merge_ready_directive_failures
from x_state_execution import lane_display_id, lane_for_attempt, lane_status_summary, lane_worktree, latest_execution_plan_for_run
from x_state_integration import lane_integration_base, untracked_files
from x_state_mailbox import open_mailbox_summary
from x_state_reviews import command_review, native_review_findings, normalize_native_review_output
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
        "interactions",
        "participant-briefs",
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


def lane_risk_dependency_summary(root: Path, run_id: str) -> str:
    plan = latest_execution_plan_for_run(root, run_id)
    lines = []
    if plan:
        plan_text = plan.read_text(encoding="utf-8")
        lines.append(f"- Plan: {plan.stem}")
        lines.append(f"- Shared Contract Surfaces: {compact(section_content(plan_text, 'Shared Contract Surfaces'), limit=900)}")
        lines.append(f"- Dependency Graph: {compact(section_content(plan_text, 'Task Dependency Graph'), limit=900)}")
        lines.append(f"- Integration Order: {compact(section_content(plan_text, 'Integration Order'), limit=900)}")
    lanes = files_for_run(root, "lanes", run_id)
    if not lanes:
        lines.append("- Lanes: none")
        return "\n".join(lines)
    lines.append("- Lanes:")
    for lane in lanes:
        text = lane.read_text(encoding="utf-8")
        lines.append(
            "  - "
            + "; ".join(
                [
                    lane_display_id(lane),
                    f"status={header_value(text, 'Status') or 'unknown'}",
                    f"risk={header_value(text, 'Risk Level') or 'unknown'}",
                    f"sample={header_value(text, 'Review Sample') or 'pending'}",
                    f"shared={header_value(text, 'Shared Files') or 'none'}",
                    f"attempt={header_value(text, 'Last Attempt') or 'none'}",
                ]
            )
        )
    return "\n".join(lines)


def run_review_summary(root: Path, run_id: str) -> str:
    lines = []
    reviews = files_for_run(root, "reviews", run_id)
    if reviews:
        lines.append("Code Reviews:")
        for review in reviews[-8:]:
            text = review.read_text(encoding="utf-8")
            lines.append(
                f"- {review.stem}: recommendation={header_value(text, 'Recommendation') or 'unknown'}; "
                f"severity={header_value(text, 'Severity') or 'unknown'}; "
                f"bounded={header_value(text, 'Bounded Fix') or 'unknown'}; "
                f"escalation={header_value(text, 'Escalation Reason') or 'unknown'}; "
                f"attempt={header_value(text, 'Linked Attempt') or 'unknown'}"
            )
    else:
        lines.append("Code Reviews:\n- none")
    architect_reviews = files_for_run(root, "architect-reviews", run_id)
    if architect_reviews:
        lines.append("Architect Reviews:")
        for review in architect_reviews[-8:]:
            text = review.read_text(encoding="utf-8")
            lines.append(
                f"- {review.stem}: recommendation={header_value(text, 'Recommendation') or 'unknown'}; "
                f"lane={header_value(text, 'Linked Lane') or 'unknown'}; "
                f"attempt={header_value(text, 'Linked Attempt') or 'unknown'}"
            )
    else:
        lines.append("Architect Reviews:\n- none")
    return "\n".join(lines)


def run_verification_summary(root: Path, run_id: str) -> str:
    plan = latest_execution_plan_for_run(root, run_id)
    lines = []
    if plan:
        plan_text = plan.read_text(encoding="utf-8")
        lines.append(
            f"- Plan Final Verification: {header_value(plan_text, 'Final Verification Status') or 'unknown'}; "
            f"evidence={compact(section_content(plan_text, 'Final Verification Evidence'), limit=700)}"
        )
    attempts = files_for_run(root, "attempts", run_id)
    if attempts:
        lines.append("- Attempts:")
        for attempt in attempts[-8:]:
            text = attempt.read_text(encoding="utf-8")
            lines.append(
                f"  - {attempt.stem}: status={header_value(text, 'Status') or 'unknown'}; "
                f"verification={compact(section_content(text, 'Verification'), limit=700)}"
            )
    else:
        lines.append("- Attempts: none")
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
        risk_summary = lane_risk_dependency_summary(root, run.stem)
        review_summary = run_review_summary(root, run.stem)
        verification_summary = run_verification_summary(root, run.stem)
        payload = f"""Run:
- ID: {run.stem}
- Status: {header_value(run_text, 'Status') or 'unknown'}
- Phase: {header_value(run_text, 'Current Phase') or 'unknown'}

State References:
- Ledger: {ledger}
- Contract: {contract.stem if contract else 'none'}
- Execution Plan: {execution_plan.stem if execution_plan else 'none'}

Architect Control Board:
{architect_control_board(root, run)}

Risk and Dependency Summary:
{risk_summary}

Review Summary:
{review_summary}

Verification Summary:
{verification_summary}

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
        lane_text = lane.read_text(encoding="utf-8") if lane else ""
        payload = f"""Technical Contract:
- ID: {contract.stem if contract else 'none'}
- Required Verification: {compact(section_content(contract_text, 'Required Verification'), limit=700)}
- Loopback Conditions: {compact(section_content(contract_text, 'Loopback Conditions'), limit=700)}

Architect Execution Plan:
- ID: {execution_plan.stem if execution_plan else 'none'}
- Reviewer Criteria: {compact(section_content(execution_plan_text, 'Reviewer Criteria'), limit=700)}
- Verification Matrix: {compact(section_content(execution_plan_text, 'Verification Matrix'), limit=700)}

Lane:
- ID: {lane_display_id(lane) if lane else 'none'}
- Allowed Scope: {compact(section_content(lane_text, 'Allowed Scope'), limit=700)}
- Forbidden Scope: {compact(section_content(lane_text, 'Forbidden Scope'), limit=700)}
- Risk Level: {header_value(lane_text, 'Risk Level') or 'unknown'}
- Review Sample: {header_value(lane_text, 'Review Sample') or 'pending'} ({header_value(lane_text, 'Review Sample Reason') or 'none'})

Engineer Task:
- ID: {task.stem}
- Goal: {compact(section_content(task_text, 'Goal'), limit=700)}
- Required Verification: {compact(section_content(task_text, 'Required Verification'), limit=700)}
- Expected Done Evidence: {compact(section_content(task_text, 'Expected Done Evidence'), limit=700)}

Attempt Result:
- ID: {attempt.stem}
- Changed Files: {compact(section_content(attempt_text, 'Changed Files'), limit=700)}
- Implementation Summary: {compact(section_content(attempt_text, 'Implementation Summary'), limit=900)}
- Verification: {compact(section_content(attempt_text, 'Verification'), limit=900)}
- Blockers: {compact(section_content(attempt_text, 'Blockers'), limit=500)}
- Residual Risk: {compact(section_content(attempt_text, 'Residual Risk'), limit=700)}

Diff Stat:
{diff_stat}

Diff Reference:
- From lane worktree: `git diff {header_value(lane_text, 'Integration Branch') or 'HEAD'}...HEAD` after computing the merge-base.
- This supplemental package intentionally does not inline the full diff. Use the lane worktree and diff stat above for inspection.

Source Review Findings:
{review_text}

Required Verification:
{verification}

Notes:
{notes}
"""
        expected = "Return recommendation ready, changes-requested, or blocked; severity p0/p1/p2/p3/none; bounded fix yes/no; escalation reason; blocking findings; non-blocking findings; verification assessment; residual risk; and next action."
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


def native_reviewer_prompt(
    root: Path,
    *,
    run: Path,
    task: Path,
    attempt: Path,
    review: Path | None,
    lane: Path,
    lane_base: str,
    verification: str,
    notes: str,
) -> str:
    contract = latest_for_run(root, "contracts", run.stem)
    execution_plan = latest_execution_plan_for_run(root, run.stem)
    contract_text = contract.read_text(encoding="utf-8") if contract else ""
    plan_text = execution_plan.read_text(encoding="utf-8") if execution_plan else ""
    lane_text = lane.read_text(encoding="utf-8")
    task_text = task.read_text(encoding="utf-8")
    attempt_text = attempt.read_text(encoding="utf-8")
    review_text = review.read_text(encoding="utf-8") if review else ""
    source_review = (
        f"{review.stem}: {compact(section_content(review_text, 'Summary'), limit=500)}"
        if review
        else "none"
    )
    return f"""# x Native Codex Reviewer Handoff

Review one x lane attempt with native Codex review. Current Codex review CLI diff selectors do not accept custom prompts; inspect the current lane worktree through:

codex review --uncommitted

Project Context Files:
{project_context(root)}

Run:
- ID: {run.stem}
- Execution: {execution_summary(run, lane)}

Technical Contract Summary:
- Contract: {contract.stem if contract else 'none'}
- Goal: {compact(section_content(contract_text, 'Goal'), limit=700)}
- Allowed Boundaries: {compact(section_content(contract_text, 'Allowed Boundaries'), limit=700)}
- Forbidden Boundaries: {compact(section_content(contract_text, 'Forbidden Boundaries'), limit=700)}
- Required Verification: {compact(section_content(contract_text, 'Required Verification'), limit=700)}
- Loopback Conditions: {compact(section_content(contract_text, 'Loopback Conditions'), limit=700)}

Architect Execution Plan:
- Plan: {execution_plan.stem if execution_plan else 'none'}
- Reviewer Criteria: {compact(section_content(plan_text, 'Reviewer Criteria'), limit=700)}
- Verification Matrix: {compact(section_content(plan_text, 'Verification Matrix'), limit=700)}
- Loopback Triggers: {compact(section_content(plan_text, 'Loopback Triggers'), limit=700)}

Lane Scope:
- Lane: {lane_display_id(lane)}
- Worktree: {header_value(lane_text, 'Worktree') or 'unknown'}
- Branch: {header_value(lane_text, 'Branch') or 'unknown'}
- Base: {lane_base}
- Allowed Scope: {compact(section_content(lane_text, 'Allowed Scope'), limit=700)}
- Forbidden Scope: {compact(section_content(lane_text, 'Forbidden Scope'), limit=700)}
- Done Evidence: {compact(section_content(lane_text, 'Done Evidence'), limit=700)}

Engineer Task:
- Task: {task.stem}
- Goal: {compact(section_content(task_text, 'Goal'), limit=700)}
- Requirements: {compact(section_content(task_text, 'Implementation Requirements'), limit=900)}
- Required Verification: {compact(section_content(task_text, 'Required Verification'), limit=700)}

Attempt Result:
- Attempt: {attempt.stem}
- Changed Files: {compact(section_content(attempt_text, 'Changed Files'), limit=700)}
- Summary: {compact(section_content(attempt_text, 'Implementation Summary'), limit=900)}
- Blockers: {compact(section_content(attempt_text, 'Blockers'), limit=700)}
- Residual Risk: {compact(section_content(attempt_text, 'Residual Risk'), limit=700)}

Source Review:
{source_review}

Verification:
{verification}

Notes:
{notes}

Expected x Review Return Format:
recommendation: ready | changes-requested | blocked

blocking findings: file/line evidence, or "- None."
non-blocking findings: finding, or "- None."
verification assessment: what was checked and what remains unverified.
residual risk: remaining risk for main/architect.
next action: run merge-ready gate, start a fix attempt, loop back to architect, or escalate to root.
"""


def run_codex_native_review(lane_tree: Path) -> str:
    command = ["codex", "review", "--uncommitted"]
    try:
        completed = subprocess.run(
            command,
            cwd=lane_tree,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except FileNotFoundError:
        raise SystemExit("codex-native reviewer backend requires `codex` executable on PATH")
    if completed.returncode != 0:
        details = []
        if completed.stdout.strip():
            details.append("stdout:\n" + completed.stdout.strip())
        if completed.stderr.strip():
            details.append("stderr:\n" + completed.stderr.strip())
        suffix = "\n" + "\n\n".join(details) if details else ""
        raise SystemExit(f"codex review failed with exit {completed.returncode}{suffix}")
    return completed.stdout.strip() or "No native review output."


def record_native_review_raw_package(
    root: Path,
    args: argparse.Namespace,
    *,
    run: Path,
    task: Path,
    attempt: Path,
    review: Path | None,
    lane: Path,
    lane_tree: Path,
    lane_base: str,
    verification: str,
    notes: str,
    output: str,
) -> Path:
    contract = latest_for_run(root, "contracts", run.stem)
    execution_plan = latest_execution_plan_for_run(root, run.stem)
    lane_text = lane.read_text(encoding="utf-8")
    attempt_text = attempt.read_text(encoding="utf-8")
    task_text = task.read_text(encoding="utf-8")
    package_id = args.package_id or f"{today()}-reviewer-native-{attempt.stem}"
    package_path = unique_path(state_dirs(root)["packages"], package_id)
    payload = f"""Native Reviewer Source:
- Command: `codex review --uncommitted`
- Cwd: `{lane_tree}`
- Stdin Prompt: none
- Custom Prompt: none
- Base Reference: `{lane_base}`

State References:
- Contract: {contract.stem if contract else 'none'}
- Plan: {execution_plan.stem if execution_plan else 'none'}
- Lane: {lane_display_id(lane)}
- Task: {task.stem}
- Attempt: {attempt.stem}
- Source Review: {review.stem if review else 'none'}

Lane Scope:
- Allowed Scope: {compact(section_content(lane_text, 'Allowed Scope'), limit=500)}
- Forbidden Scope: {compact(section_content(lane_text, 'Forbidden Scope'), limit=500)}
- Risk Level: {header_value(lane_text, 'Risk Level') or 'unknown'}
- Review Sample: {header_value(lane_text, 'Review Sample') or 'pending'}

Attempt Evidence:
- Changed Files: {compact(section_content(attempt_text, 'Changed Files'), limit=700)}
- Required Verification: {compact(section_content(task_text, 'Required Verification'), limit=700)}
- Attempt Verification: {compact(verification, limit=900)}

Native Raw Output:

{output.strip() or 'No native review output.'}

Notes:
{notes}
"""
    content = read_template(PACKAGE_TEMPLATE).format(
        package_id=package_path.stem,
        status="ready",
        role="reviewer",
        date=dt.date.today().isoformat(),
        run_id=run.stem,
        contract_id=contract.stem if contract else "none",
        plan_id=execution_plan.stem if execution_plan else "none",
        lane_id=lane_display_id(lane),
        task_id=task.stem,
        attempt_id=attempt.stem,
        review_id=review.stem if review else "none",
        control_root=header_value(run.read_text(encoding="utf-8"), "Control Root") or "unknown",
        execution_status=header_value(run.read_text(encoding="utf-8"), "Execution Status") or UNMATERIALIZED,
        execution_worktree=header_value(run.read_text(encoding="utf-8"), "Execution Worktree") or UNMATERIALIZED,
        execution_branch=header_value(run.read_text(encoding="utf-8"), "Execution Branch") or UNMATERIALIZED,
        lane_worktree=header_value(lane_text, "Worktree") or "none",
        lane_branch=header_value(lane_text, "Branch") or "none",
        purpose="Record native Codex reviewer output for normalization into an x Review.",
        project_context=project_context(root),
        payload=payload,
        expected_return="No role response is expected from this package; native output is captured above and normalized into an x Review record.",
    )
    write(package_path, content, args.dry_run)
    run_text = update_header(run, phase="Package")
    run_text = append_bullet(run_text, "Packages", f"{package_path.stem}: reviewer/native")
    run_text = append_event_text(run_text, f"Native reviewer output package created: {package_path.stem}")
    save(run, run_text, args.dry_run)
    return package_path


def record_codex_native_review(
    root: Path,
    args: argparse.Namespace,
    *,
    run: Path,
    task: Path,
    attempt: Path,
    review: Path | None,
    lane: Path,
    lane_tree: Path,
    lane_base: str,
    verification: str,
    notes: str,
) -> None:
    attempt_text = attempt.read_text(encoding="utf-8")
    if not attempt_has_result(attempt_text):
        raise SystemExit(f"attempt has no result evidence: {attempt.stem}")
    prompt = native_reviewer_prompt(
        root,
        run=run,
        task=task,
        attempt=attempt,
        review=review,
        lane=lane,
        lane_base=lane_base,
        verification=verification,
        notes=notes,
    )
    if args.dry_run:
        print("Native Codex review command:")
        print(f"codex review --uncommitted  # cwd: {lane_tree}")
        print()
        print("x context retained in state, but not passed as a custom prompt to native Codex review:")
        print(prompt)
        return
    output = run_codex_native_review(lane_tree)
    package_path = record_native_review_raw_package(
        root,
        args,
        run=run,
        task=task,
        attempt=attempt,
        review=review,
        lane=lane,
        lane_tree=lane_tree,
        lane_base=lane_base,
        verification=verification,
        notes=notes,
        output=output,
    )
    normalized = normalize_native_review_output(output)
    recommendation = str(normalized["recommendation"])
    severity = str(normalized["severity"])
    bounded_fix = str(normalized["bounded_fix"])
    escalation_reason = str(normalized["escalation_reason"])
    blocking_findings, non_blocking_findings = native_review_findings(output, recommendation, escalation_reason)
    normalized_next_action = (
        "Start the bounded fix attempt generated by x."
        if recommendation == "changes-requested" and severity in {"p3", "none"} and bounded_fix == "yes" and escalation_reason == "none"
        else "Proceed according to the normalized x Review gate."
    )
    review_args = argparse.Namespace(
        title=args.title or "Native Codex review",
        summary=str(normalized["summary"]),
        recommendation=recommendation,
        severity=severity,
        bounded_fix=bounded_fix,
        escalation_reason=escalation_reason,
        reviewed_diff=(
            f"Native Codex reviewed staged, unstaged, and untracked lane worktree changes via "
            f"`codex review --uncommitted` from `{lane_tree}`. x context was retained in state but not "
            "passed as a custom prompt because current Codex review diff selectors reject custom prompts. "
            f"Native raw output was stored first in package `{package_path.stem}`."
        ),
        verification=(
            "Attempt verification recorded in x state:\n\n"
            f"{verification}\n\n"
            "Native review command completed successfully."
        ),
        blocking_findings=blocking_findings,
        non_blocking_findings=non_blocking_findings,
        residual_risk=(
            f"Normalized native review fields: severity={severity}; bounded_fix={bounded_fix}; "
            f"escalation_reason={escalation_reason}."
        ),
        status="open",
        run_id=run.stem,
        attempt_id=attempt.stem,
        review_id=f"{today()}-codex-native-{attempt.stem}",
        loopback_target=None,
        needs_user=None,
        next_action=args.next_action or normalized_next_action,
        dry_run=args.dry_run,
    )
    command_review(review_args)


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
    if args.role == "reviewer" and args.reviewer_backend is None:
        args.reviewer_backend = "codex-native"
    if args.reviewer_backend is not None and args.role != "reviewer":
        raise SystemExit("--reviewer-backend is only valid with --role reviewer")
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
    diff_stat = ""
    diff = ""
    verification = optional_text_arg(args, "verification", section_content(attempt.read_text(encoding="utf-8"), "Verification") if attempt else "Not provided.")
    notes = optional_text_arg(args, "notes", "None.")
    if args.role == "reviewer" and package_worktree is not None:
        lane_base = lane_integration_base(package_worktree, header_value(lane.read_text(encoding="utf-8"), "Integration Branch") or "HEAD")
        if args.reviewer_backend == "codex-native":
            if task is None or attempt is None or lane is None:
                raise SystemExit("codex-native reviewer backend requires --task-id and --attempt-id")
            record_codex_native_review(
                root,
                args,
                run=run,
                task=task,
                attempt=attempt,
                review=review,
                lane=lane,
                lane_tree=package_worktree,
                lane_base=lane_base,
                verification=verification,
                notes=notes,
            )
            return
        untracked = untracked_files(package_worktree)
        if untracked:
            raise SystemExit("reviewer package cannot capture untracked lane files: " + ", ".join(untracked))
        diff_stat = optional_text_arg(args, "diff_stat", "")
        diff = optional_text_arg(args, "diff", "")
        if not has_content(diff_stat):
            diff_stat = git_output(package_worktree, "diff", "--stat", lane_base, default="Not provided.")
        if not has_content(diff):
            diff = git_output(package_worktree, "diff", lane_base, default="Not provided.")
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
    interaction_id = getattr(args, "interaction_id", None) or getattr(args, "discussion_id", None)
    if not interaction_id:
        raise SystemExit("councilor package requires --interaction-id")
    if not args.council_role:
        raise SystemExit("councilor package requires --participant")
    discussion = resolve_discussion(root, interaction_id)
    require_interaction_writable(discussion, "create participant package")
    text = discussion.read_text(encoding="utf-8")
    participants = {item.strip() for item in header_value(text, "Participants").split(",")}
    council_role = normalize_role_reference(root, args.council_role)
    if council_role not in participants:
        raise SystemExit(f"participant {council_role} is not in interaction {discussion.stem}")
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
                    "- Reply as this participant view in the ongoing conversation; do not collapse the exchange into a neutral summary.",
                    "- Name who you are answering and keep other participants visible when their views matter.",
                    "- Separate facts, assumptions, judgments, risks, and evidence gaps.",
                    "- Challenge or answer at least one named claim from another participant when the transcript contains one relevant to your view.",
                    "- Prefer a decision-useful deep turn over a short summary paragraph.",
                    "- Provide a visible conversational turn first; formal participant-brief fields may follow.",
                    "- Do not close, synthesize, or exit the interaction unless root/main explicitly asks for that step.",
                ]
            ),
            "",
            "Interaction:",
            text,
            "",
            "Interaction Summary:",
            discussion_summary(discussion),
            "",
            "Participant Card:",
            role_card_content(root, council_role),
            "",
            "Existing Participant Briefs:",
            role_brief_summary(existing_briefs),
            "",
            "Accepted Architect Intake:",
            intake.read_text(encoding="utf-8") if intake else "None.",
            "",
            "Notes:",
            notes,
        ]
    )
    purpose = f"Produce a {council_role} participant brief for the linked root interaction."
    expected_return = (
        "Return `Visible Turn` first: a conversational reply from this participant addressed to root and/or named participants. "
        "The visible turn must be substantive: include stance, reasons, facts used, assumptions, risks, a named challenge or response when relevant, "
        "and the evidence that would change the participant's mind. "
        "Then follow the participant card's `Output Format`, while still including participant-brief fields: stance/recommendation, rationale, "
        "objections or rejected options, risks, decisions needed, implications for architect, strongest objection, weakest assumption, "
        "evidence that would change the recommendation, and document-use notes for the later Room Essence. "
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
            f"- {brief.stem}: participant={header_value(text, 'Participant')}; "
            f"status={header_value(text, 'Status')}; recommendation={compact(section_content(text, 'Recommendation'))}"
        )
    return "\n".join(lines)
