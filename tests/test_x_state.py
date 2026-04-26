from __future__ import annotations

import sys
import unittest
from pathlib import Path

from tests.x_state_test_base import ROOT, XStateTestCase


class XStateWorkflowTests(XStateTestCase):
    def test_cto_room_starts_without_goal_and_materializes_after_accepted_brief(self) -> None:
        self.x("start", "--run-id", "run-room")
        run_text = self.run_file("run-room").read_text(encoding="utf-8")
        self.assertIn("Run Mode: architect-room", run_text)
        self.assertIn("Engineering Goal\n\nTo be defined with architect.", run_text)
        self.assertIn("Execution Status: unmaterialized", run_text)
        self.assertFalse((self.repo / ".dev").exists())

        self.x("package", "--role", "architect", "--run-id", "run-room", "--title", "architect room")
        old_role = "c" + "to"
        failed = self.x("package", "--role", old_role, "--run-id", "run-room", "--title", "old room", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("invalid choice", failed.stderr + failed.stdout)

        failed = self.x("materialize", "--run-id", "run-room", "--scope", "llm", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("accepted Architecture Brief", failed.stderr + failed.stdout)

        failed = self.x(
            "brief",
            "--run-id",
            "run-room",
            "--title",
            "missing direction",
            "--architect-questions",
            "- None.",
            "--options",
            "- One option.",
            "--recommendation",
            "Proceed.",
            "--risks",
            "- None.",
            "--root-decisions-needed",
            "- None.",
            "--status",
            "accepted",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("--accepted-direction is required", failed.stderr + failed.stdout)

        self.accept_brief("run-room")
        self.x("materialize", "--run-id", "run-room", "--scope", "llm")
        self.assertTrue((self.repo / ".dev/llm").exists())
        branch = self.git("rev-parse", "--abbrev-ref", "HEAD", cwd=self.repo / ".dev/llm").stdout.strip()
        self.assertEqual(branch, "feat/llm")
        run_text = self.run_file("run-room").read_text(encoding="utf-8")
        self.assertIn("Execution Status: materialized", run_text)
        self.assertIn(str((self.repo / ".dev/llm").resolve()), run_text)

    def test_architect_gate_validates_execution_plan_and_unlocks_lanes(self) -> None:
        self.x("start", "--run-id", "run-gate", "--goal", "Gate")
        self.accept_brief("run-gate")
        self.create_contract_and_task("run-gate")
        self.x(
            "task",
            "--run-id",
            "run-gate",
            "--task-id",
            "task-docs",
            "--title",
            "Docs task",
            "--goal",
            "Implement docs marker.",
            "--allowed-scope",
            "README.md",
            "--forbidden-scope",
            "Everything else.",
            "--requirements",
            "Add a docs marker.",
            "--verification",
            "Inspect README.",
            "--done-evidence",
            "Changed README.",
        )
        self.x("materialize", "--run-id", "run-gate", "--scope", "gate")

        self.x("execution-plan", "--run-id", "run-gate", "--plan-id", "plan-missing", "--title", "Missing plan")
        missing_gate = self.x("architect-gate", "--run-id", "run-gate", check=False)
        self.assertNotEqual(missing_gate.returncode, 0)
        self.assertIn("missing Integration Order", missing_gate.stderr + missing_gate.stdout)
        self.x("execution-plan", "--run-id", "run-gate", "--plan-id", "plan-missing", "--status", "superseded")

        bad_lanes = "\n".join(
            [
                "| Lane ID | Task ID | Allowed Scope | Forbidden Scope | Worktree Scope | Verification | Done Evidence | Risk Level | Concurrent Group | Serial Only | Shared Files |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                "| lane-readme | task-llm |  | Everything else. | lane-readme | Inspect README. | README marker changed. | standard | none | no | none |",
                "| lane-docs | task-docs | README.md | Everything else. | lane-docs | Inspect README. | README marker changed. | standard | none | no | none |",
            ]
        )
        self.create_execution_plan(
            "run-gate",
            plan_id="plan-bad",
            lane_id="lane-readme",
            parallel_lanes=bad_lanes,
            integration_order="1. Integrate lane-readme.",
        )
        failed_lane = self.x(
            "lane-start",
            "--run-id",
            "run-gate",
            "--lane-id",
            "lane-readme",
            "--task-id",
            "task-llm",
            check=False,
        )
        self.assertNotEqual(failed_lane.returncode, 0)
        self.assertIn("Architect readiness gate must pass", failed_lane.stderr + failed_lane.stdout)
        failed_gate = self.x("architect-gate", "--run-id", "run-gate", check=False)
        self.assertNotEqual(failed_gate.returncode, 0)
        output = failed_gate.stderr + failed_gate.stdout
        self.assertIn("lane lane-readme missing allowed scope", output)
        self.assertIn("Integration Order does not include lane lane-docs", output)
        self.x("execution-plan", "--run-id", "run-gate", "--plan-id", "plan-bad", "--status", "superseded")

        good_lanes = bad_lanes.replace("| lane-readme | task-llm |  |", "| lane-readme | task-llm | README.md |")
        self.create_execution_plan(
            "run-gate",
            plan_id="plan-good",
            lane_id="lane-readme",
            parallel_lanes=good_lanes,
            integration_order="1. Integrate lane-readme.\n2. Integrate lane-docs.",
        )
        self.x("architect-gate", "--run-id", "run-gate")
        self.x("lane-start", "--run-id", "run-gate", "--lane-id", "lane-readme", "--task-id", "task-llm")
        self.x("lane-start", "--run-id", "run-gate", "--lane-id", "lane-docs", "--task-id", "task-docs")
        status = self.x("lane-status", "--run-id", "run-gate")
        self.assertIn("lane-readme; status=active", status.stdout)
        self.assertIn("lane-docs; status=active", status.stdout)

    def test_architect_gate_validates_lane_parallelism_schema(self) -> None:
        self.x("start", "--run-id", "run-lane-schema", "--goal", "Schema")
        self.accept_brief("run-lane-schema")
        self.create_contract_and_task("run-lane-schema")
        self.x("materialize", "--run-id", "run-lane-schema", "--scope", "lane-schema")

        missing_columns = "\n".join(
            [
                "| Lane ID | Task ID | Allowed Scope | Forbidden Scope | Worktree Scope | Verification | Done Evidence |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                "| lane-llm | task-llm | README.md | Everything else. | lane-llm | Inspect README. | README marker changed. |",
            ]
        )
        self.create_execution_plan("run-lane-schema", plan_id="plan-missing-risk", parallel_lanes=missing_columns)
        failed = self.x("architect-gate", "--run-id", "run-lane-schema", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Parallel Lanes missing column risk level", failed.stderr + failed.stdout)

        invalid_values = self.execution_plan_lane_table(risk_level="critical", serial_only="maybe")
        self.create_execution_plan("run-lane-schema", plan_id="plan-invalid-values", parallel_lanes=invalid_values)
        failed = self.x("architect-gate", "--run-id", "run-lane-schema", check=False)
        self.assertNotEqual(failed.returncode, 0)
        output = failed.stderr + failed.stdout
        self.assertIn("lane lane-llm risk level must be standard or high", output)
        self.assertIn("lane lane-llm serial only must be yes or no", output)

        serial_with_group = self.execution_plan_lane_table(concurrent_group="group-a", serial_only="yes")
        self.create_execution_plan("run-lane-schema", plan_id="plan-serial-group", parallel_lanes=serial_with_group)
        failed = self.x("architect-gate", "--run-id", "run-lane-schema", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("serial only yes cannot have concurrent group group-a", failed.stderr + failed.stdout)

        shared_standard = self.execution_plan_lane_table(shared_files="README.md")
        self.create_execution_plan("run-lane-schema", plan_id="plan-shared-standard", parallel_lanes=shared_standard)
        failed = self.x("architect-gate", "--run-id", "run-lane-schema", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("shared files require risk level high", failed.stderr + failed.stdout)

    def test_same_lane_id_can_be_reused_across_runs(self) -> None:
        self.prepare_materialized_run("run-one", "one")
        self.x("start", "--run-id", "run-two", "--goal", "Two")
        self.accept_brief("run-two")
        self.create_custom_contract_and_task("run-two", "contract-two", "task-two")
        self.x("materialize", "--run-id", "run-two", "--scope", "two")
        self.create_execution_plan("run-two", task_id="task-two")
        self.x("architect-gate", "--run-id", "run-two")
        self.x("lane-start", "--run-id", "run-two", "--lane-id", "lane-llm", "--task-id", "task-two")
        self.assertTrue(self.lane_file("run-one").exists())
        self.assertTrue(self.lane_file("run-two").exists())

    def test_attempt_loop_reaches_merge_ready_gate(self) -> None:
        self.x("start", "--run-id", "run-llm", "--goal", "LLM")
        self.accept_brief("run-llm")
        self.create_contract_and_task("run-llm")

        failed = self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "implementation",
            "--title",
            "Implement llm marker",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("materialized execution worktree", failed.stderr + failed.stdout)

        self.x("materialize", "--run-id", "run-llm", "--scope", "llm")
        failed = self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "implementation",
            "--title",
            "Implement llm marker",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("Architect Execution Plan", failed.stderr + failed.stdout)

        self.create_execution_plan_and_lane("run-llm", "llm")
        self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "implementation",
            "--title",
            "Implement llm marker",
        )
        attempt_text = self.attempt_file("task-llm-a1").read_text(encoding="utf-8")
        self.assertIn("Kind: implementation", attempt_text)
        self.x(
            "package",
            "--role",
            "engineer",
            "--run-id",
            "run-llm",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
            "--package-id",
            "engineer-llm",
        )
        package = self.x_home / "projects/repo/packages/engineer-llm.md"
        package_text = package.read_text(encoding="utf-8")
        self.assertIn("Execution Status: materialized", package_text)
        self.assertIn(str(self.lane_worktree("llm").resolve()), package_text)
        attempt_text = self.attempt_file("task-llm-a1").read_text(encoding="utf-8")
        self.assertIn("Input Package: engineer-llm", attempt_text)
        self.assertIn("Linked Lane: lane-llm", attempt_text)

        readme = self.lane_worktree("llm") / "README.md"
        readme.write_text("# repo\n\nllm marker\n", encoding="utf-8")
        self.x(
            "attempt-result",
            "--attempt-id",
            "task-llm-a1",
            "--changed-files",
            "README.md",
            "--summary",
            "Added llm marker.",
            "--verification",
            "Inspected README.",
            "--residual-risk",
            "None.",
        )
        self.x(
            "package",
            "--role",
            "reviewer",
            "--run-id",
            "run-llm",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
            "--package-id",
            "reviewer-llm",
        )
        review_package = self.x_home / "projects/repo/packages/reviewer-llm.md"
        review_text = review_package.read_text(encoding="utf-8")
        self.assertIn("llm marker", review_text)
        self.x(
            "review",
            "--run-id",
            "run-llm",
            "--title",
            "LLM review",
            "--attempt-id",
            "task-llm-a1",
            "--summary",
            "Looks ready.",
            "--recommendation",
            "ready",
            "--reviewed-diff",
            "README diff reviewed.",
            "--verification",
            "Verification is sufficient.",
        )
        gate = self.x("gate", "--mode", "merge-ready", "--run-id", "run-llm", check=False)
        self.assertNotEqual(gate.returncode, 0)
        self.assertIn("architect review", gate.stderr + gate.stdout)
        integrate = self.x("integrate", "--run-id", "run-llm", "--lane-id", "lane-llm", check=False)
        self.assertNotEqual(integrate.returncode, 0)
        self.assertIn("not merge-ok", integrate.stderr + integrate.stdout)
        self.approve_integrate_and_mark_green("run-llm", "task-llm-a1", mark_green=False)
        no_evidence = self.x(
            "execution-plan",
            "--run-id",
            "run-llm",
            "--plan-id",
            "plan-llm",
            "--final-verification-status",
            "green",
            check=False,
        )
        self.assertNotEqual(no_evidence.returncode, 0)
        self.assertIn("final verification evidence is required", no_evidence.stderr + no_evidence.stdout)
        self.x(
            "execution-plan",
            "--run-id",
            "run-llm",
            "--plan-id",
            "plan-llm",
            "--final-verification-status",
            "green",
            "--final-verification",
            "Final verification command: inspect integrated README. Result: expected marker present.",
        )
        self.x("gate", "--mode", "merge-ready", "--run-id", "run-llm")
        run_text = self.run_file("run-llm").read_text(encoding="utf-8")
        self.assertIn("Gate Status: passed", run_text)
        self.assertIn("Integrated Lanes\n\n- lane-llm", run_text)
        self.assertIn("llm marker", (self.repo / ".dev/llm/README.md").read_text(encoding="utf-8"))
        after_integrated = self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--lane-id",
            "lane-llm",
            "--kind",
            "implementation",
            "--title",
            "Should not start",
            check=False,
        )
        self.assertNotEqual(after_integrated.returncode, 0)
        self.assertIn("already integrated", after_integrated.stderr + after_integrated.stdout)
        task_text = self.task_file("task-llm").read_text(encoding="utf-8")
        self.assertIn("Status: done", task_text)
        self.assertIn("Latest Ready Attempt\n\ntask-llm-a1", task_text)

        self.x("start", "--run-id", "run-other", "--goal", "Other")
        resume = self.x("resume", cwd=self.repo / ".dev/llm")
        self.assertIn("# x Run: run-llm", resume.stdout)

    def test_high_risk_lane_requires_two_merge_ok_reviews_for_latest_attempt(self) -> None:
        self.x("start", "--run-id", "run-high-risk", "--goal", "High risk")
        self.accept_brief("run-high-risk")
        self.create_contract_and_task("run-high-risk")
        self.x("materialize", "--run-id", "run-high-risk", "--scope", "high-risk")
        self.create_execution_plan(
            "run-high-risk",
            parallel_lanes=self.execution_plan_lane_table(risk_level="high", shared_files="README.md"),
        )
        self.x("architect-gate", "--run-id", "run-high-risk")
        self.x("lane-start", "--run-id", "run-high-risk", "--lane-id", "lane-llm", "--task-id", "task-llm")
        status = self.x("lane-status", "--run-id", "run-high-risk")
        self.assertIn("risk=high", status.stdout)
        self.assertIn("shared=README.md", status.stdout)
        lane_text = self.lane_file("run-high-risk").read_text(encoding="utf-8")
        self.lane_file("run-high-risk").write_text(lane_text.replace("Risk Level: high", "Risk Level: standard"), encoding="utf-8")

        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--attempt-id", "task-llm-a1", "--title", "First marker")
        self.x("package", "--role", "engineer", "--run-id", "run-high-risk", "--task-id", "task-llm", "--attempt-id", "task-llm-a1")
        (self.lane_worktree("high-risk") / "README.md").write_text("# repo\n\nfirst marker\n", encoding="utf-8")
        self.x("attempt-result", "--attempt-id", "task-llm-a1", "--changed-files", "README.md", "--summary", "Added first marker.", "--verification", "Inspected README.", "--residual-risk", "None.")
        self.x("package", "--role", "reviewer", "--run-id", "run-high-risk", "--task-id", "task-llm", "--attempt-id", "task-llm-a1")
        self.x("review", "--run-id", "run-high-risk", "--attempt-id", "task-llm-a1", "--review-id", "review-high-a1", "--title", "Ready review", "--summary", "Ready.", "--recommendation", "ready", "--reviewed-diff", "README diff reviewed.", "--verification", "Verification sufficient.")
        self.record_architect_merge_ok("run-high-risk", "task-llm-a1", review_id="arch-high-a1-first")
        self.record_architect_merge_ok("run-high-risk", "task-llm-a1", review_id="arch-high-a1-second")

        self.x("architect-review", "--run-id", "run-high-risk", "--lane-id", "lane-llm", "--attempt-id", "task-llm-a1", "--review-id", "arch-high-fix-source", "--title", "Needs architect fix", "--summary", "Latest attempt needs a fix.", "--recommendation", "changes-requested", "--criteria", "Needs updated marker.", "--verification", "Reviewed lane evidence.", "--integration-risk", "Fix before integration.", "--blocking-findings", "- Marker must be updated.")
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "fix", "--source-architect-review-id", "arch-high-fix-source", "--attempt-id", "task-llm-a2", "--title", "Fix marker")
        self.x("package", "--role", "engineer", "--run-id", "run-high-risk", "--task-id", "task-llm", "--attempt-id", "task-llm-a2")
        (self.lane_worktree("high-risk") / "README.md").write_text("# repo\n\nsecond marker\n", encoding="utf-8")
        self.x("attempt-result", "--attempt-id", "task-llm-a2", "--changed-files", "README.md", "--summary", "Added second marker.", "--verification", "Inspected README.", "--residual-risk", "None.")
        self.x("package", "--role", "reviewer", "--run-id", "run-high-risk", "--task-id", "task-llm", "--attempt-id", "task-llm-a2")
        self.x("review", "--run-id", "run-high-risk", "--attempt-id", "task-llm-a2", "--review-id", "review-high-a2", "--title", "Ready review", "--summary", "Ready.", "--recommendation", "ready", "--reviewed-diff", "README diff reviewed.", "--verification", "Verification sufficient.")
        self.record_architect_merge_ok("run-high-risk", "task-llm-a2", review_id="arch-high-a2-first")

        failed = self.x("integrate", "--run-id", "run-high-risk", "--lane-id", "lane-llm", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("high-risk lane requires a second architect review pass for latest attempt (found 1 merge-ok review record)", failed.stderr + failed.stdout)
        gate = self.x("gate", "--mode", "merge-ready", "--run-id", "run-high-risk", check=False)
        self.assertNotEqual(gate.returncode, 0)
        self.assertIn("high-risk lane requires a second architect review pass for latest attempt", gate.stderr + gate.stdout)

        self.record_architect_merge_ok("run-high-risk", "task-llm-a2", review_id="arch-high-a2-second")
        self.x("integrate", "--run-id", "run-high-risk", "--lane-id", "lane-llm")
        self.x(
            "execution-plan",
            "--run-id",
            "run-high-risk",
            "--plan-id",
            "plan-llm",
            "--final-verification-status",
            "green",
            "--final-verification",
            "Final verification command: inspect integrated README. Result: expected marker present.",
        )
        self.x("gate", "--mode", "merge-ready", "--run-id", "run-high-risk")

    def test_full_fix_loop_clears_unresolved_review_and_passes_gate(self) -> None:
        self.prepare_materialized_run("run-fix", "fix")
        self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "implementation",
            "--attempt-id",
            "task-llm-a1",
            "--title",
            "Implement first marker",
        )
        self.x(
            "package",
            "--role",
            "engineer",
            "--run-id",
            "run-fix",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
            "--package-id",
            "engineer-first",
        )
        (self.lane_worktree("fix") / "README.md").write_text("# repo\n\nbroken marker\n", encoding="utf-8")
        self.x(
            "attempt-result",
            "--attempt-id",
            "task-llm-a1",
            "--changed-files",
            "README.md",
            "--summary",
            "Added the wrong marker.",
            "--verification",
            "Inspected README.",
            "--residual-risk",
            "Needs fix.",
        )
        self.x(
            "package",
            "--role",
            "reviewer",
            "--run-id",
            "run-fix",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
            "--package-id",
            "reviewer-first",
        )
        self.x(
            "review",
            "--run-id",
            "run-fix",
            "--attempt-id",
            "task-llm-a1",
            "--review-id",
            "review-first",
            "--title",
            "First review",
            "--summary",
            "Wrong marker.",
            "--recommendation",
            "changes-requested",
            "--blocking-findings",
            "- README marker does not satisfy the task.",
            "--reviewed-diff",
            "README diff reviewed.",
            "--verification",
            "Verification showed wrong marker.",
        )
        gate = self.x("gate", "--mode", "merge-ready", "--run-id", "run-fix", check=False)
        self.assertNotEqual(gate.returncode, 0)
        self.assertIn("unresolved review review-first", gate.stderr + gate.stdout)
        close = self.x("close", "--run-id", "run-fix", "--summary", "not ready", check=False)
        self.assertNotEqual(close.returncode, 0)
        self.assertIn("unresolved review review-first", close.stderr + close.stdout)

        missing_source = self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "fix",
            "--title",
            "Fix without source",
            check=False,
        )
        self.assertNotEqual(missing_source.returncode, 0)
        self.assertIn("fix attempt requires --source-review-id or --source-architect-review-id", missing_source.stderr + missing_source.stdout)

        self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "fix",
            "--source-review-id",
            "review-first",
            "--attempt-id",
            "task-llm-a2",
            "--title",
            "Fix marker",
        )
        fix_attempt_text = self.attempt_file("task-llm-a2").read_text(encoding="utf-8")
        self.assertIn("Source Review: review-first", fix_attempt_text)
        self.x(
            "package",
            "--role",
            "engineer",
            "--run-id",
            "run-fix",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a2",
            "--package-id",
            "engineer-fix",
        )
        engineer_fix_text = self.package_file("engineer-fix").read_text(encoding="utf-8")
        self.assertIn("Wrong marker.", engineer_fix_text)
        (self.lane_worktree("fix") / "README.md").write_text("# repo\n\nllm marker\n", encoding="utf-8")
        self.x(
            "attempt-result",
            "--attempt-id",
            "task-llm-a2",
            "--changed-files",
            "README.md",
            "--summary",
            "Replaced wrong marker with llm marker.",
            "--verification",
            "Inspected README.",
            "--residual-risk",
            "None.",
        )
        self.x(
            "package",
            "--role",
            "reviewer",
            "--run-id",
            "run-fix",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a2",
            "--package-id",
            "reviewer-fix",
        )
        self.x(
            "review",
            "--run-id",
            "run-fix",
            "--attempt-id",
            "task-llm-a2",
            "--review-id",
            "review-fix",
            "--title",
            "Fix review",
            "--summary",
            "Fix is ready.",
            "--recommendation",
            "ready",
            "--reviewed-diff",
            "README diff reviewed.",
            "--verification",
            "Verification is sufficient.",
        )
        self.assertIn("Status: addressed", self.review_file("review-first").read_text(encoding="utf-8"))
        run_text = self.run_file("run-fix").read_text(encoding="utf-8")
        unresolved = run_text.split("## Unresolved Reviews", 1)[1].split("\n## ", 1)[0]
        self.assertNotIn("review-first", unresolved)
        task_text = self.task_file("task-llm").read_text(encoding="utf-8")
        self.assertIn("Status: done", task_text)
        self.assertIn("Latest Ready Attempt\n\ntask-llm-a2", task_text)
        self.approve_integrate_and_mark_green("run-fix", "task-llm-a2", review_id="architect-fix")
        self.x("gate", "--mode", "merge-ready", "--run-id", "run-fix")
        self.assertIn("Gate Status: passed", self.run_file("run-fix").read_text(encoding="utf-8"))

    def test_architect_changes_requested_starts_architect_fix_loop(self) -> None:
        self.prepare_materialized_run("run-arch-fix", "arch-fix")
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
        self.x("package", "--role", "engineer", "--run-id", "run-arch-fix", "--task-id", "task-llm", "--attempt-id", "task-llm-a1")
        (self.lane_worktree("arch-fix") / "README.md").write_text("# repo\n\nllm marker\n", encoding="utf-8")
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
        self.x("package", "--role", "reviewer", "--run-id", "run-arch-fix", "--task-id", "task-llm", "--attempt-id", "task-llm-a1")
        self.x(
            "review",
            "--run-id",
            "run-arch-fix",
            "--attempt-id",
            "task-llm-a1",
            "--review-id",
            "review-arch-ready",
            "--title",
            "Ready review",
            "--summary",
            "Code review ready.",
            "--recommendation",
            "ready",
            "--reviewed-diff",
            "README diff reviewed.",
            "--verification",
            "Verification sufficient.",
        )
        self.x(
            "architect-review",
            "--run-id",
            "run-arch-fix",
            "--lane-id",
            "lane-llm",
            "--attempt-id",
            "task-llm-a1",
            "--review-id",
            "arch-change",
            "--title",
            "Architect changes",
            "--summary",
            "Architect scope issue.",
            "--recommendation",
            "changes-requested",
            "--criteria",
            "Must match the execution plan exactly.",
            "--blocking-findings",
            "- Integration evidence needs a small fix.",
            "--verification",
            "Reviewed lane evidence.",
            "--integration-risk",
            "Needs one fix before integration.",
        )
        self.assertIn("Status: architect-changes-requested", self.lane_file("run-arch-fix").read_text(encoding="utf-8"))
        self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "fix",
            "--source-architect-review-id",
            "arch-change",
            "--attempt-id",
            "task-llm-a2",
            "--title",
            "Fix architect finding",
        )
        self.x(
            "package",
            "--role",
            "engineer",
            "--run-id",
            "run-arch-fix",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a2",
            "--package-id",
            "engineer-arch-fix",
        )
        engineer_package = self.package_file("engineer-arch-fix").read_text(encoding="utf-8")
        self.assertIn("Architect scope issue.", engineer_package)
        self.assertIn("Source Architect Review", engineer_package)

    def test_reviewer_package_requires_attempt_evidence(self) -> None:
        self.prepare_materialized_run("run-evidence", "evidence")
        self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "implementation",
            "--title",
            "Implement marker",
        )
        failed = self.x(
            "package",
            "--role",
            "reviewer",
            "--run-id",
            "run-evidence",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("attempt has no result evidence", failed.stderr + failed.stdout)

    def test_ready_review_rejects_blocking_findings(self) -> None:
        self.prepare_materialized_run("run-blocking", "blocking")
        self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "implementation",
            "--title",
            "Implement marker",
        )
        self.x("package", "--role", "engineer", "--run-id", "run-blocking", "--task-id", "task-llm", "--attempt-id", "task-llm-a1")
        (self.lane_worktree("blocking") / "README.md").write_text("# repo\n\nllm marker\n", encoding="utf-8")
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
        failed = self.x(
            "review",
            "--run-id",
            "run-blocking",
            "--attempt-id",
            "task-llm-a1",
            "--title",
            "Blocking ready review",
            "--summary",
            "Claims ready.",
            "--recommendation",
            "ready",
            "--blocking-findings",
            "- Still broken.",
            "--reviewed-diff",
            "README diff reviewed.",
            "--verification",
            "Verification assessment.",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("ready review cannot include blocking findings", failed.stderr + failed.stdout)

    def test_three_non_ready_reviews_require_architect_loopback(self) -> None:
        self.prepare_materialized_run("run-loopback", "loopback")
        self.x(
            "attempt-start",
            "--task-id",
            "task-llm",
            "--kind",
            "implementation",
            "--title",
            "Implement marker",
        )
        self.x("package", "--role", "engineer", "--run-id", "run-loopback", "--task-id", "task-llm", "--attempt-id", "task-llm-a1")
        (self.lane_worktree("loopback") / "README.md").write_text("# repo\n\nwrong marker\n", encoding="utf-8")
        self.x(
            "attempt-result",
            "--attempt-id",
            "task-llm-a1",
            "--changed-files",
            "README.md",
            "--summary",
            "Added wrong marker.",
            "--verification",
            "Inspected README.",
            "--residual-risk",
            "Needs review.",
        )
        for index in range(1, 4):
            self.x(
                "review",
                "--run-id",
                "run-loopback",
                "--attempt-id",
                "task-llm-a1",
                "--review-id",
                f"review-loop-{index}",
                "--title",
                f"Loop review {index}",
                "--summary",
                "Still wrong.",
                "--recommendation",
                "changes-requested",
                "--loopback-target",
                "engineer",
                "--blocking-findings",
                "- Marker is wrong.",
                "--reviewed-diff",
                "README diff reviewed.",
                "--verification",
                "Verification insufficient.",
            )
        third_review = self.review_file("review-loop-3").read_text(encoding="utf-8")
        self.assertIn("Loopback Target: architect", third_review)
        run_text = self.run_file("run-loopback").read_text(encoding="utf-8")
        self.assertIn("Needs User: yes", run_text)
        self.assertIn("Loop back to architect/root", run_text)

    def test_multiple_active_runs_require_explicit_run_id_from_control_root(self) -> None:
        self.x("start", "--run-id", "run-one", "--goal", "One")
        self.x("start", "--run-id", "run-two", "--goal", "Two")
        failed = self.x("resume", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("multiple active x runs", failed.stderr + failed.stdout)

    def test_state_file_sort_key_handles_attempt_ten_after_two(self) -> None:
        sys.path.insert(0, str(ROOT / "skill/scripts"))
        from x_state_common import state_file_sort_key

        ordered = sorted(
            [Path("task-llm-a1.md"), Path("task-llm-a10.md"), Path("task-llm-a2.md")],
            key=state_file_sort_key,
        )
        self.assertEqual([path.name for path in ordered], ["task-llm-a1.md", "task-llm-a2.md", "task-llm-a10.md"])

if __name__ == "__main__":
    unittest.main()
