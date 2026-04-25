"""Shared helpers for the x CTO-to-code loop."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
ASSETS = SKILL_DIR / "assets"
LEDGER_TEMPLATE = ASSETS / "ledger-template.md"
RUN_TEMPLATE = ASSETS / "run-template.md"
CONTRACT_TEMPLATE = ASSETS / "contract-template.md"
BRIEF_TEMPLATE = ASSETS / "brief-template.md"
TASK_TEMPLATE = ASSETS / "task-template.md"
ITERATION_TEMPLATE = ASSETS / "iteration-template.md"
REVIEW_TEMPLATE = ASSETS / "review-template.md"
PACKAGE_TEMPLATE = ASSETS / "package-template.md"
DECISION_TEMPLATE = ASSETS / "decision-template.md"
RISK_TEMPLATE = ASSETS / "risk-template.md"
MAX_NON_READY_REVIEWS = 3


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


def x_home() -> Path:
    return Path(os.environ.get("X_HOME", "~/.x")).expanduser()


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
    base = x_home() / "projects" / project_key(root)
    return {
        "ledger": base / "ledger",
        "runs": base / "runs",
        "briefs": base / "briefs",
        "contracts": base / "contracts",
        "tasks": base / "tasks",
        "iterations": base / "iterations",
        "reviews": base / "reviews",
        "packages": base / "packages",
        "decisions": base / "decisions",
        "risks": base / "risks",
    }


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
    return latest_run(root)


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
    return sorted(candidates, key=lambda p: p.name)


def files_for_run(root: Path, kind: str, run_id: str) -> list[Path]:
    return files_for_header(root, kind, "Linked Run", run_id)


def files_for_task(root: Path, kind: str, task_id: str) -> list[Path]:
    return files_for_header(root, kind, "Linked Task", task_id)


def latest_for_task(root: Path, kind: str, task_id: str) -> Path | None:
    candidates = files_for_task(root, kind, task_id)
    return candidates[-1] if candidates else None


def packages_for_iteration(root: Path, iteration_id: str, role: str) -> list[Path]:
    packages = files_for_header(root, "packages", "Linked Iteration", iteration_id)
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
        raise SystemExit("accepted CTO Intake Brief required before Technical Contract")
    return path


def task_for_run(root: Path, run_id: str, task_id: str | None = None) -> Path:
    if task_id:
        return resolve_state_file(root, "tasks", task_id)
    path = latest_for_run(root, "tasks", run_id)
    if path is None:
        raise SystemExit("no Engineer Task found for run")
    return path


def iteration_for_task(root: Path, task_id: str, iteration_id: str | None = None) -> Path:
    if iteration_id:
        iteration = resolve_state_file(root, "iterations", iteration_id)
        if header_value(iteration.read_text(encoding="utf-8"), "Linked Task") != task_id:
            raise SystemExit(f"iteration {iteration_id} is not linked to task {task_id}")
        return iteration
    path = latest_for_task(root, "iterations", task_id)
    if path is None:
        raise SystemExit("no iteration found for task")
    return path


def task_has_iterations(root: Path, task_id: str) -> bool:
    return bool(files_for_task(root, "iterations", task_id))


def task_has_result(task_text: str) -> bool:
    return has_content(section_content(task_text, "Result"))


def item_status(path: Path) -> str:
    return header_value(path.read_text(encoding="utf-8"), "Status")


def item_recommendation(path: Path) -> str:
    return header_value(path.read_text(encoding="utf-8"), "Recommendation")


def active_tasks_for_run(root: Path, run_id: str) -> list[Path]:
    tasks = files_for_run(root, "tasks", run_id)
    return [task for task in tasks if item_status(task) != "superseded"]


def iteration_has_result(iteration_text: str) -> bool:
    status = header_value(iteration_text, "Status")
    if status not in {"done", "reviewed"}:
        return False
    return has_content(section_content(iteration_text, "Changed Files")) and has_content(section_content(iteration_text, "Verification"))


def iteration_has_blockers(iteration_text: str) -> bool:
    return blocking_present(section_content(iteration_text, "Blockers"))


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
