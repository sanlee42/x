from __future__ import annotations

import unittest
from pathlib import Path

from tests.x_state_test_base import XStateTestCase


class XStateMailboxTests(XStateTestCase):
    def test_mailbox_send_list_resolve_status_and_architect_package(self) -> None:
        self.prepare_materialized_run("run-mailbox", "mailbox")

        self.x(
            "mailbox-send",
            "--run-id",
            "run-mailbox",
            "--lane-id",
            "lane-llm",
            "--task-id",
            "task-llm",
            "--kind",
            "request",
            "--from",
            "engineer",
            "--to",
            "main",
            "--session",
            "eng-1",
            "--summary",
            "Need interface confirmation.",
            "--body",
            "Confirm the README marker interface before review.",
            "--related-artifacts",
            "README.md",
            "--message-id",
            "msg-interface",
        )
        message = self.x_home / "projects/repo/messages/msg-interface.md"
        message_text = message.read_text(encoding="utf-8")
        self.assertIn("Status: open", message_text)
        self.assertIn("Kind: request", message_text)
        self.assertIn("Linked Run: run-mailbox", message_text)
        self.assertIn("Linked Lane: lane-llm", message_text)
        self.assertIn("From: engineer", message_text)
        self.assertIn("To: main", message_text)

        listed = self.x("mailbox-list", "--run-id", "run-mailbox")
        self.assertIn("msg-interface: request/open", listed.stdout)
        self.assertIn("summary=Need interface confirmation.", listed.stdout)

        status = self.x("status", "--run-id", "run-mailbox")
        self.assertIn("## Open Mailbox", status.stdout)
        self.assertIn("msg-interface: request/open", status.stdout)

        self.x(
            "package",
            "--role",
            "architect",
            "--run-id",
            "run-mailbox",
            "--title",
            "Architect mailbox board",
            "--package-id",
            "architect-mailbox-board",
        )
        package = self.package_file("architect-mailbox-board").read_text(encoding="utf-8")
        self.assertIn("Open Mailbox:", package)
        self.assertIn("msg-interface: request/open", package)

        self.x(
            "mailbox-resolve",
            "--message-id",
            "msg-interface",
            "--status",
            "addressed",
            "--resolution",
            "Interface confirmed in lane heartbeat.",
        )
        resolved_text = message.read_text(encoding="utf-8")
        self.assertIn("Status: addressed", resolved_text)
        self.assertIn("Interface confirmed in lane heartbeat.", resolved_text)
        open_list = self.x("mailbox-list", "--run-id", "run-mailbox")
        self.assertIn("- none", open_list.stdout)

    def test_mailbox_derives_run_and_rejects_inconsistent_links(self) -> None:
        self.prepare_materialized_run("run-mailbox-derived", "mailbox-derived")

        self.x(
            "mailbox-send",
            "--task-id",
            "task-llm",
            "--kind",
            "ack",
            "--from",
            "main",
            "--to",
            "architect",
            "--summary",
            "Task-linked message.",
            "--message-id",
            "msg-derived",
        )
        derived = self.x_home / "projects/repo/messages/msg-derived.md"
        self.assertIn("Linked Run: run-mailbox-derived", derived.read_text(encoding="utf-8"))

        self.x(
            "task",
            "--run-id",
            "run-mailbox-derived",
            "--task-id",
            "task-other",
            "--title",
            "Other task",
            "--goal",
            "Other goal.",
            "--allowed-scope",
            "README.md",
            "--forbidden-scope",
            "Everything else.",
            "--requirements",
            "Other marker.",
            "--verification",
            "Inspect README.",
            "--done-evidence",
            "Changed README.",
        )
        mismatch = self.x(
            "mailbox-send",
            "--run-id",
            "run-mailbox-derived",
            "--lane-id",
            "lane-llm",
            "--task-id",
            "task-other",
            "--kind",
            "request",
            "--from",
            "main",
            "--to",
            "engineer",
            "--summary",
            "Bad link.",
            check=False,
        )
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("lane lane-llm is not linked to task task-other", mismatch.stderr + mismatch.stdout)

        no_run = self.x(
            "mailbox-send",
            "--lane-id",
            "lane-llm",
            "--kind",
            "request",
            "--from",
            "main",
            "--to",
            "engineer",
            "--summary",
            "Missing run.",
            check=False,
        )
        self.assertNotEqual(no_run.returncode, 0)
        self.assertIn("--lane-id requires --run-id", no_run.stderr + no_run.stdout)

    def test_mailbox_resolve_does_not_partially_update_missing_run(self) -> None:
        self.prepare_materialized_run("run-mailbox-corrupt", "mailbox-corrupt")
        self.x(
            "mailbox-send",
            "--run-id",
            "run-mailbox-corrupt",
            "--kind",
            "request",
            "--from",
            "main",
            "--to",
            "architect",
            "--summary",
            "Corrupt later.",
            "--message-id",
            "msg-corrupt",
        )
        message = self.x_home / "projects/repo/messages/msg-corrupt.md"
        message_text = message.read_text(encoding="utf-8").replace("Linked Run: run-mailbox-corrupt", "Linked Run: run-missing")
        message.write_text(message_text, encoding="utf-8")

        failed = self.x("mailbox-resolve", "--message-id", "msg-corrupt", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("run not found: run-missing", failed.stderr + failed.stdout)
        self.assertIn("Status: open", message.read_text(encoding="utf-8"))


class XStateCleanupWorktreeTests(XStateTestCase):
    def complete_lane(self, run_id: str, scope: str, *, commit_lane: bool) -> Path:
        self.prepare_materialized_run(run_id, scope)
        self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "implementation",
            "--attempt-id",
            "task-llm-a1",
            "--title",
            "Implement marker",
        )
        self.x("package", "--role", "engineer", "--run-id", run_id, "--task-id", "task-llm", "--attempt-id", "task-llm-a1")
        lane = self.lane_worktree(scope)
        (lane / "README.md").write_text("# repo\n\nllm marker\n", encoding="utf-8")
        if commit_lane:
            self.git("add", "README.md", cwd=lane)
            self.git("commit", "-m", "lane marker", cwd=lane)
        self.x(
            "attempt-result",
            "--attempt-id",
            "task-llm-a1",
            "--changed-files",
            "README.md",
            "--summary",
            "Added marker.",
            "--verification",
            "Inspected README.",
            "--residual-risk",
            "None.",
        )
        self.x("package", "--role", "reviewer", "--run-id", run_id, "--task-id", "task-llm", "--attempt-id", "task-llm-a1")
        self.x(
            "review",
            "--run-id",
            run_id,
            "--attempt-id",
            "task-llm-a1",
            "--review-id",
            "review-ready",
            "--title",
            "Ready review",
            "--summary",
            "Ready.",
            "--recommendation",
            "ready",
            "--reviewed-diff",
            "README diff reviewed.",
            "--verification",
            "Verification sufficient.",
        )
        self.approve_integrate_and_mark_green(run_id, "task-llm-a1", review_id="architect-ready")
        return lane

    def test_cleanup_dry_run_lists_clean_integrated_lane_and_apply_removes_it(self) -> None:
        lane = self.complete_lane("run-cleanup", "cleanup", commit_lane=True)
        self.assertTrue(lane.exists())

        dry_run = self.x("cleanup-worktrees", "--run-id", "run-cleanup")
        self.assertIn("Mode: dry-run", dry_run.stdout)
        self.assertIn("would remove lane-llm", dry_run.stdout)
        self.assertTrue(lane.exists())

        applied = self.x("cleanup-worktrees", "--run-id", "run-cleanup", "--apply")
        self.assertIn("removed lane-llm", applied.stdout)
        self.assertFalse(lane.exists())
        self.assertTrue((self.repo / ".dev/cleanup").exists())

    def test_cleanup_keeps_active_unintegrated_worktree(self) -> None:
        self.prepare_materialized_run("run-active-cleanup", "active-cleanup")
        active = self.x("cleanup-worktrees", "--run-id", "run-active-cleanup")
        self.assertIn("skip keep lane-llm", active.stdout)
        self.assertIn("not integrated", active.stdout)
        self.assertIn("status=active", active.stdout)
        self.assertTrue(self.lane_worktree("active-cleanup").exists())

    def test_cleanup_keeps_dirty_integrated_worktree(self) -> None:
        dirty_lane = self.complete_lane("run-dirty-cleanup", "dirty-cleanup", commit_lane=False)
        dirty = self.x("cleanup-worktrees", "--run-id", "run-dirty-cleanup", "--apply")
        self.assertIn("dirty worktree", dirty.stdout)
        self.assertTrue(dirty_lane.exists())

    def test_cleanup_keeps_git_common_dir_mismatch(self) -> None:
        self.prepare_materialized_run("run-mismatch-cleanup", "mismatch-cleanup")
        other = self.base / "other-repo"
        other.mkdir()
        self.git("init", cwd=other)
        self.git("config", "user.email", "x@example.com", cwd=other)
        self.git("config", "user.name", "x test", cwd=other)
        (other / "README.md").write_text("# other\n", encoding="utf-8")
        self.git("add", ".", cwd=other)
        self.git("commit", "-m", "init", cwd=other)
        lane_path = self.lane_file("run-mismatch-cleanup")
        lane_text = lane_path.read_text(encoding="utf-8")
        lane_text = lane_text.replace("Status: active", "Status: integrated")
        lane_text = lane_text.replace("Integrated: no", "Integrated: yes")
        lane_text = lane_text.replace(
            f"Worktree: {self.lane_worktree('mismatch-cleanup')}",
            f"Worktree: {other.resolve()}",
        )
        lane_path.write_text(lane_text, encoding="utf-8")

        mismatch = self.x("cleanup-worktrees", "--run-id", "run-mismatch-cleanup", "--apply")
        self.assertIn("git common dir mismatch", mismatch.stdout)
        self.assertTrue(other.exists())

    def test_cleanup_keeps_non_lane_registered_paths(self) -> None:
        self.prepare_materialized_run("run-registration-cleanup", "registration-cleanup")
        lane_path = self.lane_file("run-registration-cleanup")
        nested = self.lane_worktree("registration-cleanup") / "nested"
        nested.mkdir()
        lane_text = lane_path.read_text(encoding="utf-8")
        lane_text = lane_text.replace("Status: active", "Status: integrated")
        lane_text = lane_text.replace("Integrated: no", "Integrated: yes")
        lane_text = lane_text.replace(
            f"Worktree: {self.lane_worktree('registration-cleanup')}",
            f"Worktree: {nested.resolve()}",
        )
        lane_path.write_text(lane_text, encoding="utf-8")

        nested_result = self.x("cleanup-worktrees", "--run-id", "run-registration-cleanup", "--apply")
        self.assertIn("not a registered git worktree", nested_result.stdout)
        self.assertTrue(nested.exists())

        lane_text = lane_path.read_text(encoding="utf-8")
        lane_text = lane_text.replace(f"Worktree: {nested.resolve()}", f"Worktree: {self.repo.resolve()}")
        lane_path.write_text(lane_text, encoding="utf-8")

        control_result = self.x("cleanup-worktrees", "--run-id", "run-registration-cleanup", "--apply")
        self.assertIn("control root", control_result.stdout)
        self.assertTrue(self.repo.exists())

    def test_cleanup_keeps_duplicate_lane_worktree_paths(self) -> None:
        self.prepare_materialized_run("run-duplicate-cleanup", "duplicate-cleanup")
        lane_path = self.lane_file("run-duplicate-cleanup")
        lane_text = lane_path.read_text(encoding="utf-8")
        lane_text = lane_text.replace("Status: active", "Status: integrated")
        lane_text = lane_text.replace("Integrated: no", "Integrated: yes")
        lane_path.write_text(lane_text, encoding="utf-8")

        duplicate = self.x_home / "projects/repo/lanes/run-duplicate-cleanup--lane-copy.md"
        duplicate.write_text(
            lane_text.replace("# x Lane: lane-llm", "# x Lane: lane-copy").replace("Lane ID: lane-llm", "Lane ID: lane-copy"),
            encoding="utf-8",
        )

        result = self.x("cleanup-worktrees", "--run-id", "run-duplicate-cleanup", "--apply")
        self.assertIn("duplicate lane worktree path", result.stdout)
        self.assertTrue(self.lane_worktree("duplicate-cleanup").exists())


if __name__ == "__main__":
    unittest.main()
