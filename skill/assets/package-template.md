# x Subagent Package: {package_id}

Status: {status}
Role: {role}
Date: {date}
Linked Run: {run_id}
Linked Contract: {contract_id}
Linked Task: {task_id}
Linked Iteration: {iteration_id}
Linked Review: {review_id}

## Purpose

{purpose}

## Execution Rules

- Load Project Context Files before answering; earlier files win on conflict.
- Stay inside the package role and linked state records.
- Do not mutate final ledger state from a subagent.
- Return exactly the evidence requested below.

## Project Context Files

{project_context}

## Payload

{payload}

## Expected Return

{expected_return}
