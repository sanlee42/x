from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

from x_state_common import *


MESSAGE_KINDS = (
    "request",
    "response",
    "artifact-ready",
    "interface-change",
    "blocker",
    "directive",
    "ack",
)
MESSAGE_STATUSES = ("open", "addressed", "superseded")


def command_mailbox_send(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run_id = linked_run_id(root, args.run_id, args)
    validate_message_links(root, run_id, args)
    message_id = args.message_id or f"{today()}-{slug(args.kind + '-' + args.summary, 'message')}"
    message_path = unique_path(state_dirs(root)["messages"], message_id)
    created_at = now()
    content = read_template(MESSAGE_TEMPLATE).format(
        message_id=message_path.stem,
        status=args.status,
        kind=args.kind,
        date=dt.date.today().isoformat(),
        created_at=created_at,
        updated_at=created_at,
        run_id=run_id,
        lane_id=args.lane_id or "none",
        task_id=args.task_id or "none",
        attempt_id=args.attempt_id or "none",
        review_id=args.review_id or "none",
        from_actor=args.from_actor,
        to_actor=args.to_actor,
        session=args.session or "none",
        summary=args.summary,
        body=optional_text_arg(args, "body", "None."),
        related_artifacts=optional_text_arg(args, "related_artifacts", "None."),
    )
    write(message_path, content, args.dry_run)
    if run_id != "none":
        run = resolve_run(root, run_id)
        run_text = append_event_text(run.read_text(encoding="utf-8"), f"Mailbox message created: {message_path.stem}")
        save(run, run_text, args.dry_run)


def command_mailbox_list(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run_id = resolve_run(root, args.run_id).stem if args.run_id else None
    messages = mailbox_messages(root, run_id=run_id, status=args.status, kind=args.kind, lane_id=args.lane_id)
    print("# x Mailbox")
    print(f"Run: {run_id or 'all'}")
    print(f"Status: {args.status}")
    if args.kind:
        print(f"Kind: {args.kind}")
    if args.lane_id:
        print(f"Lane: {args.lane_id}")
    print()
    if not messages:
        print("- none")
        return
    for message in messages:
        print(f"- {mailbox_message_summary(message)}")


def command_mailbox_resolve(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    message = resolve_state_file(root, "messages", args.message_id)
    text = message.read_text(encoding="utf-8")
    linked_run = header_value(text, "Linked Run")
    if args.run_id:
        run_id = resolve_run(root, args.run_id).stem
        if linked_run != run_id:
            raise SystemExit(f"message {message.stem} is not linked to run {run_id}")
    run = resolve_run(root, linked_run) if linked_run and linked_run != "none" else None
    status = args.status
    resolution = optional_text_arg(args, "resolution", f"Marked {status}.")
    text = replace_line(text, "Status: ", status)
    text = replace_line(text, "Updated At: ", now())
    text = replace_section(text, "Resolution", resolution)
    text = append_event_text(text, f"Mailbox message marked {status}")
    save(message, text, args.dry_run)
    if run is not None:
        run_text = append_event_text(run.read_text(encoding="utf-8"), f"Mailbox message {status}: {message.stem}")
        save(run, run_text, args.dry_run)


def linked_run_id(root: Path, run_id: str | None, args: argparse.Namespace) -> str:
    if run_id:
        return resolve_run(root, run_id).stem
    linked = linked_run_ids(root, args)
    if len(linked) > 1:
        raise SystemExit("linked mailbox artifacts belong to different runs; pass consistent --run-id, --task-id, --attempt-id, and --review-id")
    return next(iter(linked), "none")


def linked_run_ids(root: Path, args: argparse.Namespace) -> set[str]:
    run_ids = set()
    for kind, item_id in (
        ("tasks", args.task_id),
        ("attempts", args.attempt_id),
        ("reviews", args.review_id),
    ):
        if not item_id:
            continue
        path = resolve_state_file(root, kind, item_id)
        linked = header_value(path.read_text(encoding="utf-8"), "Linked Run")
        if linked:
            run_ids.add(linked)
    return run_ids


def validate_message_links(root: Path, run_id: str, args: argparse.Namespace) -> None:
    task_text = ""
    attempt_text = ""
    review_text = ""
    if args.lane_id:
        if run_id == "none":
            raise SystemExit("--lane-id requires --run-id")
        lane = state_dirs(root)["lanes"] / f"{run_id}--{args.lane_id}.md"
        if not lane.exists():
            raise SystemExit(f"lane not found for run {run_id}: {args.lane_id}")
        lane_text = lane.read_text(encoding="utf-8")
        if args.task_id and header_value(lane_text, "Linked Task") != args.task_id:
            raise SystemExit(f"lane {args.lane_id} is not linked to task {args.task_id}")
    for kind, item_id in (
        ("tasks", args.task_id),
        ("attempts", args.attempt_id),
        ("reviews", args.review_id),
    ):
        if not item_id:
            continue
        path = resolve_state_file(root, kind, item_id)
        linked = header_value(path.read_text(encoding="utf-8"), "Linked Run")
        if run_id != "none" and linked and linked != run_id:
            raise SystemExit(f"{kind[:-1]} {item_id} is not linked to run {run_id}")
        if kind == "tasks":
            task_text = path.read_text(encoding="utf-8")
        elif kind == "attempts":
            attempt_text = path.read_text(encoding="utf-8")
        elif kind == "reviews":
            review_text = path.read_text(encoding="utf-8")
    if task_text and attempt_text and header_value(attempt_text, "Linked Task") != args.task_id:
        raise SystemExit(f"attempt {args.attempt_id} is not linked to task {args.task_id}")
    if attempt_text and review_text and header_value(review_text, "Linked Attempt") != args.attempt_id:
        raise SystemExit(f"review {args.review_id} is not linked to attempt {args.attempt_id}")
    if args.lane_id and attempt_text and header_value(attempt_text, "Linked Lane") != args.lane_id:
        raise SystemExit(f"attempt {args.attempt_id} is not linked to lane {args.lane_id}")


def mailbox_messages(
    root: Path,
    *,
    run_id: str | None = None,
    status: str = "open",
    kind: str | None = None,
    lane_id: str | None = None,
) -> list[Path]:
    directory = state_dirs(root)["messages"]
    if not directory.exists():
        return []
    messages = []
    for path in directory.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if run_id is not None and header_value(text, "Linked Run") != run_id:
            continue
        if status != "all" and header_value(text, "Status") != status:
            continue
        if kind and header_value(text, "Kind") != kind:
            continue
        if lane_id and header_value(text, "Linked Lane") != lane_id:
            continue
        messages.append(path)
    return sorted(messages, key=state_file_sort_key)


def open_mailbox_summary(root: Path, run_id: str) -> str:
    messages = mailbox_messages(root, run_id=run_id, status="open")
    if not messages:
        return "- none"
    return "\n".join(f"- {mailbox_message_summary(message)}" for message in messages)


def mailbox_message_summary(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    fields = [
        f"{path.stem}: {header_value(text, 'Kind')}/{header_value(text, 'Status')}",
        f"from={compact(header_value(text, 'From'))}",
        f"to={compact(header_value(text, 'To'))}",
        f"lane={compact(header_value(text, 'Linked Lane'))}",
        f"task={compact(header_value(text, 'Linked Task'))}",
        f"attempt={compact(header_value(text, 'Linked Attempt'))}",
        f"review={compact(header_value(text, 'Linked Review'))}",
        f"session={compact(header_value(text, 'Session'))}",
        f"summary={compact(section_content(text, 'Summary'))}",
    ]
    return "; ".join(fields)


def compact(value: str, *, limit: int = 160) -> str:
    compacted = " ".join(value.strip().split())
    if not has_content(compacted) or compacted.lower() == "none":
        return "none"
    if len(compacted) > limit:
        return compacted[: limit - 3].rstrip() + "..."
    return compacted
