# x Package: {package_id}

Status: {status}
Role: {role}
Date: {date}
Linked Run: {run_id}
Linked Contract: {contract_id}
Linked Plan: {plan_id}
Linked Lane: {lane_id}
Linked Task: {task_id}
Linked Attempt: {attempt_id}
Linked Review: {review_id}
Control Root: {control_root}
Execution Status: {execution_status}
Integration Worktree: {execution_worktree}
Integration Branch: {execution_branch}
Lane Worktree: {lane_worktree}
Lane Branch: {lane_branch}

## Purpose

{purpose}

## Execution Rules

- Load Project Context Files before answering; earlier files win on conflict.
- Stay inside the package role and linked state records.
- Do not mutate final ledger state from a role package.
- Engineer and reviewer roles must work only in the Lane Worktree. If it is not available or the cwd does not match, stop and report the blocker.
- Treat this package as intentionally narrow. Do not ask main for full run history unless the linked contract, diff/evidence, lane/task scope, verification, and loopback context are insufficient to complete this exact role task.
- Return exactly the evidence requested below.

## Project Context Files

{project_context}

## Payload

{payload}

## Expected Return

{expected_return}
