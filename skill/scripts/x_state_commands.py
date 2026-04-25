from __future__ import annotations

import argparse
from pathlib import Path

from x_state_common import *


def print_project_binding(root: Path) -> None:
    print("# x Project")
    print(f"Repo Root: {root}")
    print(f"Project Key: {project_key(root)}")
    print(f"Runtime Dir: {project_state_dir(root)}")
    profile = project_profile_path(root)
    profile_status = "present" if profile.exists() else "missing"
    print(f"Project Profile: {profile_status} ({profile.relative_to(root)})")
    print()


def command_start(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run_slug = args.short_goal or slug(args.goal, "run")
    run_id = args.run_id or f"{today()}-{run_slug}"
    run_path = unique_path(state_dirs(root)["runs"], run_id)
    final_run_id = run_path.stem
    timestamp = now()
    directive = (args.directive or args.goal).strip()
    next_action = "Do repo/context intake, then create a CTO package for root/CTO co-creation."
    ledger = ensure_ledger(root, objective=args.goal.strip(), next_action=next_action, dry_run=args.dry_run)
    if not args.dry_run:
        ledger_text = ledger.read_text(encoding="utf-8")
        ledger_text = replace_line(ledger_text, "Status: ", "active")
        ledger_text = replace_line(ledger_text, "Updated At: ", now())
        ledger_text = replace_section(ledger_text, "Current Engineering Objective", args.goal.strip())
        ledger_text = replace_section(ledger_text, "Next Operating Actions", next_action)
        ledger_text = append_bullet(ledger_text, "Active Runs", final_run_id)
        save(ledger, ledger_text, args.dry_run)
    content = read_template(RUN_TEMPLATE).format(
        run_id=final_run_id,
        status="active",
        phase="Repo Intake",
        needs_user="no",
        created_at=timestamp,
        updated_at=timestamp,
        directive=directive,
        goal=args.goal.strip(),
        success=(args.success or "Merge-ready branch with review evidence and merge-back recommendation.").strip(),
        constraints=(args.constraints or "None specified.").strip(),
        blockers="None.",
        next_action=next_action,
    )
    write(run_path, content, args.dry_run)


def command_status(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    print_project_binding(root)
    ledger = ledger_path(root)
    if ledger.exists():
        text = ledger.read_text(encoding="utf-8")
        for line in text.splitlines():
            if line.startswith(("Status:", "Updated At:")):
                print(line)
        for heading in ("Current Engineering Objective", "Active Runs", "Active Engineering Work", "Root Decisions", "Risks", "Open Questions for Root", "Next Operating Actions", "Last Checkpoint"):
            marker = text.find(f"## {heading}")
            if marker >= 0:
                print()
                print(text[marker:].split("\n## ", 1)[0].strip())
    if args.run_id or state_dirs(root)["runs"].exists():
        try:
            run = resolve_run(root, args.run_id)
        except SystemExit:
            return
        run_text = run.read_text(encoding="utf-8")
        print()
        for line in run_text.splitlines():
            if line.startswith(("# x Run:", "# x Engineering Run:", "Status:", "Current Phase:", "Needs User:", "Updated At:", "Gate Status:")):
                print(line)
        for heading in ("CTO Intake Brief", "Repo Intake", "Codebase Findings", "Technical Contract", "Engineer Tasks", "Active Iteration", "Subagent Packages", "Task Results", "Review Findings", "Unresolved Reviews", "Merge Gate", "Merge-Back Recommendation", "Blockers", "Next Action"):
            marker = run_text.find(f"## {heading}")
            if marker >= 0:
                print()
                print(run_text[marker:].split("\n## ", 1)[0].strip())


def command_doctor(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    print("# x Doctor")
    print(f"Repo Root: {root}")
    print(f"Project Key: {project_key(root)}")
    print(f"Runtime Dir: {project_state_dir(root)}")
    print(f"X_HOME: {x_home()}")
    print(f"CODEX_HOME: {codex_home()}")
    print()
    print("## Project Context")
    report_path("PROJECT_CONSTRAINTS.md", root / "PROJECT_CONSTRAINTS.md")
    report_path("AGENTS.md", root / "AGENTS.md")
    report_path(".x/project/profile.md", project_profile_path(root))
    print()
    print("## Runtime State")
    report_path("runtime dir", project_state_dir(root))
    report_path("ledger", ledger_path(root))
    print()
    print("## Global Install")
    report_link("skill x", codex_home() / "skills/x", SKILL_DIR)
    report_link("agent cto", codex_home() / "agents/cto.toml", SKILL_DIR.parents[0] / "agents/cto.toml")
    report_link("agent engineer", codex_home() / "agents/engineer.toml", SKILL_DIR.parents[0] / "agents/engineer.toml")
    report_link("agent reviewer", codex_home() / "agents/reviewer.toml", SKILL_DIR.parents[0] / "agents/reviewer.toml")


def report_path(label: str, path: Path) -> None:
    status = "ok" if path.exists() else "missing"
    print(f"- {label}: {status} ({path})")


def report_link(label: str, path: Path, expected: Path) -> None:
    if path.is_symlink():
        target = path.resolve()
        status = "ok" if target == expected.resolve() else "mismatch"
        print(f"- {label}: {status} ({path} -> {target})")
        return
    status = "present" if path.exists() else "missing"
    print(f"- {label}: {status} ({path}; expected -> {expected})")


def command_resume(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    ledger = ledger_path(root)
    if not ledger.exists():
        raise SystemExit("no engineering ledger found")
    run = resolve_run(root, args.run_id)
    ledger_text = ledger.read_text(encoding="utf-8")
    run_text = run.read_text(encoding="utf-8")
    print("# x Resume Context")
    for heading in ("Current Engineering Objective", "Active Runs", "Active Engineering Work", "Root Decisions", "Risks", "Open Questions for Root", "Next Operating Actions", "Last Checkpoint"):
        marker = ledger_text.find(f"## {heading}")
        if marker >= 0:
            print()
            print(ledger_text[marker:].split("\n## ", 1)[0].strip())
    print()
    for line in run_text.splitlines():
        if line.startswith(("# x Run:", "# x Engineering Run:", "Status:", "Current Phase:", "Needs User:", "Updated At:", "Gate Status:")):
            print(line)
    for heading in ("Root Directive", "Engineering Goal", "CTO Intake Brief", "Repo Intake", "Codebase Findings", "Technical Contract", "Engineer Tasks", "Active Iteration", "Subagent Packages", "Task Results", "Review Findings", "Unresolved Reviews", "Fix Loop", "Merge Gate", "Merge-Back Recommendation", "Blockers", "Next Action", "Last Checkpoint"):
        marker = run_text.find(f"## {heading}")
        if marker >= 0:
            print()
            print(run_text[marker:].split("\n## ", 1)[0].strip())


def command_ledger(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    path = ensure_ledger(root, dry_run=args.dry_run)
    if args.show:
        print(path.read_text(encoding="utf-8"))
        return
    if args.name:
        text = path.read_text(encoding="utf-8")
        text = replace_line(text, "Updated At: ", now())
        text = replace_section(text, args.name, content_arg(args))
        save(path, text, args.dry_run)


def command_section(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    path = resolve_run(root, args.run_id)
    text = update_header(path, status=args.status, phase=args.phase, needs_user=args.needs_user)
    text = replace_section(text, args.name, content_arg(args))
    text = append_event_text(text, f"Updated section: {args.name}")
    save(path, text, args.dry_run)


def command_contract(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    run_id = run_id_from_path(run)
    brief = accepted_brief_for_run(root, run_id, args.brief_id)
    contract_id = args.contract_id or f"{today()}-{slug(args.title, 'contract')}"
    contract_path = unique_path(state_dirs(root)["contracts"], contract_id)
    content = read_template(CONTRACT_TEMPLATE).format(
        contract_id=contract_path.stem,
        status=args.status,
        date=dt.date.today().isoformat(),
        run_id=run_id,
        brief_id=brief.stem,
        goal=args.goal,
        repo_intake=args.repo_intake,
        codebase_findings=args.codebase_findings,
        allowed_boundaries=args.allowed_boundaries,
        forbidden_boundaries=args.forbidden_boundaries,
        reversible_path=args.reversible_path,
        verification=args.verification,
        loopback=args.loopback,
        root_escalations=args.root_escalations or "None.",
    )
    write(contract_path, content, args.dry_run)
    run_text = update_header(run, phase="Technical Contract", needs_user=args.needs_user)
    run_text = replace_section(run_text, "Repo Intake", args.repo_intake)
    run_text = replace_section(run_text, "Codebase Findings", args.codebase_findings)
    run_text = replace_section(run_text, "Technical Contract", f"{contract_path.stem}: {args.goal} (brief {brief.stem})")
    run_text = replace_section(run_text, "Next Action", args.next_action or "Create Engineer Task from Technical Contract.")
    run_text = append_event_text(run_text, f"Technical Contract created: {contract_path.stem}")
    save(run, run_text, args.dry_run)


def command_task(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    run_id = run_id_from_path(run)
    contract_path = contract_for_run(root, run_id, args.contract_id)
    contract_id = contract_path.stem
    task_id = args.task_id or f"{today()}-{slug(args.title, 'task')}"
    task_path = unique_path(state_dirs(root)["tasks"], task_id)
    content = read_template(TASK_TEMPLATE).format(
        task_id=task_path.stem,
        status=args.status,
        date=dt.date.today().isoformat(),
        run_id=run_id,
        contract_id=contract_id,
        goal=args.goal,
        allowed_scope=args.allowed_scope,
        forbidden_scope=args.forbidden_scope,
        requirements=args.requirements,
        verification=args.verification,
        done_evidence=args.done_evidence,
    )
    write(task_path, content, args.dry_run)
    run_text = update_header(run, phase="Engineering", needs_user=args.needs_user)
    run_text = append_bullet(run_text, "Engineer Tasks", f"{task_path.stem}: {args.title} ({args.status}, contract {contract_id})")
    run_text = replace_section(run_text, "Next Action", args.next_action or f"Start implementation iteration for {task_path.stem}.")
    run_text = append_event_text(run_text, f"Engineer Task created: {task_path.stem}")
    save(run, run_text, args.dry_run)
    ledger = ensure_ledger(root, dry_run=args.dry_run)
    if not args.dry_run:
        ledger_text = ledger.read_text(encoding="utf-8")
        ledger_text = append_bullet(ledger_text, "Active Engineering Work", f"{task_path.stem}: {args.title}")
        save(ledger, ledger_text, args.dry_run)


def command_iteration_start(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    task = resolve_state_file(root, "tasks", args.task_id)
    task_text = task.read_text(encoding="utf-8")
    run_id = header_value(task_text, "Linked Run")
    if not run_id:
        raise SystemExit(f"task missing Linked Run: {task.stem}")
    if args.kind == "fix" and not args.source_review_id:
        raise SystemExit("fix iteration requires --source-review-id")
    source_review_id = args.source_review_id or "none"
    if args.source_review_id:
        source_review = resolve_state_file(root, "reviews", args.source_review_id)
        source_text = source_review.read_text(encoding="utf-8")
        if header_value(source_text, "Linked Task") != task.stem:
            raise SystemExit(f"source review {args.source_review_id} is not linked to task {task.stem}")
    run = resolve_run(root, run_id)
    iteration_number = len(files_for_task(root, "iterations", task.stem)) + 1
    iteration_id = args.iteration_id or f"{task.stem}-i{iteration_number}"
    iteration_path = unique_path(state_dirs(root)["iterations"], iteration_id)
    content = read_template(ITERATION_TEMPLATE).format(
        iteration_id=iteration_path.stem,
        status="active",
        kind=args.kind,
        agent_policy=args.agent_policy,
        date=dt.date.today().isoformat(),
        run_id=run_id,
        task_id=task.stem,
        source_review_id=source_review_id,
        title=args.title,
        goal=args.goal or section_content(task_text, "Goal"),
    )
    write(iteration_path, content, args.dry_run)
    task_text = append_bullet(task_text, "Iterations", f"{iteration_path.stem}: {args.kind} ({args.agent_policy})")
    save(task, task_text, args.dry_run)
    phase = "Fix Loop" if args.kind == "fix" else "Engineering"
    run_text = update_header(run, phase=phase, needs_user=args.needs_user)
    run_text = replace_section(run_text, "Active Iteration", iteration_path.stem)
    if args.kind == "fix":
        run_text = append_bullet(run_text, "Fix Loop", f"{iteration_path.stem}: fix for {source_review_id} ({args.agent_policy} engineer)")
    run_text = replace_section(run_text, "Next Action", args.next_action or f"Generate engineer package for {iteration_path.stem}, then spawn engineer.")
    run_text = append_event_text(run_text, f"Iteration started: {iteration_path.stem}")
    save(run, run_text, args.dry_run)


def update_source_review_addressed(root: Path, iteration_text: str, dry_run: bool) -> None:
    source_review_id = header_value(iteration_text, "Source Review")
    if not source_review_id or source_review_id == "none":
        return
    source_review = resolve_state_file(root, "reviews", source_review_id)
    source_text = source_review.read_text(encoding="utf-8")
    source_text = replace_line(source_text, "Status: ", "addressed")
    save(source_review, source_text, dry_run)


def record_iteration_result(
    root: Path,
    iteration: Path,
    *,
    status: str,
    changed_files: str,
    summary: str,
    verification: str,
    blockers: str | None,
    residual_risk: str,
    needs_user: str | None,
    next_action: str | None,
    dry_run: bool,
) -> None:
    iteration_text = iteration.read_text(encoding="utf-8")
    task_id = header_value(iteration_text, "Linked Task")
    run_id = header_value(iteration_text, "Linked Run")
    if not task_id or not run_id:
        raise SystemExit(f"iteration missing Linked Task or Linked Run: {iteration.stem}")
    task = resolve_state_file(root, "tasks", task_id)
    run = resolve_run(root, run_id)
    iteration_text = replace_line(iteration_text, "Status: ", status)
    iteration_text = replace_section(iteration_text, "Changed Files", changed_files)
    iteration_text = replace_section(iteration_text, "Implementation Summary", summary)
    iteration_text = replace_section(iteration_text, "Verification", verification)
    iteration_text = replace_section(iteration_text, "Blockers", blockers or "None.")
    iteration_text = replace_section(iteration_text, "Residual Risk", residual_risk)
    iteration_text = replace_section(
        iteration_text,
        "Result",
        "\n".join(
            [
                f"Status: {status}",
                "",
                f"Summary: {summary}",
                "",
                f"Verification: {verification}",
                "",
                f"Blockers: {blockers or 'None.'}",
            ]
        ),
    )
    save(iteration, iteration_text, dry_run)
    task_text = task.read_text(encoding="utf-8")
    task_text = replace_section(task_text, "Result", f"Latest iteration result: {iteration.stem} ({status})")
    save(task, task_text, dry_run)
    phase = "Fix Loop" if status == "blocked" or blocking_present(blockers) else "Review"
    default_next = "Address iteration blockers before review." if phase == "Fix Loop" else f"Generate reviewer package for {iteration.stem}, then spawn reviewer."
    run_text = update_header(run, phase=phase, needs_user=needs_user)
    run_text = append_bullet(run_text, "Task Results", f"{iteration.stem}: {status} - {summary}")
    run_text = replace_section(run_text, "Validation and Acceptance", verification)
    if phase == "Fix Loop":
        run_text = append_bullet(run_text, "Fix Loop", f"{iteration.stem}: {blockers or 'blocked'}")
    run_text = replace_section(run_text, "Next Action", next_action or default_next)
    run_text = append_event_text(run_text, f"Iteration result recorded: {iteration.stem}")
    save(run, run_text, dry_run)


def command_iteration_result(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    iteration = resolve_state_file(root, "iterations", args.iteration_id)
    record_iteration_result(
        root,
        iteration,
        status=args.status,
        changed_files=args.changed_files,
        summary=args.summary,
        verification=args.verification,
        blockers=args.blockers,
        residual_risk=args.residual_risk,
        needs_user=args.needs_user,
        next_action=args.next_action,
        dry_run=args.dry_run,
    )


def command_task_result(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    task = resolve_state_file(root, "tasks", args.task_id)
    task_text = task.read_text(encoding="utf-8")
    run_id = header_value(task_text, "Linked Run")
    if not run_id:
        raise SystemExit(f"task missing Linked Run: {task.stem}")
    if args.iteration_id:
        iteration = iteration_for_task(root, task.stem, args.iteration_id)
    else:
        iteration = latest_for_task(root, "iterations", task.stem)
        if iteration is None:
            shim = argparse.Namespace(
                task_id=task.stem,
                kind="implementation",
                source_review_id=None,
                iteration_id=None,
                title="legacy task-result implementation",
                goal=None,
                agent_policy="fresh",
                needs_user=None,
                next_action=None,
                dry_run=args.dry_run,
            )
            command_iteration_start(shim)
            iteration = latest_for_task(root, "iterations", task.stem)
            if iteration is None:
                raise SystemExit("failed to create compatibility iteration")
    record_iteration_result(
        root,
        iteration,
        status=args.status,
        changed_files=args.changed_files,
        summary=args.summary,
        verification=args.verification,
        blockers=args.blockers,
        residual_risk=args.residual_risk,
        needs_user=args.needs_user,
        next_action=args.next_action,
        dry_run=args.dry_run,
    )
    run = resolve_run(root, run_id)
    result = "\n".join(
        [
            f"Status: {args.status}",
            "",
            "Changed Files:",
            args.changed_files.strip(),
            "",
            "Implementation Summary:",
            args.summary.strip(),
            "",
            "Verification:",
            args.verification.strip(),
            "",
            "Blockers:",
            (args.blockers or "None.").strip(),
            "",
            "Residual Risk:",
            args.residual_risk.strip(),
        ]
    )
    task_text = replace_line(task_text, "Status: ", args.status)
    task_text = replace_section(task_text, "Result", result)
    save(task, task_text, args.dry_run)


def command_review(args: argparse.Namespace) -> None:
    if args.recommendation == "ready" and blocking_present(args.blocking_findings):
        raise SystemExit("ready review cannot include blocking findings")
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    run_id = run_id_from_path(run)
    task = task_for_run(root, run_id, args.task_id)
    task_text = task.read_text(encoding="utf-8")
    iteration: Path | None = None
    if args.iteration_id:
        iteration = iteration_for_task(root, task.stem, args.iteration_id)
    elif task_has_iterations(root, task.stem):
        iteration = iteration_for_task(root, task.stem)
    elif not task_has_result(task_text):
        raise SystemExit(f"task has no Task Result / patch evidence: {task.stem}")
    if iteration is not None and not iteration_has_result(iteration.read_text(encoding="utf-8")):
        raise SystemExit(f"iteration has no result evidence: {iteration.stem}")
    review_id = args.review_id or f"{today()}-{slug(args.title, 'review')}"
    review_path = unique_path(state_dirs(root)["reviews"], review_id)
    source_review_id = header_value(iteration.read_text(encoding="utf-8"), "Source Review") if iteration else "none"
    if args.loopback_target:
        loopback_target = args.loopback_target
    elif args.recommendation == "changes-requested":
        loopback_target = "engineer"
    elif args.recommendation == "blocked":
        loopback_target = "cto"
    else:
        loopback_target = "none"
    content = read_template(REVIEW_TEMPLATE).format(
        review_id=review_path.stem,
        status=args.status,
        recommendation=args.recommendation,
        date=dt.date.today().isoformat(),
        run_id=run_id,
        task_id=task.stem,
        iteration_id=iteration.stem if iteration else "legacy-task-result",
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
    if args.recommendation == "ready":
        next_action = "Run merge-ready gate."
        if iteration is not None:
            iteration_text = replace_line(iteration.read_text(encoding="utf-8"), "Status: ", "reviewed")
            save(iteration, iteration_text, args.dry_run)
            task_text = replace_section(task.read_text(encoding="utf-8"), "Latest Ready Iteration", iteration.stem)
            task_text = replace_line(task_text, "Status: ", "done")
            save(task, task_text, args.dry_run)
            update_source_review_addressed(root, iteration_text, args.dry_run)
    elif loopback_target == "engineer":
        next_action = f"Start fresh fix iteration for {review_path.stem}."
    elif loopback_target == "cto":
        next_action = f"Loop back to CTO before more engineering; review {review_path.stem} is blocked."
    else:
        next_action = f"Escalate review {review_path.stem} to root."
    non_ready_count = non_ready_review_count(root, task.stem)
    needs_user = args.needs_user
    if args.recommendation != "ready" and (non_ready_count >= MAX_NON_READY_REVIEWS or loopback_target == "root"):
        needs_user = "yes"
        next_action = f"Escalate {task.stem}: {non_ready_count} non-ready reviews or root loopback."
    run_text = update_header(run, phase="Review", needs_user=needs_user)
    run_text = append_bullet(run_text, "Review Findings", f"{review_path.stem}: {args.recommendation} - {args.summary}")
    if args.recommendation == "ready" and source_review_id != "none":
        run_text = remove_bullet_containing(run_text, "Unresolved Reviews", source_review_id)
    if args.recommendation != "ready":
        run_text = append_bullet(run_text, "Fix Loop", f"{review_path.stem}: {args.recommendation}")
        run_text = append_bullet(run_text, "Unresolved Reviews", f"{review_path.stem}: {args.recommendation} -> {loopback_target}")
    run_text = replace_section(run_text, "Next Action", args.next_action or next_action)
    run_text = append_event_text(run_text, f"Review recorded: {review_path.stem}")
    save(run, run_text, args.dry_run)


def merge_ready_failures(root: Path, run: Path) -> list[str]:
    run_id = run_id_from_path(run)
    failures: list[str] = []
    if latest_accepted_brief_for_run(root, run_id) is None:
        failures.append("missing accepted CTO Intake Brief")
    contract = latest_for_run(root, "contracts", run_id)
    if contract is None:
        failures.append("missing Technical Contract")
    else:
        contract_text = contract.read_text(encoding="utf-8")
        linked_brief = header_value(contract_text, "Linked Brief")
        if not linked_brief:
            failures.append(f"{contract.stem}: Technical Contract missing Linked Brief")
        else:
            try:
                accepted_brief_for_run(root, run_id, linked_brief)
            except SystemExit as error:
                failures.append(f"{contract.stem}: invalid linked brief: {error}")
    tasks = active_tasks_for_run(root, run_id)
    if not tasks:
        failures.append("missing Engineer Task")
    for task in tasks:
        task_text = task.read_text(encoding="utf-8")
        task_id = task.stem
        if not has_content(section_content(task_text, "Required Verification")):
            failures.append(f"{task_id}: missing required verification in Engineer Task")
        iterations = files_for_task(root, "iterations", task_id)
        if not iterations:
            if task_has_result(task_text):
                failures.append(f"{task_id}: legacy Task Result exists but no iteration evidence")
            else:
                failures.append(f"{task_id}: missing iteration evidence")
            continue
        latest_iteration = iterations[-1]
        iteration_text = latest_iteration.read_text(encoding="utf-8")
        if not packages_for_iteration(root, latest_iteration.stem, "engineer"):
            failures.append(f"{task_id}: missing engineer package for latest iteration")
        if not packages_for_iteration(root, latest_iteration.stem, "reviewer"):
            failures.append(f"{task_id}: missing reviewer package for latest iteration")
        if not iteration_has_result(iteration_text):
            failures.append(f"{task_id}: latest iteration missing result evidence")
        if iteration_has_blockers(iteration_text):
            failures.append(f"{task_id}: latest iteration still has blockers")
        unresolved = unresolved_reviews_for_task(root, task_id)
        for review in unresolved:
            failures.append(f"{task_id}: unresolved review {review.stem}")
        reviews = files_for_task(root, "reviews", task_id)
        if not reviews:
            failures.append(f"{task_id}: missing Review Findings")
            continue
        review = reviews[-1]
        review_text = review.read_text(encoding="utf-8")
        if header_value(review_text, "Recommendation") != "ready":
            failures.append(f"{task_id}: latest review is not ready")
        linked_iteration = header_value(review_text, "Linked Iteration")
        if linked_iteration != latest_iteration.stem:
            failures.append(f"{task_id}: latest review does not cover latest iteration")
        if blocking_present(section_content(review_text, "Blocking Findings")):
            failures.append(f"{task_id}: review has blocking findings")
        if not has_content(section_content(review_text, "Reviewed Verification")):
            failures.append(f"{task_id}: review missing verification assessment")
        if not has_content(section_content(review_text, "Reviewed Diff")):
            failures.append(f"{task_id}: review missing diff evidence")
    return failures


def run_merge_ready_gate(root: Path, run: Path, dry_run: bool) -> None:
    failures = merge_ready_failures(root, run)
    run_text = update_header(run, phase="Merge Gate")
    if failures:
        gate = "failed:\n" + "\n".join(f"- {failure}" for failure in failures)
        run_text = replace_line(run_text, "Gate Status: ", "failed")
        run_text = replace_section(run_text, "Merge Gate", gate)
        run_text = replace_section(run_text, "Next Action", "Address merge-ready gate failures.")
        save(run, run_text, dry_run)
        raise SystemExit("merge-ready gate failed: " + "; ".join(failures))
    gate = f"passed: {now()}"
    run_text = replace_line(run_text, "Gate Status: ", "passed")
    run_text = replace_section(run_text, "Merge Gate", gate)
    run_text = replace_section(run_text, "Next Action", "Prepare merge-back recommendation and local commit if code changed.")
    run_text = append_event_text(run_text, "Merge-ready gate passed")
    save(run, run_text, dry_run)


def command_gate(args: argparse.Namespace) -> None:
    if args.mode != "merge-ready":
        raise SystemExit(f"unsupported gate mode: {args.mode}")
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    run_merge_ready_gate(root, run, args.dry_run)


def command_checkpoint(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    ledger = ensure_ledger(root, dry_run=args.dry_run)
    summary = args.summary.strip()
    next_action = args.next_action or "Continue highest-priority engineering work."
    checkpoint = f"{now()}: {summary}\n\nNext: {next_action}"
    ledger_text = ledger.read_text(encoding="utf-8")
    ledger_text = replace_line(ledger_text, "Updated At: ", now())
    ledger_text = replace_section(ledger_text, "Last Checkpoint", checkpoint)
    ledger_text = replace_section(ledger_text, "Next Operating Actions", next_action)
    save(ledger, ledger_text, args.dry_run)
    if args.run_id or state_dirs(root)["runs"].exists():
        try:
            run = resolve_run(root, args.run_id)
        except SystemExit:
            return
        run_text = update_header(run, phase=args.phase, needs_user=args.needs_user)
        run_text = replace_section(run_text, "Last Checkpoint", checkpoint)
        run_text = replace_section(run_text, "Next Action", next_action)
        run_text = append_event_text(run_text, f"Checkpoint: {summary}")
        save(run, run_text, args.dry_run)


def command_redirect(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    run_text = update_header(run, status="redirected", needs_user="no")
    run_text = append_bullet(run_text, "Blockers", f"Root redirect: {args.note}")
    run_text = replace_section(run_text, "Next Action", "Re-evaluate affected engineering contract or task.")
    run_text = append_event_text(run_text, f"Redirect: {args.note}")
    save(run, run_text, args.dry_run)


def command_risk(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    risk_id = args.risk_id or f"{today()}-{slug(args.title, 'risk')}"
    risk_path = unique_path(state_dirs(root)["risks"], risk_id)
    content = read_template(RISK_TEMPLATE).format(
        risk_id=risk_path.stem,
        status=args.status,
        severity=args.severity,
        date=dt.date.today().isoformat(),
        run_id=args.run_id or "none",
        risk=args.title,
        impact=args.impact or "Not specified.",
        mitigation=args.mitigation or "Not specified.",
        owner=args.owner or "main",
    )
    write(risk_path, content, args.dry_run)
    ledger = ensure_ledger(root, dry_run=args.dry_run)
    ledger_text = ledger.read_text(encoding="utf-8")
    ledger_text = replace_line(ledger_text, "Updated At: ", now())
    ledger_text = append_bullet(ledger_text, "Risks", f"{risk_path.stem}: {args.title} ({args.severity}, {args.status})")
    save(ledger, ledger_text, args.dry_run)
    if args.run_id:
        run = resolve_run(root, args.run_id)
        run_text = append_bullet(run.read_text(encoding="utf-8"), "Risks", f"{risk_path.stem}: {args.title}")
        save(run, run_text, args.dry_run)


def command_decision(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    decision_id = args.decision_id or f"{today()}-{slug(args.title, 'decision')}"
    decision_path = unique_path(state_dirs(root)["decisions"], decision_id)
    content = read_template(DECISION_TEMPLATE).format(
        decision_id=decision_path.stem,
        status=args.status,
        date=dt.date.today().isoformat(),
        run_id=args.run_id or "none",
        context=args.context or "Not specified.",
        decision=args.decision,
        rationale=args.rationale or "Not specified.",
        consequences=args.consequences or "Not specified.",
    )
    write(decision_path, content, args.dry_run)
    ledger = ensure_ledger(root, dry_run=args.dry_run)
    ledger_text = ledger.read_text(encoding="utf-8")
    ledger_text = replace_line(ledger_text, "Updated At: ", now())
    ledger_text = append_bullet(ledger_text, "Root Decisions", f"{decision_path.stem}: {args.decision}")
    save(ledger, ledger_text, args.dry_run)
    if args.run_id:
        run = resolve_run(root, args.run_id)
        run_text = append_bullet(run.read_text(encoding="utf-8"), "Root Decisions", f"{decision_path.stem}: {args.decision}")
        save(run, run_text, args.dry_run)


def command_close(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    if args.status == "accepted":
        run_merge_ready_gate(root, run, args.dry_run)
    run_text = update_header(run, status=args.status, phase="Closed", needs_user="no")
    recommendation = f"{args.status}: {args.summary}"
    run_text = replace_section(run_text, "Merge-Back Recommendation", recommendation)
    run_text = replace_section(run_text, "Close Summary", args.summary)
    run_text = replace_section(run_text, "Next Action", "Await root merge authorization or next engineering directive.")
    run_text = replace_section(run_text, "Last Checkpoint", f"{now()}: Closed run {run.stem}: {args.summary}")
    run_text = append_event_text(run_text, f"Closed: {args.summary}")
    save(run, run_text, args.dry_run)
    ledger = ensure_ledger(root, dry_run=args.dry_run)
    ledger_text = ledger.read_text(encoding="utf-8")
    ledger_text = replace_line(ledger_text, "Status: ", "idle" if args.status == "accepted" else args.status)
    ledger_text = replace_line(ledger_text, "Updated At: ", now())
    ledger_text = remove_bullet_containing(ledger_text, "Active Runs", run.stem)
    for task in active_tasks_for_run(root, run.stem):
        ledger_text = remove_bullet_containing(ledger_text, "Active Engineering Work", task.stem)
    ledger_text = replace_section(
        ledger_text,
        "Next Operating Actions",
        "Await root merge authorization or next engineering directive.",
    )
    ledger_text = replace_section(ledger_text, "Last Checkpoint", f"{now()}: Closed run {run.stem}: {args.summary}")
    save(ledger, ledger_text, args.dry_run)
