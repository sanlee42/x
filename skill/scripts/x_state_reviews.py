from __future__ import annotations

import argparse
import datetime as dt
import re
from pathlib import Path

from x_state_common import *
from x_state_commands import update_source_review_addressed
from x_state_execution import lane_display_id, lane_for_attempt, mark_lane_attempt_started, mark_lane_code_review


REVIEW_SEVERITIES = ("p0", "p1", "p2", "p3", "none")
REVIEW_SEVERITY_RANK = {"none": 0, "p3": 1, "p2": 2, "p1": 3, "p0": 4}
REVIEW_ESCALATION_REASONS = {
    "none",
    "scope-drift",
    "wrong-abstraction",
    "contract-incomplete",
    "cross-lane-conflict",
    "acceptance-change",
    "unstructured-native-output",
    "other",
}
NATIVE_REVIEW_RECOMMENDATIONS = {"ready", "changes-requested", "blocked"}

def command_review(args: argparse.Namespace) -> None:
    args.severity = normalized_review_severity(getattr(args, "severity", None), args.recommendation)
    args.bounded_fix = normalized_bounded_fix(getattr(args, "bounded_fix", None))
    args.escalation_reason = normalized_escalation_reason(getattr(args, "escalation_reason", None))
    if args.recommendation == "ready" and blocking_present(args.blocking_findings):
        raise SystemExit("ready review cannot include blocking findings")
    if args.recommendation == "ready" and review_severity_rank(args.severity) >= review_severity_rank("p2"):
        raise SystemExit("ready review cannot use severity p0, p1, or p2")
    if args.recommendation == "ready" and args.escalation_reason != "none":
        raise SystemExit("ready review cannot include an escalation reason")
    root = repo_root(Path.cwd())
    attempt = resolve_state_file(root, "attempts", args.attempt_id)
    attempt_text = attempt.read_text(encoding="utf-8")
    run_id = header_value(attempt_text, "Linked Run")
    if not run_id:
        raise SystemExit(f"attempt missing Linked Run: {attempt.stem}")
    run = resolve_run(root, args.run_id or run_id)
    if run.stem != run_id:
        raise SystemExit(f"attempt {attempt.stem} is linked to run {run_id}, not {run.stem}")
    require_materialized_run(run, "review")
    if not attempt_has_result(attempt_text):
        raise SystemExit(f"attempt has no result evidence: {attempt.stem}")
    lane = lane_for_attempt(root, attempt)
    if lane is not None and header_value(lane.read_text(encoding="utf-8"), "Last Attempt") != attempt.stem:
        raise SystemExit(f"review must target latest lane attempt: {header_value(lane.read_text(encoding='utf-8'), 'Last Attempt')}")
    task_id = header_value(attempt_text, "Linked Task")
    if not task_id:
        raise SystemExit(f"attempt missing Linked Task: {attempt.stem}")
    task = resolve_state_file(root, "tasks", task_id)
    source_review_id = header_value(attempt_text, "Source Review") or "none"
    review_id = args.review_id or f"{today()}-{slug(args.title, 'review')}"
    review_path = unique_path(state_dirs(root)["reviews"], review_id)
    next_non_ready_count = non_ready_review_count(root, task.stem) + (0 if args.recommendation == "ready" else 1)
    loopback_target = review_loopback(args, next_non_ready_count)
    content = read_template(REVIEW_TEMPLATE).format(
        review_id=review_path.stem,
        status=args.status,
        recommendation=args.recommendation,
        severity=args.severity,
        bounded_fix=args.bounded_fix,
        escalation_reason=args.escalation_reason,
        date=dt.date.today().isoformat(),
        run_id=run_id,
        task_id=task.stem,
        attempt_id=attempt.stem,
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
    next_action = apply_review_result(root, args, review_path, task, attempt, loopback_target)
    needs_user = review_needs_user(args, next_non_ready_count, loopback_target)
    if args.recommendation != "ready" and needs_user == "yes":
        next_action = f"Loop back to architect/root for {task.stem}: repeated non-ready reviews or root loopback."
    run_text = update_header(run, phase="Review", needs_user=needs_user)
    review_line = f"{review_path.stem}: {attempt.stem} {args.recommendation} - {args.summary}"
    run_text = append_bullet(run_text, "Review Findings", review_line)
    if args.recommendation == "ready" and source_review_id != "none":
        run_text = remove_bullet_containing(run_text, "Unresolved Reviews", source_review_id)
    if args.recommendation != "ready":
        run_text = append_bullet(run_text, "Fix Loop", f"{review_path.stem}: {args.recommendation}")
        run_text = append_bullet(run_text, "Unresolved Reviews", f"{review_path.stem}: {args.recommendation} -> {loopback_target}")
    run_text = replace_section(run_text, "Next Action", args.next_action or next_action)
    run_text = append_event_text(run_text, f"Review recorded: {review_path.stem}")
    save(run, run_text, args.dry_run)
    mark_lane_code_review(root, review_path, args.dry_run)
    maybe_start_bounded_fix_attempt(root, args, review_path, task, attempt, loopback_target)


def normalized_review_severity(value: str | None, recommendation: str) -> str:
    if value:
        normalized = value.strip().lower()
        if normalized in REVIEW_SEVERITIES:
            return normalized
        raise SystemExit(f"review severity must be one of: {', '.join(REVIEW_SEVERITIES)}")
    if recommendation == "blocked":
        return "p2"
    if recommendation == "changes-requested":
        return "p3"
    return "none"


def normalized_bounded_fix(value: str | None) -> str:
    if value is None:
        return "no"
    normalized = value.strip().lower()
    if normalized in {"yes", "no"}:
        return normalized
    raise SystemExit("bounded fix must be yes or no")


def normalized_escalation_reason(value: str | None) -> str:
    if value is None:
        return "none"
    normalized = value.strip().lower()
    if normalized in REVIEW_ESCALATION_REASONS:
        return normalized
    raise SystemExit("invalid escalation reason: " + value)


def review_severity_rank(severity: str) -> int:
    normalized = severity.strip().lower()
    if normalized not in REVIEW_SEVERITY_RANK:
        raise SystemExit(f"unknown review severity: {severity}")
    return REVIEW_SEVERITY_RANK[normalized]


def review_severity_allows_auto_fix(severity: str) -> bool:
    return severity.strip().lower() in {"p3", "none"}


def highest_review_severity(values: list[str]) -> str:
    if not values:
        return "none"
    severities = [normalized_review_severity(value, "ready") for value in values]
    return max(severities, key=review_severity_rank)


def severity_tags(text: str) -> list[str]:
    tags = []
    for match in re.finditer(r"(?:\[|\b)(P[0-3])(?:\]|\b)", text, re.IGNORECASE):
        tags.append(match.group(1).lower())
    return tags


def native_review_recommendation(output: str) -> str | None:
    for line in output.splitlines():
        label, value = native_labeled_line(line)
        if label != "recommendation":
            continue
        normalized = value.strip().lower().strip("`*_ ")
        normalized = normalized[:-1] if normalized.endswith(".") else normalized
        if normalized in NATIVE_REVIEW_RECOMMENDATIONS:
            return normalized
    return None


def native_labeled_line(line: str) -> tuple[str, str]:
    normalized = line.strip()
    if normalized.startswith(("- ", "* ")):
        normalized = normalized[2:].strip()
    if ":" not in normalized:
        return "", ""
    label, value = normalized.split(":", 1)
    return label.strip().lower(), value.strip()


def native_review_explicit_severity(output: str) -> str | None:
    for line in output.splitlines():
        label, value = native_labeled_line(line)
        if label != "severity":
            continue
        normalized = value.strip().lower().strip("`*_ ")
        normalized = normalized[:-1] if normalized.endswith(".") else normalized
        if normalized in REVIEW_SEVERITIES:
            return normalized
    return None


def native_review_explicit_bounded_fix(output: str) -> str | None:
    for line in output.splitlines():
        label, value = native_labeled_line(line)
        if label not in {"bounded fix", "bounded-fix"}:
            continue
        normalized = value.strip().lower().strip("`*_ ")
        normalized = normalized[:-1] if normalized.endswith(".") else normalized
        if normalized in {"yes", "no"}:
            return normalized
    return None


def native_review_explicit_escalation(output: str) -> str | None:
    for line in output.splitlines():
        label, value = native_labeled_line(line)
        if label != "escalation reason":
            continue
        normalized = value.strip().lower().strip("`*_ ")
        normalized = normalized[:-1] if normalized.endswith(".") else normalized
        if normalized in REVIEW_ESCALATION_REASONS:
            return normalized
    return None


def native_review_has_clear_no_findings(output: str) -> bool:
    normalized = " ".join(output.strip().lower().split())
    if not normalized:
        return False
    clear_phrases = (
        "no findings",
        "no issues",
        "no problems found",
        "no blocking findings",
        "looks good to me",
    )
    return any(phrase in normalized for phrase in clear_phrases)


def native_review_inferred_escalation(output: str) -> str:
    normalized = output.lower()
    if "scope drift" in normalized or "out of scope" in normalized:
        return "scope-drift"
    if "wrong abstraction" in normalized or "abstraction direction" in normalized:
        return "wrong-abstraction"
    if "contract incomplete" in normalized or "incomplete contract" in normalized:
        return "contract-incomplete"
    if "cross-lane conflict" in normalized or "cross lane conflict" in normalized:
        return "cross-lane-conflict"
    if "acceptance change" in normalized or "acceptance criteria changed" in normalized:
        return "acceptance-change"
    return "none"


def native_review_is_structured(output: str) -> bool:
    if native_review_recommendation(output) is not None:
        return True
    if native_review_explicit_severity(output) is not None:
        return True
    if severity_tags(output):
        return True
    if native_review_has_clear_no_findings(output):
        return True
    return False


def native_blocking_findings_present(output: str) -> bool:
    lines = output.splitlines()
    in_blocking = False
    saw_blocking_section = False
    blocking_lines = []
    for line in lines:
        label, value = native_labeled_line(line)
        if label == "blocking findings":
            saw_blocking_section = True
            in_blocking = True
            if value:
                blocking_lines.append(value)
            continue
        if in_blocking and label:
            break
        if in_blocking:
            blocking_lines.append(line)
    if not saw_blocking_section:
        return False
    body = "\n".join(blocking_lines).strip()
    return blocking_present(body)


def normalize_native_review_output(output: str) -> dict[str, str | bool]:
    explicit_recommendation = native_review_recommendation(output)
    explicit_severity = native_review_explicit_severity(output)
    tagged_severity = highest_review_severity(severity_tags(output))
    severity = explicit_severity or tagged_severity
    bounded_fix = native_review_explicit_bounded_fix(output) or "no"
    escalation_reason = native_review_explicit_escalation(output) or native_review_inferred_escalation(output)
    has_blocking_findings = native_blocking_findings_present(output)
    structured = native_review_is_structured(output)
    if not structured:
        return {
            "recommendation": "blocked",
            "severity": "none",
            "bounded_fix": "no",
            "escalation_reason": "unstructured-native-output",
            "explicit_recommendation": False,
            "summary": (
                "Native codex review completed, but the output was not structured enough for x "
                "to safely infer readiness or a bounded fix."
            ),
        }
    if severity == "none" and explicit_recommendation == "changes-requested":
        severity = "p3"
    if severity == "none" and explicit_recommendation == "blocked":
        severity = "p2"
    if severity == "none" and has_blocking_findings:
        severity = "p3"
    if review_severity_rank(severity) >= review_severity_rank("p2"):
        recommendation = explicit_recommendation if explicit_recommendation in {"changes-requested", "blocked"} else "changes-requested"
    elif severity == "p3":
        recommendation = explicit_recommendation if explicit_recommendation in {"changes-requested", "blocked"} else "changes-requested"
    elif explicit_recommendation is not None:
        recommendation = explicit_recommendation
    else:
        recommendation = "ready"
    if recommendation == "ready" and escalation_reason != "none":
        recommendation = "blocked"
    if recommendation == "ready" and review_severity_rank(severity) >= review_severity_rank("p2"):
        recommendation = "changes-requested"
    return {
        "recommendation": recommendation,
        "severity": severity,
        "bounded_fix": bounded_fix,
        "escalation_reason": escalation_reason,
        "explicit_recommendation": explicit_recommendation is not None,
        "summary": f"Native codex review normalized to {recommendation} with severity {severity}.",
    }


def indented_native_output(output: str) -> str:
    body = output.strip() or "No native review output."
    return "\n".join(f"    {line}" if line else "" for line in body.splitlines())


def native_review_findings(output: str, recommendation: str, escalation_reason: str) -> tuple[str, str]:
    raw_output = "Native Codex review output:\n\n" + indented_native_output(output)
    if recommendation == "ready":
        return "- None.", raw_output
    if escalation_reason == "unstructured-native-output":
        return (
            "Native Codex review output was not structured enough for safe automatic handling.\n\n" + raw_output,
            "- None.",
        )
    return raw_output, "- See blocking findings for the native review output."


def maybe_start_bounded_fix_attempt(
    root: Path,
    args: argparse.Namespace,
    review_path: Path,
    task: Path,
    attempt: Path,
    loopback_target: str,
) -> None:
    if args.recommendation != "changes-requested":
        return
    if not review_severity_allows_auto_fix(args.severity):
        return
    if args.bounded_fix != "yes" or args.escalation_reason != "none":
        return
    if loopback_target != "engineer":
        return
    lane = lane_for_attempt(root, attempt)
    if lane is None:
        return
    lane_text = lane.read_text(encoding="utf-8")
    if header_value(lane_text, "Last Attempt") != attempt.stem:
        return
    attempt_id = next_fix_attempt_id(root, task.stem)
    attempt_path = unique_path(state_dirs(root)["attempts"], attempt_id)
    attempt_text = attempt.read_text(encoding="utf-8")
    started_at = now()
    content = read_template(ATTEMPT_TEMPLATE).format(
        attempt_id=attempt_path.stem,
        status="active",
        kind="fix",
        started_at=started_at,
        date=dt.date.today().isoformat(),
        run_id=header_value(attempt_text, "Linked Run"),
        task_id=task.stem,
        lane_id=lane_display_id(lane),
        source_review_id=review_path.stem,
        source_architect_review_id="none",
        title=f"Bounded fix for {review_path.stem}",
        goal=f"Address the bounded code review findings in {review_path.stem}.",
    )
    write(attempt_path, content, args.dry_run)
    task_text = append_bullet(task.read_text(encoding="utf-8"), "Attempts", f"{attempt_path.stem}: fix")
    save(task, task_text, args.dry_run)
    run = resolve_run(root, header_value(attempt_text, "Linked Run"))
    run_text = update_header(run, phase="Fix Loop", needs_user="no")
    run_text = replace_section(run_text, "Active Attempt", attempt_path.stem)
    run_text = append_bullet(run_text, "Fix Loop", f"{attempt_path.stem}: auto bounded fix for {review_path.stem}")
    run_text = replace_section(run_text, "Next Action", f"Generate engineer package for {attempt_path.stem}.")
    run_text = append_event_text(run_text, f"Auto bounded fix attempt started: {attempt_path.stem}")
    save(run, run_text, args.dry_run)
    mark_lane_attempt_started(lane, attempt_path.stem, args.dry_run)


def next_fix_attempt_id(root: Path, task_id: str) -> str:
    attempt_number = len(files_for_task(root, "attempts", task_id)) + 1
    return f"{task_id}-a{attempt_number}"


def review_loopback(args: argparse.Namespace, next_non_ready_count: int) -> str:
    if args.recommendation == "ready":
        return "none"
    if next_non_ready_count >= MAX_NON_READY_REVIEWS:
        if args.loopback_target in {"architect", "root"}:
            return args.loopback_target
        return "architect"
    if args.loopback_target:
        return args.loopback_target
    if args.recommendation == "changes-requested":
        return "engineer"
    if args.recommendation == "blocked":
        return "architect"
    return "none"


def apply_review_result(
    root: Path,
    args: argparse.Namespace,
    review_path: Path,
    task: Path,
    attempt: Path,
    loopback_target: str,
) -> str:
    if args.recommendation == "ready":
        attempt_text = replace_line(attempt.read_text(encoding="utf-8"), "Status: ", "reviewed")
        save(attempt, attempt_text, args.dry_run)
        task_text = replace_section(task.read_text(encoding="utf-8"), "Latest Ready Attempt", attempt.stem)
        task_text = replace_line(task_text, "Status: ", "done")
        save(task, task_text, args.dry_run)
        update_source_review_addressed(root, attempt_text, args.dry_run)
        return "Run merge-ready gate."
    if loopback_target == "engineer":
        return f"Start fresh fix attempt for {review_path.stem}."
    if loopback_target == "architect":
        return f"Loop back to architect before more engineering; review {review_path.stem} is blocked."
    return f"Escalate review {review_path.stem} to root."


def review_needs_user(args: argparse.Namespace, next_non_ready_count: int, loopback_target: str) -> str | None:
    if args.recommendation == "ready":
        return args.needs_user or "no"
    if next_non_ready_count >= MAX_NON_READY_REVIEWS or loopback_target == "root":
        return "yes"
    return args.needs_user
