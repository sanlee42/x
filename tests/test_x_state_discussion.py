from __future__ import annotations

from tests.x_state_test_base import XStateTestCase


class XStateDiscussionTests(XStateTestCase):
    def discussion_file(self, discussion_id: str):
        return self.x_home / "projects/repo/discussions" / f"{discussion_id}.md"

    def role_brief_file(self, brief_id: str):
        return self.x_home / "projects/repo/role-briefs" / f"{brief_id}.md"

    def architect_intake_file(self, intake_id: str):
        return self.x_home / "projects/repo/architect-intakes" / f"{intake_id}.md"

    def decision_file(self, decision_id: str):
        return self.x_home / "projects/repo/decisions" / f"{decision_id}.md"

    def test_role_registry_lists_defaults_and_allows_runtime_roles(self) -> None:
        roles = self.x("role-list").stdout
        self.assertIn("strategy (default)", roles)
        self.assertIn("technical (default)", roles)
        self.assertIn("product (default)", roles)
        self.assertIn("product-acceptance -> product", roles)

        product = self.x("role-show", "product").stdout
        self.assertIn("user path", product)
        self.assertIn("Acceptance/QA", product)

        self.x(
            "role-set",
            "ops",
            "--body",
            "# x Role Card: ops\n\nRole: ops\n\n## Responsibilities\n\nKeep launch operations bounded.\n",
        )
        self.assertIn("ops (runtime)", self.x("role-list").stdout)
        self.assertIn("launch operations", self.x("role-show", "ops").stdout)

        self.x("role-set", "technical", "--body", "# x Role Card: technical\n\nRole: technical\n\nModified technical card.\n")
        self.assertIn("technical (runtime override)", self.x("role-list").stdout)
        self.assertIn("Modified technical card", self.x("role-show", "technical").stdout)

        failed = self.x(
            "interaction-start",
            "--mode",
            "with",
            "--title",
            "Unknown role",
            "--agenda",
            "Should fail.",
            "--participants",
            "unknown",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("unknown role: unknown", failed.stderr + failed.stdout)

        failed = self.x("role-set", "engineer", "--body", "# x Role Card: engineer\n", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("reserved role name: engineer", failed.stderr + failed.stdout)

        self.assertNotIn("- engineer ", self.x("role-list").stdout)

    def test_interaction_alias_supports_single_custom_role_loop(self) -> None:
        self.x(
            "role-set",
            "ops",
            "--body",
            "# x Role Card: ops\n\nRole: ops\n\n## Responsibilities\n\nChallenge operational readiness.\n",
        )
        self.x(
            "interaction-start",
            "--mode",
            "with",
            "--title",
            "Ops readiness",
            "--agenda",
            "Can this proposal operate cleanly?",
            "--participants",
            "ops",
            "--interaction-id",
            "inter-ops",
        )
        self.x(
            "interaction-turn",
            "--interaction-id",
            "inter-ops",
            "--actor",
            "root",
            "--turn-kind",
            "statement",
            "--body",
            "I think this can launch with a manual runbook.",
        )
        self.x(
            "interaction-turn",
            "--interaction-id",
            "inter-ops",
            "--actor",
            "ops",
            "--turn-kind",
            "response",
            "--body",
            "Manual launch is acceptable if rollback is explicit.",
        )
        self.x(
            "interaction-summarize",
            "--interaction-id",
            "inter-ops",
            "--agreements",
            "Manual launch can be v1.",
            "--conflicts",
            "Rollback detail is unresolved.",
            "--rejected-options",
            "No automated launch system.",
            "--root-decisions-needed",
            "Root must accept manual rollback.",
            "--recommended-direction",
            "Proceed with a manual launch runbook.",
            "--architect-intake-draft",
            "Architect should keep operations as a non-code constraint.",
            "--strongest-objection",
            "Manual launch may hide repeatability problems.",
            "--weakest-assumption",
            "The first launch is low volume.",
            "--evidence-to-change",
            "A dry run shows manual steps are unreliable.",
        )
        interaction = self.discussion_file("inter-ops").read_text(encoding="utf-8")
        self.assertIn("Status: synthesized", interaction)
        self.assertIn("ops / response", interaction)
        self.assertIn("Proceed with a manual launch runbook.", interaction)

    def test_interaction_turns_record_audience_and_print_transcript(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "Visible joint direction",
            "--agenda",
            "Keep role conversation visible.",
            "--participants",
            "product",
            "technical",
            "--interaction-id",
            "inter-visible",
        )
        first = self.x(
            "interaction-turn",
            "--interaction-id",
            "inter-visible",
            "--actor",
            "root",
            "--to",
            "product",
            "--turn-kind",
            "question",
            "--body",
            "What user path should this protect?",
        )
        self.assertIn("# x Interaction Transcript: inter-visible", first.stdout)
        self.assertIn("## Room Roster", first.stdout)
        self.assertIn("- root: direction owner", first.stdout)
        self.assertIn("- main: facilitator and recorder", first.stdout)
        self.assertIn("- product: active role view", first.stdout)
        self.assertIn("To: product", first.stdout)
        self.assertIn("What user path should this protect?", first.stdout)

        self.synthesize("inter-visible")
        second = self.x(
            "interaction-turn",
            "--interaction-id",
            "inter-visible",
            "--actor",
            "product",
            "--to",
            "all",
            "--turn-kind",
            "response",
            "--body",
            "The flow must keep the buyer's next action obvious.",
        )
        self.assertIn("Status: active", second.stdout)
        self.assertIn("To: product", second.stdout)
        self.assertIn("To: all", second.stdout)
        self.assertIn("The flow must keep the buyer's next action obvious.", second.stdout)
        self.assertIn("Status: active", self.discussion_file("inter-visible").read_text(encoding="utf-8"))

        shown = self.x("interaction-show", "--interaction-id", "inter-visible")
        self.assertIn("## Turns", shown.stdout)
        self.assertIn("To: all", shown.stdout)

    def test_interaction_id_aliases_work_for_formal_records(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "with",
            "--title",
            "Alias direction",
            "--agenda",
            "Exercise interaction-id aliases.",
            "--participants",
            "technical",
            "--interaction-id",
            "inter-alias",
        )
        self.x(
            "role-brief",
            "--interaction-id",
            "inter-alias",
            "--role",
            "technical",
            "--title",
            "Technical alias view",
            "--brief-id",
            "brief-alias",
            "--recommendation",
            "Use the alias path.",
            "--rationale",
            "It keeps interaction commands consistent.",
            "--rejected-options",
            "Do not require discussion wording.",
            "--risks",
            "None.",
            "--decisions-needed",
            "Root must accept.",
            "--implications-for-architect",
            "Architect can consume the accepted intake.",
            "--strongest-objection",
            "Aliases can obscure the storage path.",
            "--weakest-assumption",
            "Users prefer interaction wording.",
            "--evidence-to-change",
            "Usage shows the old naming is clearer.",
        )
        self.x(
            "decision",
            "--interaction-id",
            "inter-alias",
            "--decision-id",
            "decision-alias",
            "--title",
            "Alias decision",
            "--decision",
            "Accept the interaction alias path.",
        )
        self.x(
            "architect-intake",
            "--interaction-id",
            "inter-alias",
            "--decision-id",
            "decision-alias",
            "--title",
            "Alias intake",
            "--intake-id",
            "intake-alias",
            "--status",
            "accepted",
            "--accepted-direction",
            "Use interaction aliases for formal records.",
            "--architecture-input",
            "No code path change needed.",
            "--scope-boundaries",
            "CLI alias behavior only.",
            "--non-goals",
            "No storage migration.",
            "--root-decisions",
            "Root accepted the alias.",
            "--risks",
            "Naming remains mixed internally.",
            "--handoff-to-architect",
            "Proceed through normal architect flow.",
        )
        interaction = self.discussion_file("inter-alias").read_text(encoding="utf-8")
        self.assertIn("brief-alias: technical", interaction)
        self.assertIn("decision-alias", interaction)
        self.assertIn("intake-alias", interaction)
        self.assertIn("Linked Architect Intake: intake-alias", self.decision_file("decision-alias").read_text(encoding="utf-8"))

    def test_closed_interaction_rejects_followup_writes(self) -> None:
        self.x(
            "discussion-start",
            "--mode",
            "with",
            "--title",
            "Closed direction",
            "--agenda",
            "Closed interactions cannot be extended.",
            "--participants",
            "technical",
            "--discussion-id",
            "disc-closed",
            "--status",
            "closed",
        )
        failed = self.x(
            "discussion-turn",
            "--discussion-id",
            "disc-closed",
            "--actor",
            "root",
            "--turn-kind",
            "statement",
            "--body",
            "Try to continue.",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("interaction disc-closed is closed", failed.stderr + failed.stdout)

        failed = self.x(
            "decision",
            "--title",
            "Closed decision",
            "--discussion-id",
            "disc-closed",
            "--decision",
            "Try to decide after close.",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("interaction disc-closed is closed", failed.stderr + failed.stdout)

    def test_independent_synthesis_requires_ready_role_briefs(self) -> None:
        self.x(
            "discussion-start",
            "--mode",
            "independent",
            "--title",
            "Product technical challenge",
            "--agenda",
            "Compare product and technical positions.",
            "--participants",
            "product",
            "technical",
            "--discussion-id",
            "disc-ready",
        )
        self.create_role_brief("disc-ready", "product", "brief-product-draft", status="draft")
        self.create_role_brief("disc-ready", "technical", "brief-technical-ready")
        failed = self.synthesize("disc-ready", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("requires role briefs for: product", failed.stderr + failed.stdout)

        self.create_role_brief("disc-ready", "product", "brief-product-ready")
        self.synthesize("disc-ready")
        self.assertIn("Status: synthesized", self.discussion_file("disc-ready").read_text(encoding="utf-8"))

    def test_with_discussion_turn_role_brief_and_councilor_package(self) -> None:
        self.x(
            "discussion-start",
            "--mode",
            "with",
            "--title",
            "Technical direction",
            "--agenda",
            "Evaluate the technical direction before architect intake.",
            "--participants",
            "technical",
            "--discussion-id",
            "disc-tech",
        )
        self.x(
            "discussion-turn",
            "--discussion-id",
            "disc-tech",
            "--actor",
            "root",
            "--turn-kind",
            "question",
            "--body",
            "Should this start from shared contracts?",
        )
        failed = self.x(
            "role-brief",
            "--discussion-id",
            "disc-tech",
            "--role",
            "technical",
            "--title",
            "Technical view",
            "--recommendation",
            "Use the shared contract first.",
            "--rationale",
            "It keeps later architect execution bounded.",
            "--rejected-options",
            "Do not build separate semantics.",
            "--risks",
            "Contract design can become too broad.",
            "--decisions-needed",
            "Root must confirm scope.",
            "--implications-for-architect",
            "Architect should keep the first run narrow.",
            "--strongest-objection",
            "",
            "--weakest-assumption",
            "Shared contract is enough.",
            "--evidence-to-change",
            "Prototype shows the shared contract is too slow.",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("--strongest-objection is required", failed.stderr + failed.stdout)

        self.x(
            "role-brief",
            "--discussion-id",
            "disc-tech",
            "--role",
            "technical",
            "--title",
            "Technical view",
            "--brief-id",
            "brief-tech",
            "--recommendation",
            "Use the shared contract first.",
            "--rationale",
            "It keeps later architect execution bounded.",
            "--rejected-options",
            "Do not build separate semantics.",
            "--risks",
            "Contract design can become too broad.",
            "--decisions-needed",
            "Root must confirm scope.",
            "--implications-for-architect",
            "Architect should keep the first run narrow.",
            "--strongest-objection",
            "This may delay visible value.",
            "--weakest-assumption",
            "Shared contract is enough.",
            "--evidence-to-change",
            "Prototype shows the shared contract is too slow.",
        )
        self.x(
            "package",
            "--role",
            "councilor",
            "--discussion-id",
            "disc-tech",
            "--council-role",
            "technical",
            "--package-id",
            "pkg-tech",
        )
        package = self.package_file("pkg-tech").read_text(encoding="utf-8")
        self.assertIn("Role: councilor", package)
        self.assertIn("Produce a technical role brief", package)
        self.assertIn("Conversation Contract:", package)
        self.assertIn("Visible Turn", package)
        self.assertIn("Do not create execution tasks", package)
        discussion = self.discussion_file("disc-tech").read_text(encoding="utf-8")
        self.assertIn("brief-tech: technical", discussion)
        self.assertIn("pkg-tech: councilor/technical", discussion)

    def test_independent_discussion_requires_all_role_briefs_before_synthesis(self) -> None:
        self.x(
            "discussion-start",
            "--mode",
            "independent",
            "--title",
            "Direction choice",
            "--agenda",
            "Choose the next direction.",
            "--participants",
            "strategy",
            "technical",
            "--discussion-id",
            "disc-independent",
        )
        self.create_role_brief("disc-independent", "strategy", "brief-strategy")
        failed = self.synthesize("disc-independent", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("requires role briefs for: technical", failed.stderr + failed.stdout)

        self.create_role_brief("disc-independent", "technical", "brief-technical")
        self.synthesize("disc-independent")
        discussion = self.discussion_file("disc-independent").read_text(encoding="utf-8")
        self.assertIn("Status: synthesized", discussion)
        self.assertIn("### Strongest Objection", discussion)

    def test_accepted_architect_intake_requires_accepted_decision_and_board_reports_it(self) -> None:
        self.x(
            "discussion-start",
            "--mode",
            "joint",
            "--title",
            "Joint direction",
            "--agenda",
            "Align strategy and technical direction.",
            "--participants",
            "strategy,technical",
            "--discussion-id",
            "disc-intake",
        )
        failed = self.create_intake("disc-intake", "decision-missing", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("decision not found", failed.stderr + failed.stdout)

        self.x(
            "decision",
            "--title",
            "Direction decision",
            "--decision-id",
            "decision-direction",
            "--discussion-id",
            "disc-intake",
            "--decision",
            "Use the shared read contract first.",
            "--context",
            "Root discussion selected the reusable path.",
            "--rationale",
            "It reduces future split semantics.",
            "--consequences",
            "Architect must keep v1 narrow.",
        )
        self.create_intake("disc-intake", "decision-direction")
        intake = self.architect_intake_file("intake-direction").read_text(encoding="utf-8")
        self.assertIn("Status: accepted", intake)
        self.assertIn("Linked Decision: decision-direction", intake)
        decision = self.decision_file("decision-direction").read_text(encoding="utf-8")
        self.assertIn("Linked Architect Intake: intake-direction", decision)

        board = self.x("board")
        self.assertIn("disc-intake", board.stdout)
        self.assertIn("intake-direction", board.stdout)
        self.assertIn("decision-direction", board.stdout)
        self.x("board", "--write")
        self.assertTrue((self.x_home / "projects/repo/boards/current.md").exists())

        self.x("start", "--run-id", "run-from-intake", "--goal", "Use discussion intake.")
        self.x("package", "--role", "architect", "--run-id", "run-from-intake", "--title", "Architect intake", "--package-id", "pkg-architect-intake")
        package = self.package_file("pkg-architect-intake").read_text(encoding="utf-8")
        self.assertIn("Accepted architect intakes", package)
        self.assertIn("intake-direction", package)

    def test_architect_package_requires_intake_choice_when_multiple_are_accepted(self) -> None:
        self.create_discussion_decision_and_intake("disc-a", "decision-a", "intake-a")
        self.create_discussion_decision_and_intake("disc-b", "decision-b", "intake-b")
        self.x("start", "--run-id", "run-many-intakes", "--goal", "Choose an intake.")

        failed = self.x(
            "package",
            "--role",
            "architect",
            "--run-id",
            "run-many-intakes",
            "--title",
            "Architect intake",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("multiple accepted architect intakes found", failed.stderr + failed.stdout)

        self.x(
            "package",
            "--role",
            "architect",
            "--run-id",
            "run-many-intakes",
            "--title",
            "Architect intake",
            "--architect-intake-id",
            "intake-a",
            "--package-id",
            "pkg-selected-intake",
        )
        package = self.package_file("pkg-selected-intake").read_text(encoding="utf-8")
        self.assertIn("intake-a", package)
        self.assertNotIn("intake-b: decision=decision-b", package)

    def create_role_brief(self, discussion_id: str, role: str, brief_id: str, *, status: str = "ready") -> None:
        self.x(
            "role-brief",
            "--discussion-id",
            discussion_id,
            "--role",
            role,
            "--title",
            f"{role} brief",
            "--brief-id",
            brief_id,
            "--recommendation",
            f"{role} recommends a bounded direction.",
            "--rationale",
            "The direction is reversible.",
            "--rejected-options",
            "Avoid broad platform work.",
            "--risks",
            "May miss a hidden constraint.",
            "--decisions-needed",
            "Root must choose the direction.",
            "--implications-for-architect",
            "Architect should preserve boundaries.",
            "--strongest-objection",
            "The direction may be too narrow.",
            "--weakest-assumption",
            "The target scope is representative.",
            "--evidence-to-change",
            "User evidence contradicts the target scope.",
            "--status",
            status,
        )

    def synthesize(self, discussion_id: str, *, check: bool = True):
        return self.x(
            "discussion-synthesize",
            "--discussion-id",
            discussion_id,
            "--agreements",
            "Both roles favor a bounded first direction.",
            "--conflicts",
            "Strategy wants speed; technical wants contract clarity.",
            "--rejected-options",
            "Reject broad platform cleanup.",
            "--root-decisions-needed",
            "Root must accept the first direction.",
            "--recommended-direction",
            "Build the narrow reusable path.",
            "--architect-intake-draft",
            "Architect should convert the direction into a narrow brief.",
            "--strongest-objection",
            "The narrow path may not prove enough value.",
            "--weakest-assumption",
            "The first path exercises the reusable boundary.",
            "--evidence-to-change",
            "A spike shows the boundary is wrong.",
            check=check,
        )

    def create_intake(self, discussion_id: str, decision_id: str, *, check: bool = True):
        return self.x(
            "architect-intake",
            "--discussion-id",
            discussion_id,
            "--decision-id",
            decision_id,
            "--title",
            "Direction intake",
            "--intake-id",
            "intake-direction",
            "--status",
            "accepted",
            "--accepted-direction",
            "Use the shared read contract first.",
            "--architecture-input",
            "Design the first slice around the shared read contract.",
            "--scope-boundaries",
            "Only the first reusable path.",
            "--non-goals",
            "No broad platform rewrite.",
            "--root-decisions",
            "Root accepted the shared read contract direction.",
            "--risks",
            "The slice may not expose enough product value.",
            "--handoff-to-architect",
            "Create Architecture Brief from this intake.",
            check=check,
        )

    def create_discussion_decision_and_intake(self, discussion_id: str, decision_id: str, intake_id: str) -> None:
        self.x(
            "discussion-start",
            "--mode",
            "with",
            "--title",
            discussion_id,
            "--agenda",
            "Prepare architect intake.",
            "--participants",
            "technical",
            "--discussion-id",
            discussion_id,
        )
        self.x(
            "decision",
            "--title",
            decision_id,
            "--decision-id",
            decision_id,
            "--discussion-id",
            discussion_id,
            "--decision",
            f"Accept direction {decision_id}.",
            "--context",
            "Root accepted the direction.",
            "--rationale",
            "It is bounded.",
            "--consequences",
            "Architect may create a brief.",
        )
        self.x(
            "architect-intake",
            "--discussion-id",
            discussion_id,
            "--decision-id",
            decision_id,
            "--title",
            intake_id,
            "--intake-id",
            intake_id,
            "--status",
            "accepted",
            "--accepted-direction",
            f"Accepted direction for {intake_id}.",
            "--architecture-input",
            "Create a bounded brief.",
            "--scope-boundaries",
            "One narrow path.",
            "--non-goals",
            "No broad platform rewrite.",
            "--root-decisions",
            "Root accepted the direction.",
            "--risks",
            "Scope may expand.",
            "--handoff-to-architect",
            "Create Architecture Brief from this intake.",
        )


if __name__ == "__main__":
    import unittest

    unittest.main()
