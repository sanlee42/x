from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from x_state_common import *


def command_brief(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    run_id = run_id_from_path(run)
    run_text = run.read_text(encoding="utf-8")
    package_id = args.package_id or "none"
    if args.package_id:
        package = resolve_state_file(root, "packages", args.package_id)
        package_text = package.read_text(encoding="utf-8")
        if header_value(package_text, "Linked Run") != run_id:
            raise SystemExit(f"package {args.package_id} is not linked to run {run_id}")
        if header_value(package_text, "Role") != "cto":
            raise SystemExit(f"package {args.package_id} is not a cto package")

    brief_id = args.brief_id or f"{today()}-{slug(args.title, 'cto-brief')}"
    brief_path = unique_path(state_dirs(root)["briefs"], brief_id)
    accepted_direction = args.accepted_direction or (
        args.recommendation if args.status == "accepted" else "Pending."
    )
    next_action = args.next_action or default_next_action(args.status, brief_path.stem)
    content = read_template(BRIEF_TEMPLATE).format(
        brief_id=brief_path.stem,
        status=args.status,
        date=dt.date.today().isoformat(),
        run_id=run_id,
        package_id=package_id,
        directive=section_content(run_text, "Root Directive"),
        cto_questions=args.cto_questions,
        options=args.options,
        recommendation=args.recommendation,
        risks=args.risks,
        root_decisions_needed=args.root_decisions_needed,
        accepted_direction=accepted_direction,
        next_action=next_action,
    )
    write(brief_path, content, args.dry_run)

    phase = phase_for_status(args.status)
    needs_user = args.needs_user or ("no" if args.status == "accepted" else "yes")
    brief_summary = "\n".join(
        [
            f"{brief_path.stem}: {args.status}",
            "",
            "Recommendation:",
            args.recommendation.strip(),
            "",
            "Root Decisions Needed:",
            args.root_decisions_needed.strip(),
            "",
            "Accepted Direction:",
            accepted_direction.strip(),
        ]
    )
    run_text = update_header(run, phase=phase, needs_user=needs_user)
    run_text = replace_section(run_text, "CTO Intake Brief", brief_summary)
    run_text = replace_section(run_text, "Next Action", next_action)
    run_text = append_event_text(run_text, f"CTO Intake Brief recorded: {brief_path.stem} ({args.status})")
    save(run, run_text, args.dry_run)

    ledger = ensure_ledger(root, dry_run=args.dry_run)
    if not args.dry_run:
        ledger_text = ledger.read_text(encoding="utf-8")
        ledger_text = replace_line(ledger_text, "Updated At: ", now())
        ledger_text = replace_section(ledger_text, "Next Operating Actions", next_action)
        if args.status in {"draft", "blocked"}:
            ledger_text = replace_section(ledger_text, "Open Questions for Root", args.root_decisions_needed)
        elif args.status == "accepted":
            ledger_text = replace_section(ledger_text, "Open Questions for Root", "-")
        save(ledger, ledger_text, args.dry_run)


def phase_for_status(status: str) -> str:
    if status == "accepted":
        return "CTO Accepted"
    if status == "blocked":
        return "CTO Blocked"
    return "CTO Co-Creation"


def default_next_action(status: str, brief_id: str) -> str:
    if status == "accepted":
        return f"Create Technical Contract from accepted CTO Intake Brief {brief_id}."
    if status == "blocked":
        return f"Resolve root/CTO blocker before creating Technical Contract from {brief_id}."
    if status == "superseded":
        return "Create or select the active CTO Intake Brief."
    return f"Continue root/CTO co-creation for {brief_id}."
