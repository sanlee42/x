from __future__ import annotations

from pathlib import Path

from x_state_common import *
from x_state_execution import lane_display_id


def engineer_fix_loopback_failures(root: Path, run_id: str, task_id: str, lane: Path) -> list[str]:
    latest_review = latest_for_task(root, "reviews", task_id)
    if latest_review is None:
        return []
    latest_text = latest_review.read_text(encoding="utf-8")
    if header_value(latest_text, "Recommendation") == "ready":
        return []
    if header_value(latest_text, "Status") in {"addressed", "accepted", "superseded"}:
        return []
    loopback_target = header_value(latest_text, "Loopback Target")
    if loopback_target not in {"architect", "root"}:
        return []
    if non_ready_review_count(root, task_id) >= FORCE_REPLAN_NON_READY_REVIEWS:
        return [
            f"task {task_id} has {FORCE_REPLAN_NON_READY_REVIEWS} or more non-ready reviews; "
            "force architect replan before starting another engineer fix attempt"
        ]
    if architect_loopback_response_exists(root, run_id, latest_review, lane):
        return []
    return [
        f"latest unresolved review {latest_review.stem} loops to {loopback_target}; "
        "record an architect directive/review before starting another engineer fix attempt"
    ]


def architect_loopback_response_exists(root: Path, run_id: str, review: Path, lane: Path) -> bool:
    review_text = review.read_text(encoding="utf-8")
    attempt_id = header_value(review_text, "Linked Attempt")
    lane_id = lane_display_id(lane)
    review_mtime = review.stat().st_mtime
    for architect_review in files_for_run(root, "architect-reviews", run_id):
        architect_text = architect_review.read_text(encoding="utf-8")
        if header_value(architect_text, "Status") == "superseded":
            continue
        if header_value(architect_text, "Linked Attempt") == attempt_id and header_value(architect_text, "Linked Lane") == lane_id:
            return True
    for directive in files_for_run(root, "directives", run_id):
        directive_text = directive.read_text(encoding="utf-8")
        if header_value(directive_text, "Status") == "superseded":
            continue
        directive_lane = header_value(directive_text, "Linked Lane")
        if directive_lane not in {"", "none", lane_id}:
            continue
        if directive.stat().st_mtime >= review_mtime:
            return True
    return False
