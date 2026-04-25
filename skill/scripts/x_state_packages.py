from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from x_state_common import *


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
    for kind in ("briefs", "contracts", "tasks", "iterations", "reviews", "decisions", "risks"):
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


def package_payload(
    root: Path,
    *,
    role: str,
    run: Path,
    task: Path | None,
    iteration: Path | None,
    review: Path | None,
    diff_stat: str,
    diff: str,
    verification: str,
    notes: str,
) -> tuple[str, str, str]:
    run_text = run.read_text(encoding="utf-8")
    ledger = ledger_path(root)
    ledger_text = ledger.read_text(encoding="utf-8") if ledger.exists() else "No x ledger found."
    contract = latest_for_run(root, "contracts", run.stem)
    contract_text = contract.read_text(encoding="utf-8") if contract else "No Technical Contract found."
    task_text = task.read_text(encoding="utf-8") if task else "No Engineer Task provided."
    iteration_text = iteration.read_text(encoding="utf-8") if iteration else "No iteration provided."
    review_text = review.read_text(encoding="utf-8") if review else "No source review provided."
    if role == "cto":
        purpose = "Co-create or revise the CTO Intake Brief for the current x run."
        payload = f"""Run:
{run_text}

Ledger:
{ledger_text}

Recent x state:
{recent_state_summary(root, run.stem)}

Relevant repo rules:
- Project context files are listed above.

Notes:
{notes}
"""
        expected = "Return CTO questions, options considered, recommended direction, risks, root decisions needed, and whether the brief should be draft, blocked, or accepted. Do not produce a final Technical Contract until root direction is accepted."
    elif role == "engineer":
        if task is None or iteration is None:
            raise SystemExit("engineer package requires --task-id and --iteration-id")
        purpose = "Implement exactly one x engineering iteration."
        payload = f"""Technical Contract:
{contract_text}

Engineer Task:
{task_text}

Iteration:
{iteration_text}

Source Review:
{review_text}

Notes:
{notes}
"""
        expected = "Return changed files, implementation summary, verification commands and observed results, blockers, and residual risk for x_state.py iteration-result."
    elif role == "reviewer":
        if task is None or iteration is None:
            raise SystemExit("reviewer package requires --task-id and --iteration-id")
        iteration_text = iteration.read_text(encoding="utf-8")
        if not iteration_has_result(iteration_text):
            raise SystemExit(f"iteration has no result evidence: {iteration.stem}")
        purpose = "Review one iteration against the Technical Contract, Engineer Task, diff, verification, and repo constraints."
        payload = f"""Technical Contract:
{contract_text}

Engineer Task:
{task_text}

Iteration Result:
{iteration_text}

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


def command_package(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    task = resolve_state_file(root, "tasks", args.task_id) if args.task_id else None
    iteration = resolve_state_file(root, "iterations", args.iteration_id) if args.iteration_id else None
    review = resolve_state_file(root, "reviews", args.review_id) if args.review_id else None
    if task is not None and header_value(task.read_text(encoding="utf-8"), "Linked Run") != run.stem:
        raise SystemExit(f"task {task.stem} is not linked to run {run.stem}")
    if iteration is not None and header_value(iteration.read_text(encoding="utf-8"), "Linked Run") != run.stem:
        raise SystemExit(f"iteration {iteration.stem} is not linked to run {run.stem}")
    if review is not None and header_value(review.read_text(encoding="utf-8"), "Linked Run") != run.stem:
        raise SystemExit(f"review {review.stem} is not linked to run {run.stem}")
    contract = latest_for_run(root, "contracts", run.stem)
    if args.role in {"engineer", "reviewer"} and contract is None:
        raise SystemExit(f"{args.role} package requires a Technical Contract")
    diff_stat = optional_text_arg(args, "diff_stat")
    diff = optional_text_arg(args, "diff")
    verification = optional_text_arg(args, "verification", section_content(iteration.read_text(encoding="utf-8"), "Verification") if iteration else "Not provided.")
    notes = optional_text_arg(args, "notes", "None.")
    purpose, payload, expected_return = package_payload(
        root,
        role=args.role,
        run=run,
        task=task,
        iteration=iteration,
        review=review,
        diff_stat=diff_stat,
        diff=diff,
        verification=verification,
        notes=notes,
    )
    package_id = args.package_id or f"{today()}-{args.role}-{slug(args.title or purpose, 'package')}"
    package_path = unique_path(state_dirs(root)["packages"], package_id)
    content = read_template(PACKAGE_TEMPLATE).format(
        package_id=package_path.stem,
        status="ready",
        role=args.role,
        date=dt.date.today().isoformat(),
        run_id=run.stem,
        contract_id=contract.stem if contract else "none",
        task_id=task.stem if task else "none",
        iteration_id=iteration.stem if iteration else "none",
        review_id=review.stem if review else "none",
        purpose=purpose,
        project_context=project_context(root),
        payload=payload,
        expected_return=expected_return,
    )
    write(package_path, content, args.dry_run)
    run_text = update_header(run, phase="Subagent Package")
    run_text = append_bullet(run_text, "Subagent Packages", f"{package_path.stem}: {args.role}")
    run_text = replace_section(run_text, "Next Action", args.next_action or f"Spawn {args.role} with package {package_path.stem}.")
    run_text = append_event_text(run_text, f"Subagent package created: {package_path.stem}")
    save(run, run_text, args.dry_run)
