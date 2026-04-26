from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from x_state_common import *


PACKAGE_ID_BOUNDARY = r"A-Za-z0-9_-"


@dataclass(frozen=True)
class CodexThread:
    id: str
    title: str
    first_user_message: str
    tokens_used: int | None

    @property
    def searchable_text(self) -> str:
        return "\n".join([self.title, self.first_user_message])


def command_audit(args: argparse.Namespace) -> None:
    root = repo_root(Path.cwd())
    run = resolve_run(root, args.run_id)
    codex_state = Path(args.codex_state).expanduser() if args.codex_state else codex_home() / "state_5.sqlite"
    audit = build_audit(root, run, codex_state)
    markdown = render_markdown(audit)
    if args.write:
        written_path = state_dirs(root)["audits"] / f"{run.stem}.md"
        written_path.parent.mkdir(parents=True, exist_ok=True)
        written_path.write_text(markdown, encoding="utf-8")
        audit["written_path"] = str(written_path)
    if args.json:
        print(json.dumps(audit, indent=2, sort_keys=True))
        return
    print(markdown)


def build_audit(root: Path, run: Path, codex_state: Path) -> dict[str, Any]:
    run_text = run.read_text(encoding="utf-8")
    run_info = run_summary(run, run_text)
    packages = package_records(root, run.stem)
    return {
        "run": run_info,
        "engineering_scale": engineering_scale(root, run, run_text),
        "flow": flow_metrics(root, run.stem),
        "tokens": token_metrics(codex_state, packages),
        "written_path": None,
    }


def run_summary(run: Path, run_text: str) -> dict[str, Any]:
    created_at = header_value(run_text, "Created At") or None
    updated_at = header_value(run_text, "Updated At") or None
    status = header_value(run_text, "Status") or "active"
    phase = header_value(run_text, "Current Phase") or "unknown"
    closed_at = updated_at if status in CLOSED_RUN_STATUSES or phase == "Closed" else None
    duration_seconds = seconds_between(created_at, closed_at or updated_at)
    return {
        "run_id": run.stem,
        "status": status,
        "phase": phase,
        "created_at": created_at,
        "updated_at": updated_at,
        "closed_at": closed_at,
        "duration_seconds": duration_seconds,
        "duration": human_duration(duration_seconds),
        "gate_status": header_value(run_text, "Gate Status") or "unknown",
        "architect_gate_status": header_value(run_text, "Architect Gate Status") or "unknown",
        "execution_status": header_value(run_text, "Execution Status") or UNMATERIALIZED,
        "execution_worktree": header_value(run_text, "Execution Worktree") or UNMATERIALIZED,
        "execution_branch": header_value(run_text, "Execution Branch") or UNMATERIALIZED,
    }


def seconds_between(start: str | None, end: str | None) -> int | None:
    if not start or not end:
        return None
    try:
        start_dt = dt.datetime.fromisoformat(start)
        end_dt = dt.datetime.fromisoformat(end)
    except ValueError:
        return None
    return max(0, int((end_dt - start_dt).total_seconds()))


def human_duration(seconds: int | None) -> str:
    if seconds is None:
        return "unavailable"
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def engineering_scale(root: Path, run: Path, run_text: str) -> dict[str, Any]:
    git_root = audit_git_root(root, run)
    base = audit_base_revision(run_text)
    result: dict[str, Any] = {
        "available": False,
        "reason": None,
        "git_root": str(git_root) if git_root else None,
        "base": base,
        "head": None,
        "commit_count": None,
        "diff_shortstat": None,
        "changed_files_count": None,
        "changed_files": [],
    }
    if git_root is None or not git_root.exists():
        result["reason"] = "git root unavailable"
        return result
    head = git_maybe(git_root, "rev-parse", "HEAD")
    result["head"] = head
    if not base:
        result["reason"] = "base revision unavailable"
        return result
    if not git_maybe(git_root, "rev-parse", "--verify", f"{base}^{{commit}}"):
        result["reason"] = f"base revision not found: {base}"
        return result
    result["available"] = True
    result["commit_count"] = int(git_maybe(git_root, "rev-list", "--count", f"{base}..HEAD") or "0")
    result["diff_shortstat"] = git_maybe(git_root, "diff", "--shortstat", base) or "no changes"
    changed_files = git_maybe(git_root, "diff", "--name-only", base) or ""
    result["changed_files"] = [line for line in changed_files.splitlines() if line.strip()]
    result["changed_files_count"] = len(result["changed_files"])
    return result


