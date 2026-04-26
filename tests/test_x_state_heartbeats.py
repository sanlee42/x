from __future__ import annotations

import unittest

from tests.x_state_test_base import XStateTestCase


class XStateHeartbeatTests(XStateTestCase):
    def record_heartbeat(
        self,
        run_id: str,
        *,
        status: str = "active",
        activity: str = "Editing README marker.",
        blocker: str = "None.",
        next_action: str = "Run README verification.",
    ) -> None:
        self.x(
            "lane-update",
            "--run-id",
            run_id,
            "--lane-id",
            "lane-llm",
            "--actor",
            "engineer",
            "--session",
            "eng-session-1",
            "--heartbeat-status",
            status,
            "--activity",
            activity,
            "--blocker",
            blocker,
            "--next-action",
            next_action,
        )

    def remove_section(self, text: str, name: str) -> str:
        heading = f"## {name}"
        start = text.find(heading)
        if start < 0:
            return text
        next_heading = text.find("\n## ", start + len(heading))
        end = len(text) if next_heading < 0 else next_heading
        return text[:start].rstrip() + "\n\n" + text[end:].lstrip()

    def test_lane_update_writes_heartbeat_fields_and_sections(self) -> None:
        self.prepare_materialized_run("run-heartbeat-write", "heartbeat-write")
        self.record_heartbeat("run-heartbeat-write")

        lane = self.lane_file("run-heartbeat-write").read_text(encoding="utf-8")
        self.assertRegex(lane, r"Heartbeat At: \d{4}-\d{2}-\d{2}T")
        self.assertIn("Heartbeat Actor: engineer", lane)
        self.assertIn("Heartbeat Session: eng-session-1", lane)
        self.assertIn("Heartbeat Status: active", lane)
        self.assertIn("## Current Activity\n\nEditing README marker.", lane)
        self.assertIn("## Current Blocker\n\nNone.", lane)
        self.assertIn("## Lane Next Action\n\nRun README verification.", lane)

    def test_lane_status_surfaces_heartbeat_summary_and_attention(self) -> None:
        self.prepare_materialized_run("run-heartbeat-status", "heartbeat-status")
        self.record_heartbeat(
            "run-heartbeat-status",
            activity="Implementing parser guard.",
            blocker="None.",
            next_action="Run unit tests.",
        )

        status = self.x("lane-status", "--run-id", "run-heartbeat-status")
        self.assertIn("lane-llm; status=active", status.stdout)
        self.assertIn("heartbeat=active", status.stdout)
        self.assertIn("actor=engineer", status.stdout)
        self.assertIn("session=eng-session-1", status.stdout)
        self.assertIn("activity=Implementing parser guard.", status.stdout)
        self.assertIn("blocker=none", status.stdout)
        self.assertIn("next=Run unit tests.", status.stdout)
        self.assertIn("attention=none", status.stdout)

    def test_status_includes_computed_lane_heartbeats_section(self) -> None:
        self.prepare_materialized_run("run-heartbeat-status-section", "heartbeat-status-section")
        self.record_heartbeat(
            "run-heartbeat-status-section",
            activity="Preparing reviewer handoff.",
            next_action="Generate reviewer package.",
        )

        status = self.x("status", "--run-id", "run-heartbeat-status-section")
        self.assertIn("## Lane Heartbeats", status.stdout)
        self.assertIn("activity=Preparing reviewer handoff.", status.stdout)
        self.assertIn("next=Generate reviewer package.", status.stdout)
        self.assertIn("attention=none", status.stdout)

    def test_architect_package_includes_heartbeat_and_attention(self) -> None:
        self.prepare_materialized_run("run-heartbeat-package", "heartbeat-package")
        self.record_heartbeat(
            "run-heartbeat-package",
            status="reviewing",
            activity="Reviewer is checking diff scope.",
            next_action="Record review findings.",
        )

        self.x(
            "package",
            "--role",
            "architect",
            "--run-id",
            "run-heartbeat-package",
            "--title",
            "Architect heartbeat board",
            "--package-id",
            "architect-heartbeat-board",
        )
        package = self.package_file("architect-heartbeat-board").read_text(encoding="utf-8")
        self.assertIn("Architect Control Board:", package)
        self.assertIn("heartbeat=reviewing", package)
        self.assertIn("activity=Reviewer is checking diff scope.", package)
        self.assertIn("next=Record review findings.", package)
        self.assertIn("attention=none", package)

    def test_blocker_heartbeat_does_not_mutate_lane_status(self) -> None:
        self.prepare_materialized_run("run-heartbeat-blocker", "heartbeat-blocker")
        self.record_heartbeat(
            "run-heartbeat-blocker",
            status="blocked",
            activity="Waiting on contract clarification.",
            blocker="Contract does not define retry behavior.",
            next_action="Ask architect for directive.",
        )

        lane = self.lane_file("run-heartbeat-blocker").read_text(encoding="utf-8")
        self.assertIn("Status: active", lane)
        self.assertIn("Heartbeat Status: blocked", lane)
        lane_status = self.x("lane-status", "--run-id", "run-heartbeat-blocker")
        self.assertIn("blocker=Contract does not define retry behavior.", lane_status.stdout)
        self.assertIn("attention=blocker", lane_status.stdout)

    def test_missing_heartbeat_has_attention_label(self) -> None:
        self.prepare_materialized_run("run-heartbeat-missing", "heartbeat-missing")
        missing = self.x("lane-status", "--run-id", "run-heartbeat-missing")
        self.assertIn("heartbeat=none", missing.stdout)
        self.assertIn("attention=no-heartbeat", missing.stdout)

    def test_stale_heartbeat_has_attention_label(self) -> None:
        self.prepare_materialized_run("run-heartbeat-stale", "heartbeat-stale")
        self.record_heartbeat("run-heartbeat-stale")
        lane_path = self.lane_file("run-heartbeat-stale")
        lane = lane_path.read_text(encoding="utf-8")
        lane = lane.replace("Heartbeat At: " + lane.split("Heartbeat At: ", 1)[1].splitlines()[0], "Heartbeat At: 2000-01-01T00:00:00")
        lane_path.write_text(lane, encoding="utf-8")

        stale = self.x("lane-status", "--run-id", "run-heartbeat-stale")
        self.assertIn("heartbeat=active", stale.stdout)
        self.assertIn("attention=stale", stale.stdout)

    def test_old_lane_without_heartbeat_fields_is_backward_compatible(self) -> None:
        self.prepare_materialized_run("run-heartbeat-old", "heartbeat-old")
        lane_path = self.lane_file("run-heartbeat-old")
        lane = lane_path.read_text(encoding="utf-8")
        kept = [
            line
            for line in lane.splitlines()
            if not line.startswith(("Heartbeat At:", "Heartbeat Actor:", "Heartbeat Session:", "Heartbeat Status:"))
        ]
        lane = "\n".join(kept) + "\n"
        for section in ("Current Activity", "Current Blocker", "Lane Next Action"):
            lane = self.remove_section(lane, section)
        lane_path.write_text(lane, encoding="utf-8")

        status = self.x("lane-status", "--run-id", "run-heartbeat-old")
        self.assertIn("lane-llm; status=active", status.stdout)
        self.assertIn("heartbeat=none", status.stdout)
        self.assertIn("activity=none", status.stdout)
        self.assertIn("attention=no-heartbeat", status.stdout)


if __name__ == "__main__":
    unittest.main()
