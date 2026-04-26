from __future__ import annotations

from tests.x_state_test_base import XStateTestCase


class XStateDiscussionTests(XStateTestCase):
    def interaction_file(self, interaction_id: str):
        return self.x_home / "projects/repo/interactions" / f"{interaction_id}.md"

    def participant_brief_file(self, brief_id: str):
        return self.x_home / "projects/repo/participant-briefs" / f"{brief_id}.md"

    def architect_intake_file(self, intake_id: str):
        return self.x_home / "projects/repo/architect-intakes" / f"{intake_id}.md"

    def decision_file(self, decision_id: str):
        return self.x_home / "projects/repo/decisions" / f"{decision_id}.md"

    def test_participant_registry_lists_defaults_and_allows_runtime_participants(self) -> None:
        participants = self.x("participant-list").stdout
        self.assertIn("founder (default)", participants)
        self.assertIn("cto (default)", participants)
        self.assertIn("product-lead (default)", participants)
        self.assertIn("market-intelligence (default)", participants)
        self.assertIn("gtm (default)", participants)
        self.assertIn("challenger (default)", participants)
        self.assertIn("council: founder, cto, product-lead, market-intelligence, gtm, challenger", participants)
        for removed_role in ("strategy", "technical", "product", "architect", "growth"):
            self.assertNotIn(f"- {removed_role} (default)", participants)
        self.assertNotIn("company-council", participants)
        self.assertNotIn("product-acceptance", participants)

        product_lead = self.x("participant-show", "product-lead").stdout
        self.assertIn("## Use When", product_lead)
        self.assertIn("user path", product_lead)
        self.assertIn("unacceptable experience", product_lead)
        self.assertIn("Acceptance/QA", product_lead)
        founder = self.x("participant-show", "founder").stdout
        self.assertIn("company-level judgment", founder)
        market = self.x("participant-show", "market-intelligence").stdout
        self.assertIn("customer evidence", market)
        self.assertIn("competitors", market)
        gtm = self.x("participant-show", "gtm").stdout
        self.assertIn("sales motion", gtm)
        self.assertIn("pricing", gtm)

        for removed_role in ("strategy", "technical", "product", "architect", "growth"):
            failed = self.x("participant-show", removed_role, check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn(f"unknown participant: {removed_role}", failed.stderr + failed.stdout)

        self.x(
            "participant-set",
            "ops",
            "--responsibilities",
            "Keep launch operations bounded.",
            "--use-when",
            "Launch readiness is unclear.",
            "--handoff-value",
            "Surface runbook risks before architect intake.",
        )
        self.assertIn("ops (runtime)", self.x("participant-list").stdout)
        ops = self.x("participant-show", "ops").stdout
        self.assertIn("launch operations", ops)
        self.assertIn("## Evidence Standard", ops)
        self.assertIn("Launch readiness is unclear.", ops)
        self.assertIn("Surface runbook risks before architect intake.", ops)

        self.x("participant-set", "cto", "--body", "# x Participant Card: cto\n\nParticipant: cto\n\nModified CTO card.\n")
        self.assertIn("cto (runtime override)", self.x("participant-list").stdout)
        self.assertIn("Modified CTO card", self.x("participant-show", "cto").stdout)

        failed = self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "Unknown participant",
            "--agenda",
            "Should fail.",
            "--participants",
            "unknown",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("unknown participant: unknown", failed.stderr + failed.stdout)

        failed = self.x("participant-set", "engineer", "--body", "# x Participant Card: engineer\n", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("reserved participant name: engineer", failed.stderr + failed.stdout)

        failed = self.x("participant-set", "council", "--body", "# x Participant Card: council\n", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("reserved participant name: council", failed.stderr + failed.stdout)

        self.assertNotIn("- engineer ", self.x("participant-list").stdout)

    def test_council_preset_expands_and_packages_default_participants(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "Company decision",
            "--agenda",
            "Should this become a company direction?",
            "--participants",
            "council",
            "--interaction-id",
            "inter-company",
        )
        interaction = self.interaction_file("inter-company").read_text(encoding="utf-8")
        self.assertIn("Participants: founder, cto, product-lead, market-intelligence, gtm, challenger", interaction)

        self.x(
            "package",
            "--role",
            "councilor",
            "--interaction-id",
            "inter-company",
            "--participant",
            "market-intelligence",
            "--package-id",
            "pkg-market",
        )
        package = self.package_file("pkg-market").read_text(encoding="utf-8")
        self.assertIn("Role: councilor", package)
        self.assertIn("# x Participant Card: market-intelligence", package)
        self.assertIn("Competitors, substitutes, market structure, customer evidence", package)
        self.assertIn("document-use notes", package)
        self.assertIn("pkg-market: councilor/market-intelligence", self.interaction_file("inter-company").read_text(encoding="utf-8"))

        self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "Selected council",
            "--agenda",
            "Should this launch through a narrow channel?",
            "--participants",
            "founder",
            "gtm",
            "challenger",
            "--interaction-id",
            "inter-selected",
        )
        selected = self.interaction_file("inter-selected").read_text(encoding="utf-8")
        self.assertIn("Participants: founder, gtm, challenger", selected)

        failed = self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "Removed preset",
            "--agenda",
            "Should fail.",
            "--participants",
            "company-council",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("unknown participant: company-council", failed.stderr + failed.stdout)

    def test_single_custom_participant_loop(self) -> None:
        self.x(
            "participant-set",
            "ops",
            "--body",
            "# x Participant Card: ops\n\nParticipant: ops\n\n## Responsibilities\n\nChallenge operational readiness.\n",
        )
        self.x(
            "interaction-start",
            "--mode",
            "joint",
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
            "--core-judgment",
            "Manual launch is acceptable only as a bounded first proof.",
            "--key-arguments",
            "The runbook keeps launch cost low while exposing rollback risk.",
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
            "--document-use-notes",
            "BRD and sales strategy may claim manual launch, but must not imply repeatable automation.",
        )
        interaction = self.interaction_file("inter-ops").read_text(encoding="utf-8")
        self.assertIn("Status: synthesized", interaction)
        self.assertIn("ops / response", interaction)
        self.assertIn("### Room Essence", interaction)
        self.assertIn("#### Core Judgment", interaction)
        self.assertIn("Manual launch is acceptable only as a bounded first proof.", interaction)
        self.assertIn("#### Document-Use Notes", interaction)
        self.assertIn("BRD and sales strategy may claim manual launch", interaction)
        self.assertIn("Proceed with a manual launch runbook.", interaction)

    def test_interaction_turns_record_audience_and_print_transcript(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "Visible joint direction",
            "--agenda",
            "Keep participant conversation visible.",
            "--participants",
            "product-lead",
            "cto",
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
            "product-lead",
            "--turn-kind",
            "question",
            "--body",
            "What user path should this protect?",
        )
        self.assertIn("# x Interaction Transcript: inter-visible", first.stdout)
        self.assertIn("## Room Roster", first.stdout)
        self.assertIn("- root: direction owner", first.stdout)
        self.assertIn("- main: facilitator and recorder", first.stdout)
        self.assertIn("- product-lead: active participant view", first.stdout)
        self.assertIn("To: product-lead", first.stdout)
        self.assertIn("What user path should this protect?", first.stdout)

        self.synthesize("inter-visible")
        second = self.x(
            "interaction-turn",
            "--interaction-id",
            "inter-visible",
            "--actor",
            "product-lead",
            "--to",
            "all",
            "--turn-kind",
            "response",
            "--body",
            "The flow must keep the buyer's next action obvious.",
        )
        self.assertIn("Status: active", second.stdout)
        self.assertIn("To: product-lead", second.stdout)
        self.assertIn("To: all", second.stdout)
        self.assertIn("The flow must keep the buyer's next action obvious.", second.stdout)
        self.assertIn("Status: active", self.interaction_file("inter-visible").read_text(encoding="utf-8"))

        shown = self.x("interaction-show", "--interaction-id", "inter-visible")
        self.assertIn("## Turns", shown.stdout)
        self.assertIn("To: all", shown.stdout)

    def test_interaction_id_links_formal_records(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "Formal direction",
            "--agenda",
            "Exercise interaction-id linking.",
            "--participants",
            "cto",
            "--interaction-id",
            "inter-formal",
        )
        self.x(
            "participant-brief",
            "--interaction-id",
            "inter-formal",
            "--participant",
            "cto",
            "--title",
            "CTO formal view",
            "--brief-id",
            "brief-formal",
            "--recommendation",
            "Use the formal interaction path.",
            "--rationale",
            "It keeps interaction commands consistent.",
            "--rejected-options",
            "Do not require legacy wording.",
            "--risks",
            "None.",
            "--decisions-needed",
            "Root must accept.",
            "--implications-for-architect",
            "Architect can consume the accepted intake.",
            "--strongest-objection",
            "Formal records can obscure the storage path.",
            "--weakest-assumption",
            "Users prefer interaction wording.",
            "--evidence-to-change",
            "Usage shows the old naming is clearer.",
        )
        self.x(
            "decision",
            "--interaction-id",
            "inter-formal",
            "--decision-id",
            "decision-formal",
            "--title",
            "Formal decision",
            "--decision",
            "Accept the interaction path.",
        )
        self.x(
            "architect-intake",
            "--interaction-id",
            "inter-formal",
            "--decision-id",
            "decision-formal",
            "--title",
            "Formal intake",
            "--intake-id",
            "intake-formal",
            "--status",
            "accepted",
            "--accepted-direction",
            "Use interaction IDs for formal records.",
            "--architecture-input",
            "No code path change needed.",
            "--scope-boundaries",
            "CLI interaction linking only.",
            "--non-goals",
            "No storage migration.",
            "--root-decisions",
            "Root accepted the interaction.",
            "--risks",
            "Naming remains mixed internally.",
            "--handoff-to-architect",
            "Proceed through normal architect flow.",
        )
        interaction = self.interaction_file("inter-formal").read_text(encoding="utf-8")
        self.assertIn("brief-formal: cto", interaction)
        self.assertIn("decision-formal", interaction)
        self.assertIn("intake-formal", interaction)
        self.assertIn("Linked Architect Intake: intake-formal", self.decision_file("decision-formal").read_text(encoding="utf-8"))

    def test_closed_interaction_rejects_followup_writes(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "Closed direction",
            "--agenda",
            "Closed interactions cannot be extended.",
            "--participants",
            "cto",
            "--interaction-id",
            "disc-closed",
            "--status",
            "closed",
        )
        failed = self.x(
            "interaction-turn",
            "--interaction-id",
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
            "--interaction-id",
            "disc-closed",
            "--decision",
            "Try to decide after close.",
            check=False,
        )
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("interaction disc-closed is closed", failed.stderr + failed.stdout)

    def test_independent_synthesis_requires_ready_participant_briefs(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "independent",
            "--title",
            "Product CTO challenge",
            "--agenda",
            "Compare product and CTO positions.",
            "--participants",
            "product-lead",
            "cto",
            "--interaction-id",
            "disc-ready",
        )
        self.create_participant_brief("disc-ready", "product-lead", "brief-product-draft", status="draft")
        self.create_participant_brief("disc-ready", "cto", "brief-cto-ready")
        failed = self.synthesize("disc-ready", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("requires participant briefs for: product-lead", failed.stderr + failed.stdout)

        self.create_participant_brief("disc-ready", "product-lead", "brief-product-ready")
        self.synthesize("disc-ready")
        self.assertIn("Status: synthesized", self.interaction_file("disc-ready").read_text(encoding="utf-8"))

    def test_single_participant_turn_brief_and_councilor_package(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "CTO direction",
            "--agenda",
            "Evaluate the technical direction before architect intake.",
            "--participants",
            "cto",
            "--interaction-id",
            "disc-cto",
        )
        self.x(
            "interaction-turn",
            "--interaction-id",
            "disc-cto",
            "--actor",
            "root",
            "--turn-kind",
            "question",
            "--body",
            "Should this start from shared contracts?",
        )
        failed = self.x(
            "participant-brief",
            "--interaction-id",
            "disc-cto",
            "--participant",
            "cto",
            "--title",
            "CTO view",
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
            "participant-brief",
            "--interaction-id",
            "disc-cto",
            "--participant",
            "cto",
            "--title",
            "CTO view",
            "--brief-id",
            "brief-cto",
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
            "--interaction-id",
            "disc-cto",
            "--participant",
            "cto",
            "--package-id",
            "pkg-cto",
        )
        package = self.package_file("pkg-cto").read_text(encoding="utf-8")
        self.assertIn("Role: councilor", package)
        self.assertIn("Produce a cto participant brief", package)
        self.assertIn("Conversation Contract:", package)
        self.assertIn("Visible Turn", package)
        self.assertIn("Do not create execution tasks", package)
        interaction = self.interaction_file("disc-cto").read_text(encoding="utf-8")
        self.assertIn("brief-cto: cto", interaction)
        self.assertIn("pkg-cto: councilor/cto", interaction)

    def test_independent_interaction_requires_all_participant_briefs_before_synthesis(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "independent",
            "--title",
            "Direction choice",
            "--agenda",
            "Choose the next direction.",
            "--participants",
            "founder",
            "cto",
            "--interaction-id",
            "disc-independent",
        )
        self.create_participant_brief("disc-independent", "founder", "brief-founder")
        failed = self.synthesize("disc-independent", check=False)
        self.assertNotEqual(failed.returncode, 0)
        self.assertIn("requires participant briefs for: cto", failed.stderr + failed.stdout)

        self.create_participant_brief("disc-independent", "cto", "brief-cto")
        self.synthesize("disc-independent")
        interaction = self.interaction_file("disc-independent").read_text(encoding="utf-8")
        self.assertIn("Status: synthesized", interaction)
        self.assertIn("### Strongest Objection", interaction)

    def test_accepted_architect_intake_requires_accepted_decision_and_board_reports_it(self) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            "Joint direction",
            "--agenda",
            "Align founder and CTO direction.",
            "--participants",
            "founder,cto",
            "--interaction-id",
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
            "--interaction-id",
            "disc-intake",
            "--decision",
            "Use the shared read contract first.",
            "--context",
            "Root interaction selected the reusable path.",
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

        self.x("start", "--run-id", "run-from-intake", "--goal", "Use interaction intake.")
        self.x("package", "--role", "architect", "--run-id", "run-from-intake", "--title", "Architect intake", "--package-id", "pkg-architect-intake")
        package = self.package_file("pkg-architect-intake").read_text(encoding="utf-8")
        self.assertIn("Accepted architect intakes", package)
        self.assertIn("intake-direction", package)

    def test_architect_package_requires_intake_choice_when_multiple_are_accepted(self) -> None:
        self.create_interaction_decision_and_intake("disc-a", "decision-a", "intake-a")
        self.create_interaction_decision_and_intake("disc-b", "decision-b", "intake-b")
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

    def create_participant_brief(self, interaction_id: str, participant: str, brief_id: str, *, status: str = "ready") -> None:
        self.x(
            "participant-brief",
            "--interaction-id",
            interaction_id,
            "--participant",
            participant,
            "--title",
            f"{participant} brief",
            "--brief-id",
            brief_id,
            "--recommendation",
            f"{participant} recommends a bounded direction.",
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

    def synthesize(self, interaction_id: str, *, check: bool = True):
        return self.x(
            "interaction-summarize",
            "--interaction-id",
            interaction_id,
            "--agreements",
            "Both participants favor a bounded first direction.",
            "--conflicts",
            "Founder wants speed; CTO wants contract clarity.",
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

    def create_intake(self, interaction_id: str, decision_id: str, *, check: bool = True):
        return self.x(
            "architect-intake",
            "--interaction-id",
            interaction_id,
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

    def create_interaction_decision_and_intake(self, interaction_id: str, decision_id: str, intake_id: str) -> None:
        self.x(
            "interaction-start",
            "--mode",
            "joint",
            "--title",
            interaction_id,
            "--agenda",
            "Prepare architect intake.",
            "--participants",
            "cto",
            "--interaction-id",
            interaction_id,
        )
        self.x(
            "decision",
            "--title",
            decision_id,
            "--decision-id",
            decision_id,
            "--interaction-id",
            interaction_id,
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
            "--interaction-id",
            interaction_id,
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
