# x Architect Execution Plan: {plan_id}

Status: {status}
Architect Gate Status: not-run
Final Verification Status: {final_verification_status}
Date: {date}
Linked Run: {run_id}
Linked Contract: {contract_id}
Integration Worktree: {integration_worktree}
Integration Branch: {integration_branch}

## Objective

{objective}

## Parallel Lanes

Required table columns: Lane ID, Task ID, Allowed Scope, Forbidden Scope, Worktree Scope, Verification, Done Evidence, Risk Level, Concurrent Group, Serial Only, Shared Files. Risk Level is `standard`, `high`, or `critical`; Concurrent Group is a group name or `none`; Serial Only is `yes` or `no`; Shared Files is a file/module list or `none`. Shared files and public output/schema, shared interfaces, auth/security/privacy, data migrations, performance-sensitive paths, public APIs, or multi-lane file/module ownership require `critical`.

{parallel_lanes}

## Task Dependency Graph

{dependency_graph}

## Shared Contract Surfaces

{shared_contract_surfaces}

## Acceptance Checkpoints

{acceptance_checkpoints}

## Lane Session Ownership

{lane_ownership}

## Scope Boundaries

Allowed:
{allowed_scope}

Forbidden:
{forbidden_scope}

## Expected Artifacts

{expected_artifacts}

## Verification Matrix

{verification_matrix}

## Reviewer Criteria

{reviewer_criteria}

## Architect Merge Criteria

{architect_merge_criteria}

## Integration Order

{integration_order}

## Known Risks

{known_risks}

## Loopback Triggers

Must include: second non-ready review -> architect loopback; third non-ready review -> architect replan; first non-ready review with abstraction/public-surface/shared-interface signals -> architect observation before another fix.

{loopback_triggers}

## Blocked-State Recovery

{blocked_recovery}

## Root Decisions Needed

{root_decisions}

## Gate Result

Pending.

## Final Verification Evidence

{final_verification}
