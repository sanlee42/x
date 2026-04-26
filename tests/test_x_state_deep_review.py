from __future__ import annotations

import unittest

from tests.x_state_test_base import XStateTestCase


class XStateDeepReviewTests(XStateTestCase):
    def start_custom_lane_run(self, run_id: str, scope: str, contract_id: str, task_id: str) -> None:
        self.x("start", "--run-id", run_id, "--goal", task_id)
        self.accept_brief(run_id)
        self.create_custom_contract_and_task(run_id, contract_id, task_id)
        self.x("materialize", "--run-id", run_id, "--scope", scope)
        self.create_execution_plan(run_id, task_id=task_id)
        self.x("architect-gate", "--run-id", run_id)
        self.x("lane-start", "--run-id", run_id, "--lane-id", "lane-llm", "--task-id", task_id)

    def record_ready_readme_attempt(self, run_id: str, scope: str, marker: str, *, commit: bool = False) -> None:
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "Implement marker")
        readme = self.lane_worktree(scope) / "README.md"
        readme.write_text(f"# repo\n\n{marker}\n", encoding="utf-8")
        if commit:
            self.git("add", "README.md", cwd=self.lane_worktree(scope))
            self.git("commit", "-m", "lane marker", cwd=self.lane_worktree(scope))
        self.x(
            "attempt-result",
            "--attempt-id",
            "task-llm-a1",
            "--changed-files",
            "README.md",
            "--summary",
            f"Added {marker}.",
            "--verification",
            "Inspected README.",
            "--residual-risk",
            "None.",
        )
        self.x("package", "--role", "reviewer", "--run-id", run_id, "--task-id", "task-llm", "--attempt-id", "task-llm-a1", "--package-id", f"reviewer-{run_id}")
        self.x(
            "review",
            "--run-id",
            run_id,
            "--attempt-id",
            "task-llm-a1",
            "--review-id",
            f"review-{run_id}",
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

    def test_plan_status_update_cannot_target_plan_from_another_run(self) -> None:
        self.prepare_materialized_run("run-one", "one")
        self.start_custom_lane_run("run-two", "two", "contract-two", "task-two")
        failed = self.x("execution-plan", "--run-id", "run-two", "--plan-id", "plan-llm", "--status", "superseded", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("execution plan plan-llm is not linked to run run-two", failed.stderr + failed.stdout)
        self.assertIn("Status: active", self.execution_plan_file("plan-llm").read_text(encoding="utf-8"))

    def test_architect_gate_rejects_duplicate_lane_task(self) -> None:
        self.x("start", "--run-id", "run-dup-task", "--goal", "Duplicate")
        self.accept_brief("run-dup-task")
        self.create_contract_and_task("run-dup-task")
        self.x("materialize", "--run-id", "run-dup-task", "--scope", "dup-task")
        lanes = "\n".join(
            [
                "| Lane ID | Task ID | Allowed Scope | Forbidden Scope | Worktree Scope | Verification | Done Evidence |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                "| lane-a | task-llm | README.md | Everything else. | lane-a | Inspect README. | README marker changed. |",
                "| lane-b | task-llm | README.md | Everything else. | lane-b | Inspect README. | README marker changed. |",
            ]
        )
        self.create_execution_plan("run-dup-task", parallel_lanes=lanes, integration_order="1. Integrate lane-a.\n2. Integrate lane-b.")
        failed = self.x("architect-gate", "--run-id", "run-dup-task", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("duplicate lane task task-llm", failed.stderr + failed.stdout)

    def test_architect_review_rejects_attempt_from_another_run(self) -> None:
        self.prepare_materialized_run("run-one", "one")
        self.record_ready_readme_attempt("run-one", "one", "run one marker")
        self.start_custom_lane_run("run-two", "two", "contract-two", "task-two")
        failed = self.x(
            "architect-review",
            "--run-id",
            "run-two",
            "--lane-id",
            "lane-llm",
            "--attempt-id",
            "task-llm-a1",
            "--review-id",
            "arch-cross-run",
            "--title",
            "Cross run review",
            "--summary",
            "Should fail.",
            "--recommendation",
            "merge-ok",
            "--criteria",
            "N/A",
            "--verification",
            "N/A",
            "--integration-risk",
            "N/A",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("attempt task-llm-a1 is not linked to run run-two", failed.stderr + failed.stdout)

    def test_committed_lane_diff_is_reviewed_and_integrated(self) -> None:
        self.prepare_materialized_run("run-commit", "commit")
        self.record_ready_readme_attempt("run-commit", "commit", "committed marker", commit=True)
        reviewer_package = self.package_file("reviewer-run-commit").read_text(encoding="utf-8")
        self.assertIn("committed marker", reviewer_package)
        self.approve_integrate_and_mark_green("run-commit", "task-llm-a1", review_id="architect-commit")
        integrated_readme = (self.repo / ".dev/commit/README.md").read_text(encoding="utf-8")
        self.assertIn("committed marker", integrated_readme)

    def test_lane_rejects_second_attempt_while_latest_is_active(self) -> None:
        self.prepare_materialized_run("run-active", "active")
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "First attempt")
        failed = self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "Second attempt", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("already has an active attempt: task-llm-a1", failed.stderr + failed.stdout)

    def test_stale_attempt_cannot_be_reviewed_after_fix_attempt_starts(self) -> None:
        self.prepare_materialized_run("run-stale", "stale")
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "First attempt")
        readme = self.lane_worktree("stale") / "README.md"
        readme.write_text("# repo\n\nwrong marker\n", encoding="utf-8")
        self.x("attempt-result", "--attempt-id", "task-llm-a1", "--changed-files", "README.md", "--summary", "Wrong marker.", "--verification", "Inspected README.", "--residual-risk", "Needs fix.")
        self.x("review", "--run-id", "run-stale", "--attempt-id", "task-llm-a1", "--review-id", "review-stale", "--title", "Needs fix", "--summary", "Wrong.", "--recommendation", "changes-requested", "--blocking-findings", "- Wrong marker.", "--reviewed-diff", "README diff reviewed.", "--verification", "Verification insufficient.")
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "fix", "--source-review-id", "review-stale", "--attempt-id", "task-llm-a2", "--title", "Fix")
        failed = self.x("review", "--run-id", "run-stale", "--attempt-id", "task-llm-a1", "--title", "Late ready", "--summary", "Late.", "--recommendation", "ready", "--reviewed-diff", "Old diff.", "--verification", "Old verification.", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("review must target latest lane attempt: task-llm-a2", failed.stderr + failed.stdout)

    def test_reviewer_package_rejects_untracked_lane_files(self) -> None:
        self.prepare_materialized_run("run-untracked", "untracked")
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "Add file")
        (self.lane_worktree("untracked") / "new-file.txt").write_text("new\n", encoding="utf-8")
        self.x("attempt-result", "--attempt-id", "task-llm-a1", "--changed-files", "new-file.txt", "--summary", "Added new file.", "--verification", "Inspected file.", "--residual-risk", "None.")
        failed = self.x("package", "--role", "reviewer", "--run-id", "run-untracked", "--task-id", "task-llm", "--attempt-id", "task-llm-a1", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("reviewer package cannot capture untracked lane files: new-file.txt", failed.stderr + failed.stdout)


if __name__ == "__main__":
    unittest.main()
