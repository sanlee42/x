from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from tests.x_state_test_base import XStateTestCase


class XStateAuditTests(XStateTestCase):
    def create_package(self, run_id: str, package_id: str, role: str = "architect") -> Path:
        self.x("package", "--role", role, "--run-id", run_id, "--title", package_id, "--package-id", package_id)
        return self.package_file(package_id)

    def create_codex_state(self, rows: list[tuple[str, str, str, int]]) -> Path:
        path = self.base / "codex-state.sqlite"
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "create table threads (id text, title text, first_user_message text, tokens_used integer)"
            )
            connection.executemany(
                "insert into threads (id, title, first_user_message, tokens_used) values (?, ?, ?, ?)",
                rows,
            )
            connection.commit()
        finally:
            connection.close()
        return path

    def audit_json(self, run_id: str, codex_state: Path) -> dict:
        result = self.x("audit", "--run-id", run_id, "--json", "--codex-state", str(codex_state))
        return json.loads(result.stdout)

    def test_audit_succeeds_without_codex_sqlite(self) -> None:
        self.x("start", "--run-id", "run-audit-missing", "--goal", "Audit missing sqlite")
        self.create_package("run-audit-missing", "pkg-audit")

        result = self.x(
            "audit",
            "--run-id",
            "run-audit-missing",
            "--codex-state",
            str(self.base / "missing.sqlite"),
        )

        self.assertIn("# x Run Audit: run-audit-missing", result.stdout)
        self.assertIn("Available: no", result.stdout)
        self.assertIn("Reason: Codex sqlite unavailable", result.stdout)

    def test_audit_matches_package_path_and_aggregates_tokens_by_role(self) -> None:
        self.x("start", "--run-id", "run-audit-tokens", "--goal", "Audit tokens")
        package = self.create_package("run-audit-tokens", "pkg-architect")
        codex_state = self.create_codex_state(
            [
                ("thread-1", "Architect package", f"Use package {package}", 123),
                ("thread-ignored", "Unrelated", "No package here", 999),
            ]
        )

        audit = self.audit_json("run-audit-tokens", codex_state)

        self.assertTrue(audit["tokens"]["available"])
        self.assertEqual(audit["tokens"]["total_tokens"], 123)
        self.assertEqual(audit["tokens"]["tokens_by_role"], {"architect": 123})
        self.assertEqual(audit["tokens"]["matched_packages"], 1)
        self.assertEqual(audit["tokens"]["unmatched_packages"], 0)
        self.assertEqual(audit["tokens"]["ambiguous_packages"], 0)
        self.assertEqual(audit["tokens"]["packages"][0]["thread_id"], "thread-1")

    def test_audit_package_id_boundaries_avoid_prefix_matches(self) -> None:
        self.x("start", "--run-id", "run-audit-prefix", "--goal", "Audit prefix")
        self.create_package("run-audit-prefix", "pkg-foo")
        self.create_package("run-audit-prefix", "pkg-foo-extra")
        codex_state = self.create_codex_state(
            [
                ("thread-extra", "Review /packages/pkg-foo-extra.md", "Use pkg-foo-extra only.", 50),
            ]
        )

        audit = self.audit_json("run-audit-prefix", codex_state)
        packages = {item["package_id"]: item for item in audit["tokens"]["packages"]}

        self.assertEqual(packages["pkg-foo"]["match_status"], "unmatched")
        self.assertEqual(packages["pkg-foo-extra"]["match_status"], "matched")
        self.assertEqual(audit["tokens"]["total_tokens"], 50)

    def test_audit_excludes_ambiguous_and_missing_package_tokens(self) -> None:
        self.x("start", "--run-id", "run-audit-unresolved", "--goal", "Audit unresolved")
        self.create_package("run-audit-unresolved", "pkg-amb")
        self.create_package("run-audit-unresolved", "pkg-missing")
        codex_state = self.create_codex_state(
            [
                ("thread-amb-1", "pkg-amb", "Use pkg-amb.", 10),
                ("thread-amb-2", "pkg-amb follow-up", "Use pkg-amb.", 20),
            ]
        )

        audit = self.audit_json("run-audit-unresolved", codex_state)
        packages = {item["package_id"]: item for item in audit["tokens"]["packages"]}

        self.assertEqual(audit["tokens"]["total_tokens"], 0)
        self.assertEqual(audit["tokens"]["matched_packages"], 0)
        self.assertEqual(audit["tokens"]["ambiguous_packages"], 1)
        self.assertEqual(audit["tokens"]["unmatched_packages"], 1)
        self.assertEqual(packages["pkg-amb"]["match_status"], "ambiguous")
        self.assertEqual(packages["pkg-missing"]["match_status"], "unmatched")
        self.assertEqual({item["package_id"] for item in audit["tokens"]["unresolved"]}, {"pkg-amb", "pkg-missing"})

    def test_audit_json_shape_and_write_markdown(self) -> None:
        self.x("start", "--run-id", "run-audit-write", "--goal", "Audit write")
        self.create_package("run-audit-write", "pkg-write")
        codex_state = self.create_codex_state([])

        result = self.x(
            "audit",
            "--run-id",
            "run-audit-write",
            "--write",
            "--json",
            "--codex-state",
            str(codex_state),
        )
        audit = json.loads(result.stdout)
        audit_file = self.x_home / "projects/repo/audits/run-audit-write.md"

        self.assertEqual(audit["run"]["run_id"], "run-audit-write")
        self.assertIn("engineering_scale", audit)
        self.assertIn("flow", audit)
        self.assertIn("tokens", audit)
        self.assertEqual(audit["written_path"], str(audit_file))
        self.assertTrue(audit_file.exists())
        self.assertIn("# x Run Audit: run-audit-write", audit_file.read_text(encoding="utf-8"))