def audit_git_root(root: Path, run: Path) -> Path | None:
    execution = run_execution_worktree(run)
    if execution and execution.exists():
        return execution
    control = run_control_root(run)
    if control and control.exists():
        return control
    return root.resolve()


def audit_base_revision(run_text: str) -> str | None:
    execution_base = header_value(run_text, "Execution Base")
    if execution_base and execution_base not in {UNMATERIALIZED, "Pending.", "-"}:
        if "@" in execution_base:
            return execution_base.rsplit("@", 1)[1].strip() or None
        return execution_base
    base_commit = header_value(run_text, "Base Commit")
    if base_commit and base_commit not in {"unknown", "Pending.", "-"}:
        return base_commit
    return None


def git_maybe(root: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def flow_metrics(root: Path, run_id: str) -> dict[str, Any]:
    packages = files_for_run(root, "packages", run_id)
    attempts = files_for_run(root, "attempts", run_id)
    reviews = files_for_run(root, "reviews", run_id)
    architect_reviews = files_for_run(root, "architect-reviews", run_id)
    directives = files_for_run(root, "directives", run_id)
    lanes = files_for_run(root, "lanes", run_id)
    integrated_lanes = [
        lane
        for lane in lanes
        if header_value(lane.read_text(encoding="utf-8"), "Integrated") == "yes"
        or header_value(lane.read_text(encoding="utf-8"), "Status") == "integrated"
    ]
    return {
        "packages": len(packages),
        "packages_by_role": count_headers(packages, "Role"),
        "attempts": len(attempts),
        "attempts_by_status": count_headers(attempts, "Status"),
        "reviews": len(reviews),
        "review_recommendations": count_headers(reviews, "Recommendation"),
        "architect_reviews": len(architect_reviews),
        "architect_review_recommendations": count_headers(architect_reviews, "Recommendation"),
        "directives": len(directives),
        "directives_by_status": count_headers(directives, "Status"),
        "lanes": len(lanes),
        "lanes_by_status": count_headers(lanes, "Status"),
        "integrated_lanes": len(integrated_lanes),
        "integrated_lane_ids": [
            header_value(lane.read_text(encoding="utf-8"), "Lane ID") or lane.stem
            for lane in integrated_lanes
        ],
    }


def count_headers(paths: list[Path], header: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        value = header_value(path.read_text(encoding="utf-8"), header) or "unknown"
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def package_records(root: Path, run_id: str) -> list[dict[str, str]]:
    records = []
    for package in files_for_run(root, "packages", run_id):
        text = package.read_text(encoding="utf-8")
        records.append(
            {
                "package_id": package.stem,
                "path": str(package.resolve()),
                "role": header_value(text, "Role") or "unknown",
            }
        )
    return records


def token_metrics(codex_state: Path, packages: list[dict[str, str]]) -> dict[str, Any]:
    threads, reason = read_codex_threads(codex_state)
    metrics: dict[str, Any] = {
        "available": reason is None,
        "reason": reason,
        "codex_state": str(codex_state),
        "total_tokens": 0,
        "tokens_by_role": {},
        "matched_packages": 0,
        "unmatched_packages": 0,
        "ambiguous_packages": 0,
        "packages": [],
        "unresolved": [],
    }
    if reason is not None:
        return metrics

    candidates_by_package = {
        package["package_id"]: matching_threads(package, threads) for package in packages
    }
    provisional_thread_to_packages: dict[str, list[str]] = {}
    for package in packages:
        candidates = candidates_by_package[package["package_id"]]
        if len(candidates) == 1:
            provisional_thread_to_packages.setdefault(candidates[0].id, []).append(package["package_id"])

    tokens_by_role: dict[str, int] = {}
    for package in packages:
        candidates = candidates_by_package[package["package_id"]]
        record: dict[str, Any] = {
            "package_id": package["package_id"],
            "role": package["role"],
            "match_status": "unmatched",
            "thread_id": None,
            "tokens_used": None,
            "reason": "no matching Codex thread",
        }
        if len(candidates) > 1:
            record["match_status"] = "ambiguous"
            record["reason"] = f"matched {len(candidates)} Codex threads"
        elif len(candidates) == 1:
            thread = candidates[0]
            if len(provisional_thread_to_packages.get(thread.id, [])) > 1:
                record["match_status"] = "ambiguous"
                record["thread_id"] = thread.id
                record["tokens_used"] = thread.tokens_used
                record["reason"] = "same Codex thread matched multiple packages"
            else:
                record["match_status"] = "matched"
                record["thread_id"] = thread.id
                record["tokens_used"] = thread.tokens_used
                record["reason"] = None
        metrics["packages"].append(record)

        if record["match_status"] == "matched":
            metrics["matched_packages"] += 1
            if isinstance(record["tokens_used"], int):
                role = record["role"]
                tokens_by_role[role] = tokens_by_role.get(role, 0) + record["tokens_used"]
                metrics["total_tokens"] += record["tokens_used"]
        elif record["match_status"] == "ambiguous":
            metrics["ambiguous_packages"] += 1
            metrics["unresolved"].append(record)
        else:
            metrics["unmatched_packages"] += 1
            metrics["unresolved"].append(record)

    metrics["tokens_by_role"] = dict(sorted(tokens_by_role.items()))
    return metrics


def read_codex_threads(codex_state: Path) -> tuple[list[CodexThread], str | None]:
    if not codex_state.exists():
        return [], "Codex sqlite unavailable"
    try:
        connection = sqlite3.connect(f"file:{codex_state}?mode=ro", uri=True, timeout=1.0)
    except sqlite3.Error as error:
        return [], f"cannot open Codex sqlite: {error}"
    try:
        connection.row_factory = sqlite3.Row
        if not has_threads_table(connection):
            return [], "Codex sqlite has no threads table"
        columns = table_columns(connection, "threads")
        required = {"id", "title", "first_user_message", "tokens_used"}
        missing = sorted(required - columns)
        if missing:
            return [], "Codex threads table missing columns: " + ", ".join(missing)
        rows = connection.execute(
            "select id, title, first_user_message, tokens_used from threads"
        ).fetchall()
    except sqlite3.Error as error:
        return [], f"cannot read Codex sqlite: {error}"
    finally:
        connection.close()
    threads = []
    for row in rows:
        tokens = row["tokens_used"]
        threads.append(
            CodexThread(
                id=str(row["id"] or ""),
                title=str(row["title"] or ""),
                first_user_message=str(row["first_user_message"] or ""),
                tokens_used=int(tokens) if isinstance(tokens, int) else None,
            )
        )
    return threads, None


def has_threads_table(connection: sqlite3.Connection) -> bool:
    row = connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = 'threads'"
    ).fetchone()
    return row is not None


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in connection.execute(f"pragma table_info({table})")}


