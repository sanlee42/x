from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

from x_state_common import *


DISCUSSION_MODES = ("with", "joint", "independent")
DISCUSSION_STATUSES = ("active", "synthesized", "closed", "superseded")
LEGACY_ROLE_ALIASES = {"product-acceptance": "product"}
DISCUSSION_TURN_KINDS = ("statement", "question", "viewpoint", "challenge", "critique", "response", "summary", "decision-candidate")
ROLE_BRIEF_STATUSES = ("draft", "ready", "superseded")
ARCHITECT_INTAKE_STATUSES = ("draft", "accepted", "superseded")
ROLE_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
RESERVED_ROLE_NAMES = {"root", "main", "engineer", "reviewer", "councilor"}


def command_discussion_start(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    participants = normalized_participants(root, args.participants)
    validate_mode_participants(args.mode, participants)
    run_id = resolve_run(root, args.run_id).stem if args.run_id else "none"
    discussion_id = args.discussion_id or f"{today()}-{slug(args.title, 'discussion')}"
    discussion_path = unique_path(state_dirs(root)["discussions"], discussion_id)
    created_at = now()
    content = read_template(DISCUSSION_TEMPLATE).format(
        discussion_id=discussion_path.stem,
        status=args.status,
        mode=args.mode,
        date=dt.date.today().isoformat(),
        created_at=created_at,
        updated_at=created_at,
        run_id=run_id,
        participants=", ".join(participants),
        agenda=args.agenda,
    )
    write(discussion_path, content, args.dry_run)


def command_discussion_turn(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    discussion = resolve_discussion(root, require_discussion_arg(args))
    require_interaction_writable(discussion, "record turns")
    actor = normalized_interaction_actor(args.actor)
    validate_actor_for_discussion(discussion, actor)
    body = optional_text_arg(args, "body", "")
    if not has_content(body):
        raise SystemExit("--body or --body-file is required")
    timestamp = now()
    turn = "\n".join(
        [
            f"### {timestamp} {actor} / {args.turn_kind}",
            "",
            body.strip(),
        ]
    )
    text = discussion.read_text(encoding="utf-8")
    current = section_content(text, "Turns")
    text = replace_section(text, "Turns", turn if current in {"", "-", "Pending."} else current.rstrip() + "\n\n" + turn)
    text = replace_line(text, "Updated At: ", timestamp)
    text = append_event_text(text, f"discussion turn recorded: {actor}/{args.turn_kind}")
    save(discussion, text, args.dry_run)


def command_role_brief(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    discussion = resolve_discussion(root, require_discussion_arg(args))
    require_interaction_writable(discussion, "record role briefs")
    role = normalize_role_reference(root, args.role)
    validate_actor_for_discussion(discussion, role)
    require_challenge_fields(args)
    brief_id = args.brief_id or f"{today()}-{slug(args.role + '-' + args.title, 'role-brief')}"
    brief_path = unique_path(state_dirs(root)["role-briefs"], brief_id)
    created_at = now()
    content = read_template(ROLE_BRIEF_TEMPLATE).format(
        brief_id=brief_path.stem,
        status=args.status,
        role=role,
        date=dt.date.today().isoformat(),
        discussion_id=discussion.stem,
        recommendation=args.recommendation,
        rationale=args.rationale,
        rejected_options=args.rejected_options,
        risks=args.risks,
        decisions_needed=args.decisions_needed,
        implications_for_architect=args.implications_for_architect,
        strongest_objection=args.strongest_objection,
        weakest_assumption=args.weakest_assumption,
        evidence_to_change=args.evidence_to_change,
        created_at=created_at,
    )
    write(brief_path, content, args.dry_run)
    text = replace_line(discussion.read_text(encoding="utf-8"), "Updated At: ", created_at)
    text = append_bullet(text, "Role Briefs", f"{brief_path.stem}: {role} ({args.status})")
    text = append_event_text(text, f"role brief recorded: {brief_path.stem}")
    save(discussion, text, args.dry_run)


def command_discussion_synthesize(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    discussion = resolve_discussion(root, require_discussion_arg(args))
    require_interaction_writable(discussion, "record synthesis")
    require_challenge_fields(args)
    missing = missing_independent_role_briefs(root, discussion)
    if missing:
        raise SystemExit("independent discussion synthesis requires role briefs for: " + ", ".join(missing))
    synthesis = "\n".join(
        [
            "### Agreements",
            "",
            args.agreements.strip(),
            "",
            "### Conflicts",
            "",
            args.conflicts.strip(),
            "",
            "### Rejected Options",
            "",
            args.rejected_options.strip(),
            "",
            "### Root Decisions Needed",
            "",
            args.root_decisions_needed.strip(),
            "",
            "### Recommended Direction",
            "",
            args.recommended_direction.strip(),
            "",
            "### Architect Intake Draft",
            "",
            args.architect_intake_draft.strip(),
            "",
            "### Strongest Objection",
            "",
            args.strongest_objection.strip(),
            "",
            "### Weakest Assumption",
            "",
            args.weakest_assumption.strip(),
            "",
            "### Evidence To Change",
            "",
            args.evidence_to_change.strip(),
        ]
    )
    timestamp = now()
    text = discussion.read_text(encoding="utf-8")
    text = replace_section(text, "Synthesis", synthesis)
    text = replace_section(text, "Current Summary", args.recommended_direction)
    text = replace_line(text, "Status: ", "synthesized")
    text = replace_line(text, "Updated At: ", timestamp)
    text = append_event_text(text, "discussion synthesis recorded")
    save(discussion, text, args.dry_run)


def command_architect_intake(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    discussion = resolve_discussion(root, require_discussion_arg(args))
    require_interaction_writable(discussion, "record architect intake")
    decision_id = args.decision_id or "none"
    intake_id = args.intake_id or f"{today()}-{slug(args.title, 'architect-intake')}"
    intake_path = unique_path(state_dirs(root)["architect-intakes"], intake_id)
    decision = None
    if args.status == "accepted":
        decision = require_accepted_decision(root, decision_id, discussion.stem)
        if not has_content(args.accepted_direction):
            raise SystemExit("--accepted-direction is required for accepted architect intake")
        require_decision_can_link_intake(decision, discussion.stem, intake_path.stem)
    elif args.decision_id:
        resolve_state_file(root, "decisions", args.decision_id)
    created_at = now()
    content = read_template(ARCHITECT_INTAKE_TEMPLATE).format(
        intake_id=intake_path.stem,
        status=args.status,
        date=dt.date.today().isoformat(),
        discussion_id=discussion.stem,
        decision_id=decision_id,
        accepted_direction=args.accepted_direction,
        architecture_input=args.architecture_input,
        scope_boundaries=args.scope_boundaries,
        non_goals=args.non_goals,
        root_decisions=args.root_decisions,
        risks=args.risks,
        handoff_to_architect=args.handoff_to_architect,
        created_at=created_at,
    )
    write(intake_path, content, args.dry_run)
    if decision is not None:
        link_decision_to_intake(decision, discussion.stem, intake_path.stem, args.dry_run)
    text = replace_line(discussion.read_text(encoding="utf-8"), "Updated At: ", created_at)
    text = append_bullet(text, "Architect Intake", f"{intake_path.stem}: {args.status}")
    text = append_event_text(text, f"architect intake recorded: {intake_path.stem}")
    save(discussion, text, args.dry_run)


def command_board(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    content = board_content(root)
    if args.write:
        write(state_dirs(root)["boards"] / "current.md", content, args.dry_run)
        return
    print(content)


def board_content(root: Path) -> str:
    timestamp = now()
    lines = [
        "# x Root Board",
        "",
        f"Updated At: {timestamp}",
        "",
        "## Active Interactions",
        "",
        discussion_board_lines(root),
        "",
        "## Accepted Architect Intakes",
        "",
        intake_board_lines(root),
        "",
        "## Root Decisions",
        "",
        decision_board_lines(root),
        "",
        "## Active Runs",
        "",
        run_board_lines(root),
        "",
        "## Risks",
        "",
        risk_board_lines(root),
    ]
    return "\n".join(lines).rstrip() + "\n"


def discussion_board_lines(root: Path) -> str:
    discussions = [
        path
        for path in sorted(state_dirs(root)["discussions"].glob("*.md"), key=state_file_sort_key)
        if header_value(path.read_text(encoding="utf-8"), "Status") not in {"closed", "superseded"}
    ] if state_dirs(root)["discussions"].exists() else []
    if not discussions:
        return "- none"
    return "\n".join(f"- {discussion_summary(path)}" for path in discussions)


def intake_board_lines(root: Path) -> str:
    intakes = [
        path
        for path in sorted(state_dirs(root)["architect-intakes"].glob("*.md"), key=state_file_sort_key)
        if header_value(path.read_text(encoding="utf-8"), "Status") == "accepted"
    ] if state_dirs(root)["architect-intakes"].exists() else []
    if not intakes:
        return "- none"
    return "\n".join(f"- {intake_summary(path)}" for path in intakes)


def decision_board_lines(root: Path) -> str:
    decisions = sorted(state_dirs(root)["decisions"].glob("*.md"), key=state_file_sort_key) if state_dirs(root)["decisions"].exists() else []
    if not decisions:
        return "- none"
    return "\n".join(f"- {path.stem}: {compact(section_content(path.read_text(encoding='utf-8'), 'Decision'))}" for path in decisions[-10:])


def run_board_lines(root: Path) -> str:
    runs = active_runs(root)
    if not runs:
        return "- none"
    return "\n".join(f"- {run.stem}: {run_status(run)}/{run_phase(run)}" for run in runs)


def risk_board_lines(root: Path) -> str:
    risks = sorted(state_dirs(root)["risks"].glob("*.md"), key=state_file_sort_key) if state_dirs(root)["risks"].exists() else []
    open_risks = [path for path in risks if header_value(path.read_text(encoding="utf-8"), "Status") in {"open", "mitigating"}]
    if not open_risks:
        return "- none"
    return "\n".join(f"- {path.stem}: {header_value(path.read_text(encoding='utf-8'), 'Severity')} {section_content(path.read_text(encoding='utf-8'), 'Risk')}" for path in open_risks[-10:])


def resolve_discussion(root: Path, discussion_id: str) -> Path:
    return resolve_state_file(root, "discussions", discussion_id)


def resolve_architect_intake(root: Path, intake_id: str) -> Path:
    return resolve_state_file(root, "architect-intakes", intake_id)


def command_role_list(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    print("# x Roles")
    print(f"Runtime Roles: {state_dirs(root)['roles']}")
    print()
    print("## Active Role Cards")
    names = all_role_names(root)
    if not names:
        print("- none")
    for role in names:
        print(f"- {role} ({role_source(root, role)})")
    print()
    print("## Legacy Aliases")
    for alias, target in sorted(LEGACY_ROLE_ALIASES.items()):
        print(f"- {alias} -> {target}")


def command_role_show(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    role = normalize_role_reference(root, args.role)
    content = role_card_content(root, role)
    print(content, end="" if content.endswith("\n") else "\n")


def command_role_set(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    role = normalize_role_name(args.role)
    body = optional_text_arg(args, "body", "")
    if has_content(body):
        content = body.strip() + "\n"
    else:
        content = read_template(ROLE_CARD_TEMPLATE).format(
            role=role,
            updated_at=now(),
            responsibilities=(args.responsibilities or "Not specified.").strip(),
            focus=(args.focus or "Not specified.").strip(),
            must_challenge=(args.must_challenge or "Not specified.").strip(),
            out_of_bounds=(args.out_of_bounds or "Do not create execution tasks, manage lanes, assign reviewers, or issue architect directives.").strip(),
            output_format=(args.output_format or "Return stance, reasons, objections, weakest assumption, evidence that would change the stance, and questions needing root decision.").strip(),
        )
    path = state_dirs(root)["roles"] / f"{role}.md"
    write(path, content, args.dry_run)


def discussion_summary(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return (
        f"{path.stem}: mode={header_value(text, 'Mode')}; "
        f"status={header_value(text, 'Status')}; participants={header_value(text, 'Participants')}; "
        f"summary={compact(section_content(text, 'Current Summary'))}"
    )


def intake_summary(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return (
        f"{path.stem}: decision={header_value(text, 'Linked Decision')}; "
        f"direction={compact(section_content(text, 'Accepted Direction'))}"
    )


def role_briefs_for_discussion(root: Path, discussion_id: str, role: str | None = None) -> list[Path]:
    briefs = files_for_header(root, "role-briefs", "Linked Discussion", discussion_id)
    if role is None:
        return briefs
    return [brief for brief in briefs if header_value(brief.read_text(encoding="utf-8"), "Role") == role]


def latest_accepted_intake_for_discussion(root: Path, discussion_id: str) -> Path | None:
    candidates = [
        path
        for path in files_for_header(root, "architect-intakes", "Linked Discussion", discussion_id)
        if header_value(path.read_text(encoding="utf-8"), "Status") == "accepted"
    ]
    return candidates[-1] if candidates else None


def normalized_participants(root: Path, values: list[str]) -> list[str]:
    participants: list[str] = []
    for value in values:
        for item in value.split(","):
            raw_role = item.strip()
            if not raw_role:
                continue
            role = normalize_role_reference(root, raw_role)
            if role not in participants:
                participants.append(role)
    if not participants:
        raise SystemExit("--participants is required")
    return participants


def validate_mode_participants(mode: str, participants: list[str]) -> None:
    if mode == "with" and len(participants) != 1:
        raise SystemExit("with discussion requires exactly one participant")
    if mode in {"joint", "independent"} and len(participants) < 2:
        raise SystemExit(f"{mode} discussion requires at least two participants")


def normalized_interaction_actor(actor: str) -> str:
    if actor in {"root", "main"}:
        return actor
    return LEGACY_ROLE_ALIASES.get(actor.strip().lower(), actor.strip().lower())


def validate_actor_for_discussion(discussion: Path, actor: str) -> None:
    if actor in {"root", "main"}:
        return
    actor = LEGACY_ROLE_ALIASES.get(actor, actor)
    participants = {item.strip() for item in header_value(discussion.read_text(encoding="utf-8"), "Participants").split(",")}
    if actor not in participants:
        raise SystemExit(f"actor {actor} is not a participant in interaction {discussion.stem}")


def require_challenge_fields(args: argparse.Namespace) -> None:
    for name in ("strongest_objection", "weakest_assumption", "evidence_to_change"):
        if not has_content(getattr(args, name, "") or ""):
            raise SystemExit(f"--{name.replace('_', '-')} is required")


def missing_independent_role_briefs(root: Path, discussion: Path) -> list[str]:
    text = discussion.read_text(encoding="utf-8")
    if header_value(text, "Mode") != "independent":
        return []
    missing = []
    for role in [item.strip() for item in header_value(text, "Participants").split(",") if item.strip()]:
        ready = [
            brief
            for brief in role_briefs_for_discussion(root, discussion.stem, role)
            if header_value(brief.read_text(encoding="utf-8"), "Status") == "ready"
        ]
        if not ready:
            missing.append(role)
    return missing


def require_interaction_writable(discussion: Path, operation: str) -> None:
    status = header_value(discussion.read_text(encoding="utf-8"), "Status")
    if status in {"closed", "superseded"}:
        raise SystemExit(f"interaction {discussion.stem} is {status}; cannot {operation}")


def require_discussion_arg(args: argparse.Namespace) -> str:
    discussion_id = getattr(args, "discussion_id", None)
    if not discussion_id:
        raise SystemExit("--discussion-id or --interaction-id is required")
    return discussion_id


def require_accepted_decision(root: Path, decision_id: str, discussion_id: str) -> Path:
    if not decision_id or decision_id == "none":
        raise SystemExit("accepted architect intake requires --decision-id")
    decision = resolve_state_file(root, "decisions", decision_id)
    decision_text = decision.read_text(encoding="utf-8")
    if header_value(decision_text, "Status") != "accepted":
        raise SystemExit(f"decision {decision_id} is not accepted")
    linked_discussion = header_value(decision_text, "Linked Discussion")
    if linked_discussion not in {"", "none", discussion_id}:
        raise SystemExit(f"decision {decision_id} is linked to discussion {linked_discussion}, not {discussion_id}")
    return decision


def require_decision_can_link_intake(decision: Path, discussion_id: str, intake_id: str) -> None:
    text = decision.read_text(encoding="utf-8")
    linked_discussion = header_value(text, "Linked Discussion")
    if linked_discussion not in {"", "none", discussion_id}:
        raise SystemExit(f"decision {decision.stem} is linked to discussion {linked_discussion}, not {discussion_id}")
    linked_intake = header_value(text, "Linked Architect Intake")
    if linked_intake not in {"", "none", intake_id}:
        raise SystemExit(f"decision {decision.stem} is already linked to architect intake {linked_intake}")


def link_decision_to_intake(decision: Path, discussion_id: str, intake_id: str, dry_run: bool) -> None:
    text = decision.read_text(encoding="utf-8")
    text = upsert_line_after(text, "Linked Discussion: ", discussion_id, "Linked Run: ")
    text = upsert_line_after(text, "Linked Architect Intake: ", intake_id, "Linked Discussion: ")
    save(decision, text, dry_run)


def normalize_role_name(role: str) -> str:
    normalized = role.strip().lower()
    if normalized in LEGACY_ROLE_ALIASES:
        normalized = LEGACY_ROLE_ALIASES[normalized]
    if normalized in RESERVED_ROLE_NAMES:
        raise SystemExit(f"reserved role name: {role}")
    if not ROLE_NAME_PATTERN.match(normalized):
        raise SystemExit(f"invalid role name: {role}")
    return normalized


def normalize_role_reference(root: Path, role: str) -> str:
    normalized = normalize_role_name(role)
    if not role_exists(root, normalized):
        raise SystemExit(f"unknown role: {role}")
    return normalized


def role_exists(root: Path, role: str) -> bool:
    return role in all_role_names(root)


def all_role_names(root: Path) -> list[str]:
    names = {path.stem for path in DEFAULT_ROLE_CARDS_DIR.glob("*.md")} if DEFAULT_ROLE_CARDS_DIR.exists() else set()
    runtime_dir = state_dirs(root)["roles"]
    if runtime_dir.exists():
        names.update(path.stem for path in runtime_dir.glob("*.md"))
    names.difference_update(RESERVED_ROLE_NAMES)
    names.difference_update(LEGACY_ROLE_ALIASES)
    return sorted(names)


def role_source(root: Path, role: str) -> str:
    runtime = state_dirs(root)["roles"] / f"{role}.md"
    default = DEFAULT_ROLE_CARDS_DIR / f"{role}.md"
    if runtime.exists() and default.exists():
        return "runtime override"
    if runtime.exists():
        return "runtime"
    return "default"


def role_card_content(root: Path, role: str) -> str:
    role = normalize_role_name(role)
    runtime = state_dirs(root)["roles"] / f"{role}.md"
    if runtime.exists():
        return runtime.read_text(encoding="utf-8")
    default = DEFAULT_ROLE_CARDS_DIR / f"{role}.md"
    if default.exists():
        return default.read_text(encoding="utf-8")
    raise SystemExit(f"unknown role: {role}")


def compact(value: str, *, limit: int = 160) -> str:
    compacted = " ".join(value.strip().split())
    if not has_content(compacted):
        return "none"
    if len(compacted) > limit:
        return compacted[: limit - 3].rstrip() + "..."
    return compacted
