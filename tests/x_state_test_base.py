from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skill/scripts/x_state.py"


class XStateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.x_home = self.base / "x-home"
        self.repo.mkdir()
        self.git("init")
        self.git("config", "user.email", "x@example.com")
        self.git("config", "user.name", "x test")
        (self.repo / "PROJECT_CONSTRAINTS.md").write_text("# Test constraints\n", encoding="utf-8")
        (self.repo / "AGENTS.md").write_text("# Test agents\n", encoding="utf-8")
        (self.repo / "README.md").write_text("# repo\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "init")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=cwd or self.repo,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )

    def x(self, *args: str, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["X_HOME"] = str(self.x_home)
        env.setdefault("X_AUTO_NATIVE_REVIEW", "0")
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args],
            cwd=cwd or self.repo,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=check,
        )

    def run_file(self, run_id: str) -> Path:
        return self.x_home / "projects/repo/runs" / f"{run_id}.md"

    def attempt_file(self, attempt_id: str) -> Path:
        return self.x_home / "projects/repo/attempts" / f"{attempt_id}.md"

    def task_file(self, task_id: str) -> Path:
        return self.x_home / "projects/repo/tasks" / f"{task_id}.md"

    def review_file(self, review_id: str) -> Path:
        return self.x_home / "projects/repo/reviews" / f"{review_id}.md"

    def package_file(self, package_id: str) -> Path:
        return self.x_home / "projects/repo/packages" / f"{package_id}.md"

    def execution_plan_file(self, plan_id: str) -> Path:
        return self.x_home / "projects/repo/execution-plans" / f"{plan_id}.md"

    def lane_file(self, run_id: str, lane_id: str = "lane-llm") -> Path:
        return self.x_home / "projects/repo/lanes" / f"{run_id}--{lane_id}.md"

    def architect_review_file(self, review_id: str) -> Path:
        return self.x_home / "projects/repo/architect-reviews" / f"{review_id}.md"

    def lane_worktree(self, scope: str, lane_id: str = "lane-llm") -> Path:
        return self.repo / f".dev/{scope}-{lane_id}"

    def accept_brief(self, run_id: str) -> None:
        self.x(
            "brief",
            "--run-id",
            run_id,
            "--title",
            "LLM direction",
            "--architect-questions",
            "- None.",
            "--options",
            "- Build llm path.",
            "--recommendation",
            "Build the llm path.",
            "--risks",
            "- Scope drift.",
            "--root-decisions-needed",
            "- None.",
            "--accepted-direction",
            "Build a bounded llm path.",
            "--status",
            "accepted",
        )

    def create_contract_and_task(self, run_id: str) -> None:
        self.x(
            "contract",
            "--run-id",
            run_id,
            "--contract-id",
            "contract-llm",
            "--title",
            "LLM contract",
            "--goal",
            "Build llm path.",
            "--repo-intake",
            "Test repo.",
            "--codebase-findings",
            "No findings.",
            "--allowed-boundaries",
            "README only.",
            "--forbidden-boundaries",
            "No external systems.",
            "--reversible-path",
            "Revert README change.",
            "--verification",
            "Inspect README.",
            "--loopback",
            "Loop back on scope drift.",
        )
        self.x(
            "task",
            "--run-id",
            run_id,
            "--task-id",
            "task-llm",
            "--title",
            "LLM task",
            "--goal",
            "Implement README llm marker.",
            "--allowed-scope",
            "README.md",
            "--forbidden-scope",
            "Everything else.",
            "--requirements",
            "Add a marker.",
            "--verification",
            "Inspect README.",
            "--done-evidence",
            "Changed README.",
        )

    def create_custom_contract_and_task(self, run_id: str, contract_id: str, task_id: str) -> None:
        self.x(
            "contract",
            "--run-id",
            run_id,
            "--contract-id",
            contract_id,
            "--title",
            f"{task_id} contract",
            "--goal",
            f"Build {task_id}.",
            "--repo-intake",
            "Test repo.",
            "--codebase-findings",
            "No findings.",
            "--allowed-boundaries",
            "README only.",
            "--forbidden-boundaries",
            "No external systems.",
            "--reversible-path",
            "Revert README change.",
            "--verification",
            "Inspect README.",
            "--loopback",
            "Loop back on scope drift.",
        )
        self.x(
            "task",
            "--run-id",
            run_id,
            "--task-id",
            task_id,
            "--title",
            f"{task_id} task",
            "--goal",
            f"Implement {task_id} marker.",
            "--allowed-scope",
            "README.md",
            "--forbidden-scope",
            "Everything else.",
            "--requirements",
            "Add a marker.",
            "--verification",
            "Inspect README.",
            "--done-evidence",
            "Changed README.",
        )

    def prepare_materialized_run(self, run_id: str, scope: str) -> None:
        self.x("start", "--run-id", run_id, "--goal", "LLM")
        self.accept_brief(run_id)
        self.create_contract_and_task(run_id)
        self.x("materialize", "--run-id", run_id, "--scope", scope)
        self.create_execution_plan_and_lane(run_id, scope)

    def record_readme_attempt(self, attempt_id: str, marker: str) -> None:
        readme = self.lane_worktree(marker) / "README.md"
        readme.write_text(f"# repo\n\n{marker} marker\n", encoding="utf-8")
        self.x(
            "attempt-result",
            "--attempt-id",
            attempt_id,
            "--changed-files",
            "README.md",
            "--summary",
            f"Added {marker} marker.",
            "--verification",
            "Inspected README.",
            "--residual-risk",
            "None.",
        )

    def create_execution_plan(
        self,
        run_id: str,
        *,
        plan_id: str = "plan-llm",
        lane_id: str = "lane-llm",
        task_id: str = "task-llm",
        final_verification_status: str = "pending",
        parallel_lanes: str | None = None,
        integration_order: str | None = None,
        shared_contract_surfaces: str | None = None,
        acceptance_checkpoints: str | None = None,
    ) -> None:
        lanes = parallel_lanes or self.execution_plan_lane_table(lane_id=lane_id, task_id=task_id)
        self.x(
            "execution-plan",
            "--run-id",
            run_id,
            "--plan-id",
            plan_id,
            "--title",
            "LLM execution plan",
            "--objective",
            "Run bounded lane work for the README marker and integrate only after dual review.",
            "--parallel-lanes",
            lanes,
            "--dependency-graph",
            f"{lane_id} has no dependencies.",
            "--shared-contract-surfaces",
            shared_contract_surfaces
            if shared_contract_surfaces is not None
            else f"{lane_id}: README.md is the only shared contract surface; coordinate any README ownership changes before parallel lane work.",
            "--acceptance-checkpoints",
            acceptance_checkpoints
            if acceptance_checkpoints is not None
            else "Pre-integration checkpoint: confirm reviewer ready and architect merge criteria before integration.\nFinal checkpoint: inspect integrated README and lane state before merge-ready gate.",
            "--lane-ownership",
            f"{lane_id}: owns {task_id}; run implementation/fix attempts, code review, architect review, then integration.",
            "--allowed-scope",
            "README.md through the lane task only.",
            "--forbidden-scope",
            "No external systems, repo metadata, or unrelated files.",
            "--expected-artifacts",
            "Attempt evidence, reviewer findings, architect review, integrated README diff.",
            "--verification-matrix",
            "Lane verification: inspect README. Final verification: inspect integrated README and confirm lane state.",
            "--reviewer-criteria",
            "Reviewer must confirm task scope, README diff, required verification, and no blockers.",
            "--architect-merge-criteria",
            "Architect must confirm lane matches plan, has ready code review, and has no integration conflict.",
            "--integration-order",
            integration_order or f"1. Integrate {lane_id} after reviewer ready and architect merge-ok.",
            "--known-risks",
            "Integration conflict blocks lane and loops to architect.",
            "--loopback-triggers",
            "Test failure starts a fix attempt; contract ambiguity stops and loops to architect/root.",
            "--blocked-recovery",
            "On blocked review, create a fresh fix attempt from the source review; on integration conflict, stop and replan.",
            "--root-decisions",
            "No root decision is required unless the contract direction changes or final merge is requested.",
            "--final-verification-status",
            final_verification_status,
        )

    def execution_plan_lane_table(
        self,
        *,
        lane_id: str = "lane-llm",
        task_id: str = "task-llm",
        risk_level: str = "standard",
        concurrent_group: str = "none",
        serial_only: str = "no",
        shared_files: str = "none",
    ) -> str:
        return "\n".join(
            [
                "| Lane ID | Task ID | Allowed Scope | Forbidden Scope | Worktree Scope | Verification | Done Evidence | Risk Level | Concurrent Group | Serial Only | Shared Files |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                f"| {lane_id} | {task_id} | README.md | Everything else. | {lane_id} | Inspect README after the lane patch. | README marker changed. | {risk_level} | {concurrent_group} | {serial_only} | {shared_files} |",
            ]
        )

    def create_execution_plan_and_lane(self, run_id: str, scope: str, lane_id: str = "lane-llm") -> None:
        self.create_execution_plan(run_id, lane_id=lane_id)
        self.x("architect-gate", "--run-id", run_id)
        self.x("lane-start", "--run-id", run_id, "--lane-id", lane_id, "--task-id", "task-llm")

    def approve_integrate_and_mark_green(
        self,
        run_id: str,
        attempt_id: str,
        *,
        lane_id: str = "lane-llm",
        review_id: str = "architect-llm",
        plan_id: str = "plan-llm",
        mark_green: bool = True,
    ) -> None:
        self.record_architect_merge_ok(run_id, attempt_id, lane_id=lane_id, review_id=review_id)
        self.x("integrate", "--run-id", run_id, "--lane-id", lane_id)
        if not mark_green:
            return
        self.x(
            "execution-plan",
            "--run-id",
            run_id,
            "--plan-id",
            plan_id,
            "--final-verification-status",
            "green",
            "--final-verification",
            "Final verification command: inspect integrated README. Result: expected marker present.",
        )

    def record_architect_merge_ok(
        self,
        run_id: str,
        attempt_id: str,
        *,
        lane_id: str = "lane-llm",
        review_id: str = "architect-llm",
    ) -> None:
        self.x(
            "architect-review",
            "--run-id",
            run_id,
            "--lane-id",
            lane_id,
            "--attempt-id",
            attempt_id,
            "--review-id",
            review_id,
            "--title",
            "Architect integration review",
            "--summary",
            "Lane is mergeable.",
            "--recommendation",
            "merge-ok",
            "--criteria",
            "Matches execution plan and ready code review.",
            "--verification",
            "Reviewed lane evidence.",
            "--integration-risk",
            "No conflict expected.",
        )
