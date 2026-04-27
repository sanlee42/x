from __future__ import annotations

import os
import unittest

from tests.x_state_test_base import ROOT, XStateTestCase


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
        self.x("package", "--role", "reviewer", "--reviewer-backend", "package", "--run-id", run_id, "--task-id", "task-llm", "--attempt-id", "task-llm-a1", "--package-id", f"reviewer-{run_id}")
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

    def record_attempt_for_native_review(self, run_id: str, scope: str, marker: str) -> None:
        self.prepare_materialized_run(run_id, scope)
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "Implement marker")
        readme = self.lane_worktree(scope) / "README.md"
        readme.write_text(f"# repo\n\n{marker}\n", encoding="utf-8")
        self.x(
            "attempt-result",
            "--attempt-id",
            "task-llm-a1",
            "--changed-files",
            "README.md",
            "--summary",
            "Updated README.",
            "--verification",
            "Inspected README.",
            "--residual-risk",
            "None.",
        )

    def install_fake_codex(self, output: str):
        bin_dir = self.base / "fake-bin"
        log_dir = self.base / "fake-codex-log"
        bin_dir.mkdir()
        log_dir.mkdir()
        executable = bin_dir / "codex"
        executable.write_text(
            """#!/usr/bin/env python3
import os
import pathlib
import sys

log_dir = pathlib.Path(os.environ["FAKE_CODEX_LOG_DIR"])
log_dir.mkdir(parents=True, exist_ok=True)
(log_dir / "argv.txt").write_text("\\n".join(sys.argv), encoding="utf-8")
(log_dir / "cwd.txt").write_text(os.getcwd(), encoding="utf-8")
(log_dir / "stdin.txt").write_text(sys.stdin.read(), encoding="utf-8")
print(os.environ.get("FAKE_CODEX_OUTPUT", ""))
""",
            encoding="utf-8",
        )
        executable.chmod(0o755)
        saved_env = {key: os.environ.get(key) for key in ("PATH", "FAKE_CODEX_LOG_DIR", "FAKE_CODEX_OUTPUT")}

        def restore_env() -> None:
            for key, value in saved_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

        self.addCleanup(restore_env)
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
        os.environ["FAKE_CODEX_LOG_DIR"] = str(log_dir)
        os.environ["FAKE_CODEX_OUTPUT"] = output
        return log_dir

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
                "| Lane ID | Task ID | Allowed Scope | Forbidden Scope | Worktree Scope | Verification | Done Evidence | Risk Level | Concurrent Group | Serial Only | Shared Files |",
                "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
                "| lane-a | task-llm | README.md | Everything else. | lane-a | Inspect README. | README marker changed. | standard | none | no | none |",
                "| lane-b | task-llm | README.md | Everything else. | lane-b | Inspect README. | README marker changed. | standard | none | no | none |",
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
        self.assertIn("Diff Reference", reviewer_package)
        self.assertIn("This supplemental package intentionally does not inline the full diff", reviewer_package)
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
        failed = self.x("package", "--role", "reviewer", "--reviewer-backend", "package", "--run-id", "run-untracked", "--task-id", "task-llm", "--attempt-id", "task-llm-a1", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("reviewer package cannot capture untracked lane files: new-file.txt", failed.stderr + failed.stdout)

    def test_codex_native_reviewer_invokes_codex_and_records_ready_review(self) -> None:
        log_dir = self.install_fake_codex(
            "recommendation: ready\n\nblocking findings:\n- None.\n\nverification assessment:\n- Looks sufficient."
        )
        self.record_attempt_for_native_review("run-native-ready", "native-ready", "NATIVE_DIFF_SENTINEL")
        lane_tree = self.lane_worktree("native-ready")

        self.x(
            "package",
            "--role",
            "reviewer",
            "--run-id",
            "run-native-ready",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
        )

        argv = (log_dir / "argv.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(argv[1:], ["review", "--uncommitted"])
        self.assertEqual((log_dir / "cwd.txt").read_text(encoding="utf-8"), str(lane_tree))
        stdin = (log_dir / "stdin.txt").read_text(encoding="utf-8")
        self.assertEqual("", stdin)
        self.assertNotIn("NATIVE_DIFF_SENTINEL", stdin)

        reviews = sorted((self.x_home / "projects/repo/reviews").glob("*.md"))
        self.assertEqual(len(reviews), 1)
        review_text = reviews[0].read_text(encoding="utf-8")
        self.assertIn("Recommendation: ready", review_text)
        self.assertIn("Severity: none", review_text)
        self.assertIn("Bounded Fix: no", review_text)
        self.assertIn("Escalation Reason: none", review_text)
        self.assertIn("Linked Run: run-native-ready", review_text)
        self.assertIn("Linked Attempt: task-llm-a1", review_text)
        self.assertIn("recommendation: ready", review_text)
        self.assertIn("codex review --uncommitted", review_text)
        self.assertIn("x context was retained in state", review_text)

    def test_codex_native_reviewer_defaults_to_blocked_without_explicit_recommendation(self) -> None:
        self.install_fake_codex("Looks okay, but this output does not have the required structured recommendation line.")
        self.record_attempt_for_native_review("run-native-blocked", "native-blocked", "blocked sentinel")

        self.x(
            "package",
            "--role",
            "reviewer",
            "--reviewer-backend",
            "codex-native",
            "--run-id",
            "run-native-blocked",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
        )

        reviews = sorted((self.x_home / "projects/repo/reviews").glob("*.md"))
        self.assertEqual(len(reviews), 1)
        review_text = reviews[0].read_text(encoding="utf-8")
        self.assertIn("Recommendation: blocked", review_text)
        self.assertIn("Severity: none", review_text)
        self.assertIn("Bounded Fix: no", review_text)
        self.assertIn("Escalation Reason: unstructured-native-output", review_text)
        self.assertIn("not structured enough", review_text)
        self.assertIn("Looks okay", review_text)
        run_text = self.run_file("run-native-blocked").read_text(encoding="utf-8")
        self.assertIn("Proceed according to the normalized x Review gate", run_text)

    def test_codex_native_reviewer_invokes_codex_with_untracked_files(self) -> None:
        log_dir = self.install_fake_codex("recommendation: ready")
        self.prepare_materialized_run("run-native-untracked", "native-untracked")
        self.x("attempt-start", "--task-id", "task-llm", "--kind", "implementation", "--title", "Add file")
        (self.lane_worktree("native-untracked") / "new-file.txt").write_text("new\n", encoding="utf-8")
        self.x("attempt-result", "--attempt-id", "task-llm-a1", "--changed-files", "new-file.txt", "--summary", "Added new file.", "--verification", "Inspected file.", "--residual-risk", "None.")

        self.x(
            "package",
            "--role",
            "reviewer",
            "--reviewer-backend",
            "codex-native",
            "--run-id",
            "run-native-untracked",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
        )

        argv = (log_dir / "argv.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(argv[1:], ["review", "--uncommitted"])
        review_text = next((self.x_home / "projects/repo/reviews").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("Recommendation: ready", review_text)

    def test_native_p2_blocks_without_auto_fix(self) -> None:
        self.install_fake_codex("[P2] README marker is wrong.")
        self.record_attempt_for_native_review("run-native-p2", "native-p2", "wrong marker")

        self.x(
            "package",
            "--role",
            "reviewer",
            "--run-id",
            "run-native-p2",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
        )

        review_text = next((self.x_home / "projects/repo/reviews").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("Recommendation: changes-requested", review_text)
        self.assertIn("Severity: p2", review_text)
        self.assertIn("Bounded Fix: no", review_text)
        self.assertFalse(self.attempt_file("task-llm-a2").exists())

    def test_native_bounded_p3_starts_fix_attempt(self) -> None:
        self.install_fake_codex(
            "recommendation: changes-requested\n"
            "severity: p3\n"
            "bounded fix: yes\n"
            "escalation reason: none\n\n"
            "blocking findings:\n- README marker typo is narrowly fixable."
        )
        self.record_attempt_for_native_review("run-native-bounded", "native-bounded", "typo marker")

        self.x(
            "package",
            "--role",
            "reviewer",
            "--run-id",
            "run-native-bounded",
            "--task-id",
            "task-llm",
            "--attempt-id",
            "task-llm-a1",
        )

        review_text = next((self.x_home / "projects/repo/reviews").glob("*.md")).read_text(encoding="utf-8")
        self.assertIn("Recommendation: changes-requested", review_text)
        self.assertIn("Severity: p3", review_text)
        self.assertIn("Bounded Fix: yes", review_text)
        fix_text = self.attempt_file("task-llm-a2").read_text(encoding="utf-8")
        self.assertIn("Kind: fix", fix_text)
        self.assertIn("Source Review:", fix_text)

    def test_review_severity_order_and_auto_fix_cutoff(self) -> None:
        import sys

        sys.path.insert(0, str(ROOT / "skill/scripts"))
        from x_state_reviews import (
            highest_review_severity,
            normalize_native_review_output,
            review_severity_allows_auto_fix,
        )

        self.assertEqual(highest_review_severity(["none", "p3", "p2", "p1", "p0"]), "p0")
        self.assertTrue(review_severity_allows_auto_fix("p3"))
        self.assertTrue(review_severity_allows_auto_fix("none"))
        self.assertFalse(review_severity_allows_auto_fix("p2"))
        normalized = normalize_native_review_output("blocking findings:\n- Something is wrong.")
        self.assertEqual(normalized["recommendation"], "blocked")
        self.assertEqual(normalized["escalation_reason"], "unstructured-native-output")

    def test_attempt_result_does_not_run_native_reviewer_inline_by_default(self) -> None:
        self.record_attempt_for_native_review("run-native-not-inline", "native-not-inline", "marker")

        self.assertEqual(list((self.x_home / "projects/repo/reviews").glob("*.md")), [])
        self.assertEqual(list((self.x_home / "projects/repo/packages").glob("*.md")), [])
        run_text = self.run_file("run-native-not-inline").read_text(encoding="utf-8")
        self.assertIn("Spawn a reviewer subagent to run native reviewer", run_text)

    def test_skill_documents_main_role_boundaries(self) -> None:
        skill_text = (ROOT / "skill/SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Main must not act as architect, engineer, or reviewer", skill_text)
        self.assertIn("architecture/design judgment", skill_text)
        self.assertIn("Architect integration review should run in an architect role/subagent", skill_text)


if __name__ == "__main__":
    unittest.main()
