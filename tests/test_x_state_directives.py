from __future__ import annotations

import unittest

from tests.x_state_test_base import XStateTestCase


class XStateDirectiveTests(XStateTestCase):
    def pause_lane(self, run_id: str, directive_id: str = "pause-lane") -> None:
        self.x(
            "architect-directive",
            "--run-id",
            run_id,
            "--directive-id",
            directive_id,
            "--title",
            "Pause lane",
            "--target",
            "lane",
            "--lane-id",
            "lane-llm",
            "--action",
            "pause-lane",
            "--summary",
            "Pause lane while architect checks scope.",
            "--instructions",
            "Do not hand work to engineer or reviewer until resumed.",
            "--acceptance",
            "Lane remains paused until architect resumes it.",
        )

    def resume_lane(self, run_id: str) -> None:
        self.x(
            "architect-directive",
            "--run-id",
            run_id,
            "--directive-id",
            "resume-lane",
            "--title",
            "Resume lane",
            "--target",
            "lane",
            "--lane-id",
            "lane-llm",
            "--action",
            "resume-lane",
            "--summary",
            "Resume the lane after architect check.",
            "--instructions",
            "Continue from the restored lane state.",
            "--acceptance",
            "Engineer package can be generated again.",
        )

    def prepare_ready_lane_for_close(self, run_id: str, scope: str) -> None:
        self.prepare_materialized_run(run_id, scope)
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "Implement marker")
        self.x("package", "--role", "engineer", "--run-id", run_id, "--task-id", "task-llm", "--attempt-id", "task-llm-a1")
        (self.lane_worktree(scope) / "README.md").write_text("# repo\n\nllm marker\n", encoding="utf-8")
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
        self.approve_integrate_and_mark_green(run_id, "task-llm-a1")

    def test_pause_directive_blocks_package_until_resume(self) -> None:
        self.prepare_materialized_run("run-pause", "pause")
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "Implement marker")
        self.pause_lane("run-pause")
        failed = self.x(
            "package",
            "--role",
            "engineer",
            "--run-id",
            "run-pause",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("engineer package blocked", failed.stderr + failed.stdout)
        self.assertIn("lane lane-llm is paused by architect", failed.stderr + failed.stdout)
        self.assertIn("Status: architect-paused", self.lane_file("run-pause").read_text(encoding="utf-8"))

        self.resume_lane("run-pause")
        self.x(
            "package",
            "--role",
            "engineer",
            "--run-id",
            "run-pause",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
            "--package-id",
            "engineer-after-resume",
        )
        self.assertIn("Status: addressed", (self.x_home / "projects/repo/directives/pause-lane.md").read_text(encoding="utf-8"))
        self.assertIn("Status: active", self.lane_file("run-pause").read_text(encoding="utf-8"))

    def test_pause_directive_blocks_new_attempt(self) -> None:
        self.prepare_materialized_run("run-pause-attempt", "pause-attempt")
        self.pause_lane("run-pause-attempt")
        failed = self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "implementation",
            "--title",
            "Should not start",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("lane work blocked", failed.stderr + failed.stdout)

    def test_replan_directive_blocks_engineer_package(self) -> None:
        self.prepare_materialized_run("run-replan", "replan")
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "Implement marker")
        self.x(
            "architect-directive",
            "--run-id",
            "run-replan",
            "--directive-id",
            "replan-now",
            "--title",
            "Replan",
            "--target",
            "plan",
            "--action",
            "replan",
            "--summary",
            "Current execution plan is no longer valid.",
            "--instructions",
            "Stop lane work and produce a revised execution plan.",
            "--acceptance",
            "New execution plan passes architect gate.",
        )
        failed = self.x(
            "package",
            "--role",
            "engineer",
            "--run-id",
            "run-replan",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("architect replan directive is open", failed.stderr + failed.stdout)
        self.assertIn("Status: replan-required", self.execution_plan_file("plan-llm").read_text(encoding="utf-8"))
        self.assertIn("Status: replan-required", self.lane_file("run-replan").read_text(encoding="utf-8"))
        self.create_execution_plan("run-replan", plan_id="plan-llm-v2")
        self.x("architect-gate", "--run-id", "run-replan")
        self.assertIn(
            "Status: addressed",
            (self.x_home / "projects/repo/directives/replan-now.md").read_text(encoding="utf-8"),
        )
        still_stopped = self.x(
            "package",
            "--role",
            "engineer",
            "--run-id",
            "run-replan",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
            check=False,
        )
        self.assertNotEqual(still_stopped.returncode, 0)
        self.assertIn("status is replan-required", still_stopped.stderr + still_stopped.stdout)

    def test_root_decision_directive_blocks_accepted_close(self) -> None:
        self.prepare_ready_lane_for_close("run-root-decision", "root-decision")
        self.x(
            "architect-directive",
            "--run-id",
            "run-root-decision",
            "--directive-id",
            "root-choice",
            "--title",
            "Root choice",
            "--target",
            "run",
            "--action",
            "root-decision",
            "--summary",
            "Root must choose whether to merge this behavior.",
            "--instructions",
            "Do not close accepted until root resolves the decision.",
            "--acceptance",
            "Decision is recorded or directive is addressed.",
        )
        close = self.x("close", "--run-id", "run-root-decision", "--summary", "ready", check=False)
        self.assertNotEqual(close.returncode, 0)
        self.assertIn("open architect directive action=root-decision", close.stderr + close.stdout)
        self.x(
            "decision",
            "--run-id",
            "run-root-decision",
            "--decision-id",
            "decision-root-choice",
            "--title",
            "Root accepts merge",
            "--decision",
            "Proceed with merge-back recommendation.",
        )
        self.assertIn(
            "Status: addressed",
            (self.x_home / "projects/repo/directives/root-choice.md").read_text(encoding="utf-8"),
        )
        self.x("close", "--run-id", "run-root-decision", "--summary", "ready")

    def test_architect_package_contains_control_board_and_directives(self) -> None:
        self.prepare_materialized_run("run-board", "board")
        self.pause_lane("run-board", "pause-board")
        self.x("package", "--role", "architect", "--run-id", "run-board", "--title", "Architect board", "--package-id", "architect-board")
        package = self.package_file("architect-board").read_text(encoding="utf-8")
        self.assertIn("Architect Control Board:", package)
        self.assertIn("Open Directives:", package)
        self.assertIn("pause-board: action=pause-lane", package)
        self.assertIn("lane-llm; status=architect-paused", package)


if __name__ == "__main__":
    unittest.main()
