"""Shared helpers for the x architect-to-code loop."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS = SKILL_DIR / "assets"
LEDGER_TEMPLATE = ASSETS / "ledger-template.md"
RUN_TEMPLATE = ASSETS / "run-template.md"
CONTRACT_TEMPLATE = ASSETS / "contract-template.md"
BRIEF_TEMPLATE = ASSETS / "brief-template.md"
TASK_TEMPLATE = ASSETS / "task-template.md"
ATTEMPT_TEMPLATE = ASSETS / "attempt-template.md"
REVIEW_TEMPLATE = ASSETS / "review-template.md"
PACKAGE_TEMPLATE = ASSETS / "package-template.md"
EXECUTION_PLAN_TEMPLATE = ASSETS / "execution-plan-template.md"
LANE_TEMPLATE = ASSETS / "lane-template.md"
ARCHITECT_REVIEW_TEMPLATE = ASSETS / "architect-review-template.md"
DIRECTIVE_TEMPLATE = ASSETS / "directive-template.md"
DECISION_TEMPLATE = ASSETS / "decision-template.md"
RISK_TEMPLATE = ASSETS / "risk-template.md"
MESSAGE_TEMPLATE = ASSETS / "message-template.md"
DISCUSSION_TEMPLATE = ASSETS / "discussion-template.md"
ROLE_BRIEF_TEMPLATE = ASSETS / "role-brief-template.md"
ARCHITECT_INTAKE_TEMPLATE = ASSETS / "architect-intake-template.md"
ROLE_CARD_TEMPLATE = ASSETS / "role-card-template.md"
DEFAULT_ROLE_CARDS_DIR = ASSETS / "role-cards"
MAX_NON_READY_REVIEWS = 3
CLOSED_RUN_STATUSES = {"accepted", "closed", "superseded"}
MATERIALIZED = "materialized"
UNMATERIALIZED = "unmaterialized"


def repo_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "PROJECT_CONSTRAINTS.md").exists() and (candidate / "AGENTS.md").exists():
            return candidate
    raise SystemExit("repo root not found: expected PROJECT_CONSTRAINTS.md and AGENTS.md")


def now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def today() -> str:
    return dt.date.today().strftime("%Y%m%d")


def slug(value: str, fallback: str = "item") -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value.strip().lower()).strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return (normalized or fallback)[:56].strip("-") or fallback


def git_output(root: Path, *args: str, default: str | None = None) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        if default is not None:
            return default
        raise SystemExit(f"git command failed: git -C {root} {' '.join(args)}")


def git_path(root: Path, *args: str) -> Path:
    value = git_output(root, *args)
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def current_git_context(root: Path) -> dict[str, str]:
    return {
        "root": str(root.resolve()),
        "branch": git_output(root, "rev-parse", "--abbrev-ref", "HEAD", default="unknown"),
        "base_commit": git_output(root, "rev-parse", "HEAD", default="unknown"),
        "git_common_dir": str(git_path(root, "rev-parse", "--git-common-dir")),
    }


def x_home() -> Path:
    return Path(os.environ.get("X_HOME", "~/.x")).expanduser()


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()


def git_worktree_project_name(root: Path) -> str | None:
    git_file = root / ".git"
    if not git_file.is_file():
        return None
    content = git_file.read_text(encoding="utf-8").strip()
    prefix = "gitdir: "
    if not content.startswith(prefix):
        return None
    git_dir = Path(content[len(prefix) :]).expanduser()
    if not git_dir.is_absolute():
        git_dir = (root / git_dir).resolve()
    parts = git_dir.parts
    if ".git" not in parts:
        return None
    git_index = parts.index(".git")
    if len(parts) > git_index + 1 and parts[git_index + 1] == "worktrees":
        return Path(*parts[:git_index]).name
    return None


def project_key(root: Path) -> str:
    override = os.environ.get("X_PROJECT_KEY")
    if override:
        return slug(override, "project")
    return slug(git_worktree_project_name(root) or root.name, "project")


def state_dirs(root: Path) -> dict[str, Path]:
    base = project_state_dir(root)
    return {
        "ledger": base / "ledger",
        "runs": base / "runs",
        "briefs": base / "briefs",
        "contracts": base / "contracts",
        "tasks": base / "tasks",
        "attempts": base / "attempts",
        "reviews": base / "reviews",
        "execution-plans": base / "execution-plans",
        "lanes": base / "lanes",
        "architect-reviews": base / "architect-reviews",
        "directives": base / "directives",
        "packages": base / "packages",
        "decisions": base / "decisions",
        "risks": base / "risks",
        "messages": base / "messages",
        "audits": base / "audits",
        "discussions": base / "discussions",
        "role-briefs": base / "role-briefs",
        "architect-intakes": base / "architect-intakes",
        "roles": base / "roles",
        "boards": base / "boards",
    }


def project_state_dir(root: Path) -> Path:
    return x_home() / "projects" / project_key(root)


def project_profile_path(root: Path) -> Path:
    return root / ".x/project/profile.md"


def ledger_path(root: Path) -> Path:
    return state_dirs(root)["ledger"] / "current.md"


def unique_path(directory: Path, stem: str) -> Path:
    path = directory / f"{stem}.md"
    if not path.exists():
        return path
    index = 2
    while True:
        candidate = directory / f"{stem}-{index}.md"
        if not candidate.exists():
            return candidate
        index += 1


def latest_run(root: Path) -> Path:
    runs = state_dirs(root)["runs"]
    candidates = sorted(runs.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not candidates:
        raise SystemExit("no x runs found")
    return candidates[0]


def resolve_run(root: Path, run_id: str | None) -> Path:
    if run_id:
        path = state_dirs(root)["runs"] / f"{run_id}.md"
        if not path.exists():
            raise SystemExit(f"run not found: {run_id}")
        return path
    return select_current_run(root)


def all_runs(root: Path) -> list[Path]:
    runs = state_dirs(root)["runs"]
    if not runs.exists():
        return []
    return sorted(runs.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)


def run_status(path: Path) -> str:
    return header_value(path.read_text(encoding="utf-8"), "Status") or "active"


def run_phase(path: Path) -> str:
    return header_value(path.read_text(encoding="utf-8"), "Current Phase") or "unknown"


def active_runs(root: Path) -> list[Path]:
    return [run for run in all_runs(root) if run_status(run) not in CLOSED_RUN_STATUSES]


def header_path(text: str, name: str) -> Path | None:
    value = header_value(text, name)
    if value in {"", "-", "Pending.", UNMATERIALIZED, "none"}:
        return None
    return Path(value).expanduser().resolve()


def run_control_root(run: Path) -> Path | None:
    return header_path(run.read_text(encoding="utf-8"), "Control Root")


def run_execution_worktree(run: Path) -> Path | None:
    return header_path(run.read_text(encoding="utf-8"), "Execution Worktree")


def run_execution_status(run: Path) -> str:
    return header_value(run.read_text(encoding="utf-8"), "Execution Status") or UNMATERIALIZED


def run_is_materialized(run: Path) -> bool:
    return run_execution_status(run) == MATERIALIZED and run_execution_worktree(run) is not None


def select_current_run(root: Path) -> Path:
    runs = active_runs(root)
    if not runs:
        return latest_run(root)
    current = root.resolve()
    execution_matches = [run for run in runs if run_execution_worktree(run) == current]
    if len(execution_matches) == 1:
        return execution_matches[0]
    if len(execution_matches) > 1:
        ids = ", ".join(run.stem for run in execution_matches)
        raise SystemExit(f"multiple active x runs are bound to this execution worktree; pass --run-id ({ids})")
    control_matches = [run for run in runs if run_control_root(run) == current]
    if len(control_matches) == 1:
        return control_matches[0]
    if len(control_matches) > 1:
        ids = ", ".join(run.stem for run in control_matches)
        raise SystemExit(f"multiple active x runs in this control root; pass --run-id ({ids})")
    if len(runs) == 1:
        return runs[0]
    ids = ", ".join(run.stem for run in runs)
    raise SystemExit(f"multiple active x runs; pass --run-id ({ids})")


def resolve_state_file(root: Path, kind: str, item_id: str) -> Path:
    path = state_dirs(root)[kind] / f"{item_id}.md"
    if not path.exists():
        raise SystemExit(f"{kind[:-1]} not found: {item_id}")
    return path


def header_value(text: str, name: str) -> str:
    prefix = f"{name}: "
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def latest_for_run(root: Path, kind: str, run_id: str) -> Path | None:
    directory = state_dirs(root)[kind]
    if not directory.exists():
        return None
    candidates = []
    for path in directory.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if header_value(text, "Linked Run") == run_id:
            candidates.append(path)
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def latest_accepted_brief_for_run(root: Path, run_id: str) -> Path | None:
    candidates = [
        path
        for path in files_for_run(root, "briefs", run_id)
        if header_value(path.read_text(encoding="utf-8"), "Status") == "accepted"
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def files_for_header(root: Path, kind: str, header: str, value: str) -> list[Path]:
    directory = state_dirs(root)[kind]
    if not directory.exists():
        return []
    candidates = []
    for path in directory.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if header_value(text, header) == value:
            candidates.append(path)
    return sorted(candidates, key=state_file_sort_key)


def state_file_sort_key(path: Path) -> tuple:
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", path.name))


def files_for_run(root: Path, kind: str, run_id: str) -> list[Path]:
    return files_for_header(root, kind, "Linked Run", run_id)


def files_for_task(root: Path, kind: str, task_id: str) -> list[Path]:
    return files_for_header(root, kind, "Linked Task", task_id)


def latest_for_task(root: Path, kind: str, task_id: str) -> Path | None:
    candidates = files_for_task(root, kind, task_id)
    return candidates[-1] if candidates else None


def packages_for_attempt(root: Path, attempt_id: str, role: str) -> list[Path]:
    packages = files_for_header(root, "packages", "Linked Attempt", attempt_id)
    return [package for package in packages if header_value(package.read_text(encoding="utf-8"), "Role") == role]


def read_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        print(content)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(path)


def replace_line(text: str, prefix: str, value: str) -> str:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{prefix}{value}"
            return "\n".join(lines) + "\n"
    return text


def upsert_line_after(text: str, prefix: str, value: str, after_prefix: str) -> str:
    replacement = f"{prefix}{value}"
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            return "\n".join(lines) + "\n"
    for index, line in enumerate(lines):
        if line.startswith(after_prefix):
            lines.insert(index + 1, replacement)
            return "\n".join(lines) + "\n"
    lines.insert(1, replacement)
    return "\n".join(lines) + "\n"


def section_bounds(text: str, name: str) -> tuple[int, int] | None:
    heading = f"## {name}"
    start = text.find(heading)
    if start < 0:
        return None
    next_heading = text.find("\n## ", start + len(heading))
    end = len(text) if next_heading < 0 else next_heading
    return start, end


def replace_section(text: str, name: str, content: str) -> str:
    heading = f"## {name}"
    replacement = f"{heading}\n\n{content.strip()}\n"
    bounds = section_bounds(text, name)
    if bounds is None:
        event_log = text.find("\n## Event Log")
        insertion = "\n" + replacement
        if event_log < 0:
            return text.rstrip() + insertion + "\n"
        return text[:event_log].rstrip() + insertion + text[event_log:]
    start, end = bounds
    return text[:start].rstrip() + "\n\n" + replacement + text[end:]


def section_content(text: str, name: str) -> str:
    bounds = section_bounds(text, name)
    if bounds is None:
        return ""
    start, end = bounds
    body = text[start:end].split("\n", 1)[1] if "\n" in text[start:end] else ""
    return body.strip()


def has_content(value: str) -> bool:
    return value.strip() not in {"", "-", "Pending.", "Not specified.", "None.", "- None."}


def append_bullet(text: str, name: str, item: str) -> str:
    current = section_content(text, name)
    if current in {"", "-", "Pending."}:
        content = f"- {item.strip()}"
    else:
        content = current.rstrip() + f"\n- {item.strip()}"
    return replace_section(text, name, content)


def remove_bullet_containing(text: str, name: str, needle: str) -> str:
    current = section_content(text, name)
    if current in {"", "-", "Pending."}:
        return text
    kept = [line for line in current.splitlines() if needle not in line]
    content = "\n".join(kept).strip() or "-"
    return replace_section(text, name, content)


def append_event_text(text: str, event: str) -> str:
    return text.rstrip() + f"\n- {now()}: {event}\n"


def content_arg(args: argparse.Namespace) -> str:
    if getattr(args, "content_file", None):
        if args.content_file == "-":
            return sys.stdin.read()
        return Path(args.content_file).read_text(encoding="utf-8")
    if getattr(args, "content", None) is None:
        raise SystemExit("--content or --content-file is required")
    return args.content


def optional_text_arg(args: argparse.Namespace, name: str, default: str = "Not provided.") -> str:
    file_value = getattr(args, f"{name}_file", None)
    if file_value:
        if file_value == "-":
            return sys.stdin.read()
        return Path(file_value).read_text(encoding="utf-8")
    value = getattr(args, name, None)
    if value is None:
        return default
    return value


def blocking_present(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    return normalized not in {"", "none", "none.", "- none", "- none.", "n/a", "na"}


def ensure_ledger(root: Path, *, objective: str = "To be defined.", next_action: str = "-", dry_run: bool = False) -> Path:
    path = ledger_path(root)
    if path.exists():
        return path
    timestamp = now()
    content = read_template(LEDGER_TEMPLATE).format(
        updated_at=timestamp,
        objective=objective,
        next_action=next_action,
    )
    write(path, content, dry_run)
    return path


def update_header(path: Path, *, status: str | None = None, phase: str | None = None, needs_user: str | None = None) -> str:
    text = path.read_text(encoding="utf-8")
    text = replace_line(text, "Updated At: ", now())
    if status:
        text = replace_line(text, "Status: ", status)
    if phase:
        text = replace_line(text, "Current Phase: ", phase)
    if needs_user:
        text = replace_line(text, "Needs User: ", needs_user)
    return text


def save(path: Path, text: str, dry_run: bool) -> None:
    if dry_run:
        print(text)
        return
    path.write_text(text, encoding="utf-8")
    print(path)


def run_id_from_path(path: Path) -> str:
    return path.stem


def contract_for_run(root: Path, run_id: str, contract_id: str | None = None) -> Path:
    if contract_id:
        return resolve_state_file(root, "contracts", contract_id)
    path = latest_for_run(root, "contracts", run_id)
    if path is None:
        raise SystemExit("no Technical Contract found for run")
    return path


def accepted_brief_for_run(root: Path, run_id: str, brief_id: str | None = None) -> Path:
    if brief_id:
        path = resolve_state_file(root, "briefs", brief_id)
        text = path.read_text(encoding="utf-8")
        if header_value(text, "Linked Run") != run_id:
            raise SystemExit(f"brief {brief_id} is not linked to run {run_id}")
        if header_value(text, "Status") != "accepted":
            raise SystemExit(f"brief {brief_id} is not accepted")
        return path
    path = latest_accepted_brief_for_run(root, run_id)
    if path is None:
        raise SystemExit("accepted Architecture Brief required before Technical Contract")
    return path


def accepted_brief_with_direction(root: Path, run_id: str) -> Path:
    brief = accepted_brief_for_run(root, run_id)
    direction = section_content(brief.read_text(encoding="utf-8"), "Accepted Direction")
    if not has_content(direction):
        raise SystemExit(f"accepted Architecture Brief has no accepted direction: {brief.stem}")
    return brief


def require_materialized_run(run: Path, operation: str) -> Path:
    if run_execution_status(run) != MATERIALIZED:
        raise SystemExit(f"{operation} requires a materialized execution worktree for run {run.stem}")
    worktree = run_execution_worktree(run)
    if worktree is None:
        raise SystemExit(f"{operation} requires Execution Worktree for run {run.stem}")
    if not worktree.exists():
        raise SystemExit(f"{operation} execution worktree is missing for run {run.stem}: {worktree}")
    return worktree


def task_for_run(root: Path, run_id: str, task_id: str | None = None) -> Path:
    if task_id:
        return resolve_state_file(root, "tasks", task_id)
    path = latest_for_run(root, "tasks", run_id)
    if path is None:
        raise SystemExit("no Engineer Task found for run")
    return path


def attempt_for_task(root: Path, task_id: str, attempt_id: str | None = None) -> Path:
    if attempt_id:
        attempt = resolve_state_file(root, "attempts", attempt_id)
        if header_value(attempt.read_text(encoding="utf-8"), "Linked Task") != task_id:
            raise SystemExit(f"attempt {attempt_id} is not linked to task {task_id}")
        return attempt
    path = latest_for_task(root, "attempts", task_id)
    if path is None:
        raise SystemExit("no attempt found for task")
    return path


def task_has_attempts(root: Path, task_id: str) -> bool:
    return bool(files_for_task(root, "attempts", task_id))


def task_has_result(task_text: str) -> bool:
    return has_content(section_content(task_text, "Result"))


def item_status(path: Path) -> str:
    return header_value(path.read_text(encoding="utf-8"), "Status")


def item_recommendation(path: Path) -> str:
    return header_value(path.read_text(encoding="utf-8"), "Recommendation")


def active_tasks_for_run(root: Path, run_id: str) -> list[Path]:
    tasks = files_for_run(root, "tasks", run_id)
    return [task for task in tasks if item_status(task) != "superseded"]


def attempt_has_result(attempt_text: str) -> bool:
    status = header_value(attempt_text, "Status")
    if status not in {"done", "reviewed"}:
        return False
    return has_content(section_content(attempt_text, "Changed Files")) and has_content(section_content(attempt_text, "Verification"))


def attempt_has_blockers(attempt_text: str) -> bool:
    return blocking_present(section_content(attempt_text, "Blockers"))


def unresolved_reviews_for_task(root: Path, task_id: str) -> list[Path]:
    unresolved = []
    for review in files_for_task(root, "reviews", task_id):
        text = review.read_text(encoding="utf-8")
        status = header_value(text, "Status")
        recommendation = header_value(text, "Recommendation")
        if recommendation != "ready" and status not in {"addressed", "accepted", "superseded"}:
            unresolved.append(review)
    return unresolved


def non_ready_review_count(root: Path, task_id: str) -> int:
    return sum(1 for review in files_for_task(root, "reviews", task_id) if item_recommendation(review) != "ready")