def matching_threads(package: dict[str, str], threads: list[CodexThread]) -> list[CodexThread]:
    package_id = package["package_id"]
    full_path = package["path"]
    package_path_suffix = f"/packages/{package_id}.md"
    id_pattern = re.compile(
        rf"(?<![{PACKAGE_ID_BOUNDARY}]){re.escape(package_id)}(?![{PACKAGE_ID_BOUNDARY}])"
    )
    matches = []
    for thread in threads:
        text = thread.searchable_text
        if full_path in text or package_path_suffix in text or id_pattern.search(text):
            matches.append(thread)
    return matches


def render_markdown(audit: dict[str, Any]) -> str:
    run = audit["run"]
    scale = audit["engineering_scale"]
    flow = audit["flow"]
    tokens = audit["tokens"]
    lines = [
        f"# x Run Audit: {run['run_id']}",
        "",
        f"Status: {run['status']}",
        f"Current Phase: {run['phase']}",
        f"Created At: {run['created_at'] or '-'}",
        f"Closed At: {run['closed_at'] or '-'}",
        f"Duration: {run['duration']}",
        f"Gate Status: {run['gate_status']}",
        f"Architect Gate Status: {run['architect_gate_status']}",
        "",
        "## Engineering Scale",
        "",
        f"Available: {'yes' if scale['available'] else 'no'}",
        f"Reason: {scale['reason'] or '-'}",
        f"Git Root: {scale['git_root'] or '-'}",
        f"Base: {scale['base'] or '-'}",
        f"Head: {scale['head'] or '-'}",
        f"Commit Count: {display_value(scale['commit_count'])}",
        f"Changed Files: {display_value(scale['changed_files_count'])}",
        f"Diff Shortstat: {scale['diff_shortstat'] or '-'}",
        "",
        "## Flow Metrics",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Packages | {flow['packages']} |",
        f"| Attempts | {flow['attempts']} |",
        f"| Reviews | {flow['reviews']} |",
        f"| Architect Reviews | {flow['architect_reviews']} |",
        f"| Directives | {flow['directives']} |",
        f"| Lanes | {flow['lanes']} |",
        f"| Integrated Lanes | {flow['integrated_lanes']} |",
        "",
        "### Packages By Role",
        "",
        render_counts_table(flow["packages_by_role"], "Role"),
        "",
        "### Code Review Recommendations",
        "",
        render_counts_table(flow["review_recommendations"], "Recommendation"),
        "",
        "### Architect Review Recommendations",
        "",
        render_counts_table(flow["architect_review_recommendations"], "Recommendation"),
        "",
        "## Token Metrics",
        "",
        f"Codex State: {tokens['codex_state']}",
        f"Available: {'yes' if tokens['available'] else 'no'}",
        f"Reason: {tokens['reason'] or '-'}",
        f"Matched Packages: {tokens['matched_packages']}",
        f"Unmatched Packages: {tokens['unmatched_packages']}",
        f"Ambiguous Packages: {tokens['ambiguous_packages']}",
        f"Total Tokens: {tokens['total_tokens']}",
        "",
        "### Tokens By Role",
        "",
        render_counts_table(tokens["tokens_by_role"], "Role", value_name="Tokens"),
        "",
        "### Package Matches",
        "",
        render_package_table(tokens["packages"]),
    ]
    unresolved = tokens["unresolved"]
    if unresolved:
        lines.extend(
            [
                "",
                "### Unresolved Packages",
                "",
                render_unresolved_table(unresolved),
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def display_value(value: Any) -> str:
    return "-" if value is None else str(value)


def render_counts_table(counts: dict[str, int], label_name: str, *, value_name: str = "Count") -> str:
    if not counts:
        return f"| {label_name} | {value_name} |\n| --- | ---: |\n| - | 0 |"
    rows = [f"| {label_name} | {value_name} |", "| --- | ---: |"]
    rows.extend(f"| {escape_cell(key)} | {value} |" for key, value in counts.items())
    return "\n".join(rows)


def render_package_table(packages: list[dict[str, Any]]) -> str:
    if not packages:
        return "| Package | Role | Match | Thread | Tokens |\n| --- | --- | --- | --- | ---: |\n| - | - | - | - | 0 |"
    rows = ["| Package | Role | Match | Thread | Tokens |", "| --- | --- | --- | --- | ---: |"]
    for package in packages:
        rows.append(
            "| {package} | {role} | {match} | {thread} | {tokens} |".format(
                package=escape_cell(package["package_id"]),
                role=escape_cell(package["role"]),
                match=package["match_status"],
                thread=package["thread_id"] or "-",
                tokens=display_value(package["tokens_used"]),
            )
        )
    return "\n".join(rows)


def render_unresolved_table(packages: list[dict[str, Any]]) -> str:
    rows = ["| Package | Role | Match | Reason |", "| --- | --- | --- | --- |"]
    for package in packages:
        rows.append(
            "| {package} | {role} | {match} | {reason} |".format(
                package=escape_cell(package["package_id"]),
                role=escape_cell(package["role"]),
                match=package["match_status"],
                reason=escape_cell(package["reason"] or "-"),
            )
        )
    return "\n".join(rows)


def escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|")
