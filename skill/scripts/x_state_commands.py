from __future__ import annotations

import argparse
from pathlib import Path

from x_state_common import *
from x_state_directives import mark_root_decision_directives_addressed
from x_state_discussion import require_interaction_writable
from x_state_execution import (
    active_lane_for_task,
    lane_heartbeats_summary,
    lane_display_id,
    lane_for_attempt,
    mark_lane_attempt_result,
    mark_lane_attempt_started,
    require_architect_gate_passed,
)
from x_state_integration import execution_plan_merge_ready_failures
from x_state_mailbox import open_mailbox_summary


def print_project_binding(root: Path) -> None:
    git_context = current_git_context(root)
    print("# x Project")
    print(f"Repo Root: {root}")
    print(f"Current Branch: {git_context['branch']}")
    print(f"Git Common Dir: {git_context['git_common_dir']}")
    print(f"Project Key: {project_key(root)}")
    print(f"Runtime Dir: {project_state_dir(root)}")
    profile = project_profile_path(root)
    profile_status = "present" if profile.exists() else "missing"
    print(f"Project Profile: {profile_status} ({profile.relative_to(root)})")
    print()


def command_start(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    goal = (args.goal or "To be defined with architect.").strip()
    run_slug = args.short_goal or slug(args.goal or "architect-room", "architect-room")
    run_id = args.run_id or f"{today()}-{run_slug}"
    run_path = unique_path(state_dirs(root)["runs"], run_id)
    final_run_id = run_path.stem
    timestamp = now()
    directive = (args.directive or args.goal or "Open architect room with root; discover direction before execution.").strip()
    next_action = "Do repo/context intake, then create an architect package for root/architect co-creation."
    git_context = current_git_context(root)
    ledger = ensure_ledger(root, objective=goal, next_action=next_action, dry_run=args.dry_run)
    if not args.dry_run:
        ledger_text = ledger.read_text(encoding="utf-8")
        ledger_text = replace_line(ledger_text, "Status: ", "active")
        ledger_text = replace_line(ledger_text, "Updated At: ", now())
        ledger_text = replace_section(ledger_text, "Current Engineering Objective", goal)
        ledger_text = replace_section(ledger_text, "Next Operating Actions", next_action)
        ledger_text = append_bullet(ledger_text, "Active Runs", final_run_id)
        save(ledger, ledger_text, args.dry_run)
    content = read_template(RUN_TEMPLATE).format(
        run_id=final_run_id,
        status="active",
        run_mode="architect-room",
        phase="Repo Intake",
        needs_user="no",
        created_at=timestamp,
        updated_at=timestamp,
        control_root=git_context["root"],
        control_branch=git_context["branch"],
        git_common_dir=git_context["git_common_dir"],
        base_commit=git_context["base_commit"],
        execution_status=UNMATERIALIZED,
        execution_worktree=UNMATERIALIZED,
        execution_branch=UNMATERIALIZED,
        execution_base=f"{git_context['branch']}@{git_context['base_commit']}",
        directive=directive,
        goal=goal,
        success=(args.success or "Accepted architecture direction, materialized execution worktree, reviewed implementation evidence, and merge-back recommendation.").strip(),
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
    runs = active_runs(root)
    if runs:
        print()
        print("## Active Run Bindings")
        for item in sorted(runs, key=lambda p: p.name):
            print(f"- {run_binding_summary(item)}")
    if args.run_id or state_dirs(root)["runs"].exists():
        run = status_run(root, args.run_id)
        if run is None:
            return
        run_text = run.read_text(encoding="utf-8")
        print()
        for line in run_text.splitlines():
            if line.startswith(("# x Run:", "# x Engineering Run:", "Status:", "Run Mode:", "Current Phase:", "Needs User:", "Updated At:", "Gate Status:", "Architect Gate Status:", "Control Root:", "Control Branch:", "Execution Status:", "Execution Worktree:", "Execution Branch:")):
                print(line)
        print()
        print("## Lane Heartbeats")
        print(lane_heartbeats_summary(root, run))
        print()
        print("## Open Mailbox")
        print(open_mailbox_summary(root, run.stem))
        for heading in ("Architecture Brief", "Repo Intake", "Codebase Findings", "Technical Contract", "Engineer Tasks", "Architect Execution Plan", "Architect Gate", "Architect Directives", "Lanes", "Active Attempt", "Packages", "Task Results", "Review Findings", "Architect Reviews", "Integrated Lanes", "Unresolved Reviews", "Merge Gate", "Merge-Back Recommendation", "Blockers", "Next Action"):
            marker = run_text.find(f"## {heading}")
            if marker >= 0:
                print()
                print(run_text[marker:].split("\n## ", 1)[0].strip())


def run_binding_summary(run: Path) -> str:
    text = run.read_text(encoding="utf-8")
    status = header_value(text, "Status") or "active"
    phase = header_value(text, "Current Phase") or "unknown"
    goal = section_content(text, "Engineering Goal").splitlines()[0] if section_content(text, "Engineering Goal") else "No goal."
    execution_status = header_value(text, "Execution Status") or UNMATERIALIZED
    execution_worktree = header_value(text, "Execution Worktree") or UNMATERIALIZED
    execution_branch = header_value(text, "Execution Branch") or UNMATERIALIZED
    return f"{run.stem}: {status}/{phase}; execution={execution_status}; branch={execution_branch}; worktree={execution_worktree}; goal={goal}"


def status_run(root: Path, run_id: str | None) -> Path | None:
    if run_id:
        return resolve_run(root, run_id)
    runs = active_runs(root)
    if not runs:
        try:
            return latest_run(root)
        except SystemExit:
            return None
    current = root.resolve()
    execution_matches = [run for run in runs if run_execution_worktree(run) == current]
    if len(execution_matches) == 1:
        return execution_matches[0]
    if len(runs) == 1:
        return runs[0]
    print()
    print("Multiple active runs are available; pass --run-id to show one run in detail.")
    return None


def command_doctor(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    git_context = current_git_context(root)
    print("# x Doctor")
    print(f"Repo Root: {root}")
    print(f"Current Branch: {git_context['branch']}")
    print(f"Git Common Dir: {git_context['git_common_dir']}")
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
    print("## Active Runs")
    runs = active_runs(root)
    if runs:
        for run in sorted(runs, key=lambda p: p.name):
            print(f"- {run_binding_summary(run)}")
    else:
        print("- none")
    print()
    print("## Global Install")
    report_link("skill x", codex_home() / "skills/x", SKILL_DIR)
    report_link("agent architect", codex_home() / "agents/architect.toml", SKILL_DIR.parents[0] / "agents/architect.toml")
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
        if line.startswith(("# x Run:", "# x Engineering Run:", "Status:", "Run Mode:", "Current Phase:", "Needs User:", "Updated At:", "Gate Status:", "Architect Gate Status:", "Control Root:", "Control Branch:", "Execution Status:", "Execution Worktree:", "Execution Branch:")):
            print(line)
    for heading in ("Root Directive", "Engineering Goal", "Architecture Brief", "Repo Intake", "Codebase Findings", "Technical Contract", "Engineer Tasks", "Architect Execution Plan", "Architect Gate", "Architect Directives", "Lanes", "Active Attempt", "Packages", "Task Results", "Review Findings", "Architect Reviews", "Integrated Lanes", "Unresolved Reviews", "Fix Loop", "Merge Gate", "Merge-Back Recommendation", "Blockers", "Next Action", "Last Checkpoint"):
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


def command_materialize(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    run_id = run_id_from_path(run)
    accepted_brief_with_direction(root, run_id)
    scope = slug(args.scope, "worktree")
    run_text = run.read_text(encoding="utf-8")
    control_root = header_path(run_text, "Control Root") or root.resolve()
    branch = args.branch or f"feat/{scope}"
    worktree = Path(args.worktree).expanduser() if args.worktree else control_root / ".dev" / scope
    if not worktree.is_absolute():
        worktree = control_root / worktree
    worktree = worktree.resolve()
    base = args.base or header_value(run_text, "Control Branch") or "HEAD"

    if run_is_materialized(run) and not args.reuse_worktree:
        raise SystemExit(f"run {run_id} is already materialized; use --reuse-worktree to refresh binding")
    if args.reuse_worktree:
        if not worktree.exists():
            raise SystemExit(f"--reuse-worktree requires an existing worktree: {worktree}")
        assert_same_project_git_dir(control_root, worktree)
    else:
        if worktree.exists():
            raise SystemExit(f"execution worktree already exists: {worktree}; use --reuse-worktree or choose another --scope")
        if git_branch_exists(control_root, branch):
            raise SystemExit(f"execution branch already exists: {branch}; use --reuse-worktree or choose another --branch")
        if not args.dry_run:
            subprocess.check_call(["git", "-C", str(control_root), "worktree", "add", str(worktree), "-b", branch, base])
    git_context = current_git_context(worktree) if worktree.exists() else {
        "root": str(worktree),
        "branch": branch,
        "base_commit": git_output(control_root, "rev-parse", base, default=header_value(run_text, "Base Commit") or "unknown"),
        "git_common_dir": str(git_path(control_root, "rev-parse", "--git-common-dir")),
    }
    control_context = current_git_context(control_root)
    new_text = update_header(run, phase="Materialized", needs_user=args.needs_user)
    new_text = upsert_line_after(new_text, "Run Mode: ", header_value(new_text, "Run Mode") or "architect-room", "Status: ")
    new_text = upsert_line_after(new_text, "Control Root: ", str(control_root), "Gate Status: ")
    new_text = upsert_line_after(new_text, "Control Branch: ", control_context["branch"], "Control Root: ")
    new_text = upsert_line_after(new_text, "Git Common Dir: ", control_context["git_common_dir"], "Control Branch: ")
    new_text = upsert_line_after(new_text, "Base Commit: ", control_context["base_commit"], "Git Common Dir: ")
    new_text = upsert_line_after(new_text, "Execution Status: ", MATERIALIZED, "Base Commit: ")
    new_text = upsert_line_after(new_text, "Execution Worktree: ", str(worktree), "Execution Status: ")
    new_text = upsert_line_after(new_text, "Execution Branch: ", git_context["branch"], "Execution Worktree: ")
    new_text = upsert_line_after(new_text, "Execution Base: ", f"{base}@{git_context['base_commit']}", "Execution Branch: ")
    new_text = replace_section(new_text, "Next Action", args.next_action or "Create Technical Contract, then Engineer Task, attempt, and packages.")
    new_text = append_event_text(new_text, f"Execution worktree materialized: {worktree} ({git_context['branch']})")
    save(run, new_text, args.dry_run)


def git_branch_exists(root: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        check=False,
    )
    return result.returncode == 0


def assert_same_project_git_dir(control_root: Path, worktree: Path) -> None:
    if not worktree.exists():
        raise SystemExit(f"worktree does not exist: {worktree}")
    expected = git_path(control_root, "rev-parse", "--git-common-dir")
    actual = git_path(worktree, "rev-parse", "--git-common-dir")
    if expected != actual:
        raise SystemExit(f"worktree belongs to a different git common dir: {worktree} ({actual} != {expected})")


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
    direction = section_content(brief.read_text(encoding="utf-8"), "Accepted Direction")
    if not has_content(direction):
        raise SystemExit(f"accepted Architecture Brief has no accepted direction: {brief.stem}")
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
    run_text = replace_section(run_text, "Next Action", args.next_action or f"Start implementation attempt for {task_path.stem}.")
    run_text = append_event_text(run_text, f"Engineer Task created: {task_path.stem}")
    save(run, run_text, args.dry_run)
    ledger = ensure_ledger(root, dry_run=args.dry_run)
    if not args.dry_run:
        ledger_text = ledger.read_text(encoding="utf-8")
        ledger_text = append_bullet(ledger_text, "Active Engineering Work", f"{task_path.stem}: {args.title}")
        save(ledger, ledger_text, args.dry_run)


def command_attempt_start(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    task = resolve_state_file(root, "tasks", args.task_id)
    task_text = task.read_text(encoding="utf-8")
    run_id = header_value(task_text, "Linked Run")
    if not run_id:
        raise SystemExit(f"task missing Linked Run: {task.stem}")
    if args.kind == "fix" and not (args.source_review_id or args.source_architect_review_id):
        raise SystemExit("fix attempt requires --source-review-id or --source-architect-review-id")
    if args.kind != "fix" and (args.source_review_id or args.source_architect_review_id):
        raise SystemExit("--source-review-id and --source-architect-review-id are only valid for fix attempts")
    if args.source_review_id and args.source_architect_review_id:
        raise SystemExit("fix attempt can have only one source review")
    source_review_id = args.source_review_id or "none"
    source_architect_review_id = args.source_architect_review_id or "none"
    if args.source_review_id:
        source_review = resolve_state_file(root, "reviews", args.source_review_id)
        source_text = source_review.read_text(encoding="utf-8")
        if header_value(source_text, "Linked Task") != task.stem:
            raise SystemExit(f"source review {args.source_review_id} is not linked to task {task.stem}")
        if header_value(source_text, "Recommendation") == "ready":
            raise SystemExit(f"source review {args.source_review_id} is already ready")
        if header_value(source_text, "Status") in {"addressed", "accepted", "superseded"}:
            raise SystemExit(f"source review {args.source_review_id} is already {header_value(source_text, 'Status')}")
    if args.source_architect_review_id:
        source_review = resolve_state_file(root, "architect-reviews", args.source_architect_review_id)
        source_text = source_review.read_text(encoding="utf-8")
        if header_value(source_text, "Linked Task") != task.stem:
            raise SystemExit(f"source architect review {args.source_architect_review_id} is not linked to task {task.stem}")
        if header_value(source_text, "Recommendation") == "merge-ok":
            raise SystemExit(f"source architect review {args.source_architect_review_id} is already merge-ok")
        if header_value(source_text, "Status") in {"addressed", "accepted", "superseded"}:
            raise SystemExit(f"source architect review {args.source_architect_review_id} is already {header_value(source_text, 'Status')}")
    run = resolve_run(root, run_id)
    require_materialized_run(run, "attempt-start")
    require_architect_gate_passed(root, run)
    lane = active_lane_for_task(root, run_id, task.stem, args.lane_id)
    attempt_number = len(files_for_task(root, "attempts", task.stem)) + 1
    attempt_id = args.attempt_id or f"{task.stem}-a{attempt_number}"
    attempt_path = unique_path(state_dirs(root)["attempts"], attempt_id)
    started_at = now()
    content = read_template(ATTEMPT_TEMPLATE).format(
        attempt_id=attempt_path.stem,
        status="active",
        kind=args.kind,
        started_at=started_at,
        date=dt.date.today().isoformat(),
        run_id=run_id,
        task_id=task.stem,
        lane_id=lane_display_id(lane),
        source_review_id=source_review_id,
        source_architect_review_id=source_architect_review_id,
        title=args.title,
        goal=args.goal or section_content(task_text, "Goal"),
    )
    write(attempt_path, content, args.dry_run)
    task_text = append_bullet(task_text, "Attempts", f"{attempt_path.stem}: {args.kind}")
    save(task, task_text, args.dry_run)
    phase = "Fix Loop" if args.kind == "fix" else "Engineering"
    default_next = f"Generate engineer package for {attempt_path.stem}, then hand it to engineer."
    run_text = update_header(run, phase=phase, needs_user=args.needs_user)
    run_text = replace_section(run_text, "Active Attempt", attempt_path.stem)
    if args.kind == "fix":
        source = source_review_id if source_review_id != "none" else source_architect_review_id
        run_text = append_bullet(run_text, "Fix Loop", f"{attempt_path.stem}: fix for {source}")
    run_text = replace_section(run_text, "Next Action", args.next_action or default_next)
    run_text = append_event_text(run_text, f"Attempt started: {attempt_path.stem}")
    save(run, run_text, args.dry_run)
    mark_lane_attempt_started(lane, attempt_path.stem, args.dry_run)


def update_source_review_addressed(root: Path, attempt_text: str, dry_run: bool) -> None:
    source_review_id = header_value(attempt_text, "Source Review")
    if not source_review_id or source_review_id == "none":
        return
    source_review = resolve_state_file(root, "reviews", source_review_id)
    source_text = source_review.read_text(encoding="utf-8")
    source_text = replace_line(source_text, "Status: ", "addressed")
    save(source_review, source_text, dry_run)


def record_attempt_result(
    root: Path,
    attempt: Path,
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
    attempt_text = attempt.read_text(encoding="utf-8")
    task_id = header_value(attempt_text, "Linked Task")
    run_id = header_value(attempt_text, "Linked Run")
    if not task_id or not run_id:
        raise SystemExit(f"attempt missing Linked Task or Linked Run: {attempt.stem}")
    task = resolve_state_file(root, "tasks", task_id)
    lane = lane_for_attempt(root, attempt)
    if lane is not None and header_value(lane.read_text(encoding="utf-8"), "Last Attempt") != attempt.stem:
        raise SystemExit(f"attempt-result must target latest lane attempt: {header_value(lane.read_text(encoding='utf-8'), 'Last Attempt')}")
    run = resolve_run(root, run_id)
    require_materialized_run(run, "attempt-result")
    attempt_text = replace_line(attempt_text, "Status: ", status)
    attempt_text = replace_line(attempt_text, "Completed At: ", now())
    attempt_text = replace_line(attempt_text, "Output Evidence: ", f"{attempt.stem} result")
    attempt_text = replace_section(attempt_text, "Changed Files", changed_files)
    attempt_text = replace_section(attempt_text, "Implementation Summary", summary)
    attempt_text = replace_section(attempt_text, "Verification", verification)
    attempt_text = replace_section(attempt_text, "Blockers", blockers or "None.")
    attempt_text = replace_section(attempt_text, "Residual Risk", residual_risk)
    attempt_text = replace_section(
        attempt_text,
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
    save(attempt, attempt_text, dry_run)
    task_text = task.read_text(encoding="utf-8")
    task_text = replace_section(task_text, "Result", f"Latest attempt result: {attempt.stem} ({status})")
    save(task, task_text, dry_run)
    phase = "Fix Loop" if status == "blocked" or blocking_present(blockers) else "Review"
    default_next = "Address attempt blockers before review." if phase == "Fix Loop" else f"Generate reviewer package for {attempt.stem}, then hand it to reviewer."
    run_text = update_header(run, phase=phase, needs_user=needs_user)
    run_text = append_bullet(run_text, "Task Results", f"{attempt.stem}: {status} - {summary}")
    run_text = replace_section(run_text, "Validation and Acceptance", verification)
    if phase == "Fix Loop":
        run_text = append_bullet(run_text, "Fix Loop", f"{attempt.stem}: {blockers or 'blocked'}")
    run_text = replace_section(run_text, "Next Action", next_action or default_next)
    run_text = append_event_text(run_text, f"Attempt result recorded: {attempt.stem}")
    save(run, run_text, dry_run)
    mark_lane_attempt_result(root, attempt, dry_run)


def command_attempt_result(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    attempt = resolve_state_file(root, "attempts", args.attempt_id)
    record_attempt_result(
        root,
        attempt,
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


def merge_ready_failures(root: Path, run: Path) -> list[str]:
    run_id = run_id_from_path(run)
    failures: list[str] = []
    try:
        require_materialized_run(run, "merge-ready gate")
    except SystemExit as error:
        failures.append(str(error))
    if latest_accepted_brief_for_run(root, run_id) is None:
        failures.append("missing accepted Architecture Brief")
    failures.extend(execution_plan_merge_ready_failures(root, run))
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
        attempts = files_for_task(root, "attempts", task_id)
        if not attempts:
            failures.append(f"{task_id}: missing attempt evidence")
            continue
        latest_attempt = attempts[-1]
        attempt_text = latest_attempt.read_text(encoding="utf-8")
        if not packages_for_attempt(root, latest_attempt.stem, "engineer"):
            failures.append(f"{task_id}: missing engineer package for latest attempt")
        if not packages_for_attempt(root, latest_attempt.stem, "reviewer"):
            failures.append(f"{task_id}: missing reviewer package for latest attempt")
        if not attempt_has_result(attempt_text):
            failures.append(f"{task_id}: latest attempt missing result evidence")
        if attempt_has_blockers(attempt_text):
            failures.append(f"{task_id}: latest attempt still has blockers")
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
        linked_attempt = header_value(review_text, "Linked Attempt")
        if linked_attempt != latest_attempt.stem:
            failures.append(f"{task_id}: latest review does not cover latest attempt")
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
    require_materialized_run(run, "gate")
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
    discussion = None
    if args.discussion_id:
        discussion = resolve_state_file(root, "discussions", args.discussion_id)
        require_interaction_writable(discussion, "record root decisions")
    if args.architect_intake_id:
        resolve_state_file(root, "architect-intakes", args.architect_intake_id)
    decision_id = args.decision_id or f"{today()}-{slug(args.title, 'decision')}"
    decision_path = unique_path(state_dirs(root)["decisions"], decision_id)
    content = read_template(DECISION_TEMPLATE).format(
        decision_id=decision_path.stem,
        status=args.status,
        date=dt.date.today().isoformat(),
        run_id=args.run_id or "none",
        discussion_id=args.discussion_id or "none",
        architect_intake_id=args.architect_intake_id or "none",
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
    if discussion is not None:
        discussion_text = replace_line(discussion.read_text(encoding="utf-8"), "Updated At: ", now())
        discussion_text = append_bullet(discussion_text, "Root Decisions", f"{decision_path.stem}: {args.decision}")
        discussion_text = append_event_text(discussion_text, f"root decision recorded: {decision_path.stem}")
        save(discussion, discussion_text, args.dry_run)
    if args.run_id:
        run = resolve_run(root, args.run_id)
        run_text = append_bullet(run.read_text(encoding="utf-8"), "Root Decisions", f"{decision_path.stem}: {args.decision}")
        save(run, run_text, args.dry_run)
        mark_root_decision_directives_addressed(root, run.stem, decision_path.stem, args.dry_run)


def command_close(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    if args.status == "accepted":
        require_materialized_run(run, "close --status accepted")
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
