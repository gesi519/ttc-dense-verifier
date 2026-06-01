# Codex Agent Dispatch Protocol

## Purpose

This project can delegate bounded non-GPU subtasks to Codex sub-agents. The scheduler remains responsible for review, integration, commits, and deciding when to stop.

## Dispatch Rules

Use Codex sub-agents for:

- Documentation contracts.
- Local schema validation.
- Local tests.
- Makefile or runbook dry-run improvements.
- Report templates.
- Code changes with a narrow, disjoint write scope.

Do not use Codex sub-agents to directly:

- Start long GPU training.
- Start model services.
- Run batch remote generation.
- Run full benchmark inference.
- Modify remote `.env`.
- Delete remote data or checkpoints.
- Commit or push without scheduler review.

## Required Task Log

Before spawning a Codex sub-agent, the scheduler must create or update a task log under:

```text
agents/runs/<task_id>.md
```

The task log must include:

- task id
- owning agent card
- status
- objective
- allowed files
- forbidden files/actions
- required checks
- expected deliverables
- scheduler review checklist

## Worker Prompt Requirements

Every Codex sub-agent prompt must include:

- the repository path
- the task log path
- the exact write scope
- a statement that other agents may be editing the repo
- a warning not to revert unrelated changes
- required validation commands
- final response format

## Review Flow

1. Scheduler creates task log.
2. Scheduler spawns worker.
3. Worker edits only its assigned files.
4. Worker reports changed files, checks, risks, and follow-up.
5. Scheduler reviews diff and runs relevant tests.
6. Scheduler either integrates, asks for changes, or discards the worker output.
7. Scheduler updates task log status.
8. Scheduler commits only after review.

## Status Values

```text
planned
delegated
in_review
accepted
needs_revision
blocked
committed
```

## Final Worker Response Format

```text
Summary:
- ...

Files changed:
- ...

Checks:
- command: result

Risks:
- ...

Follow-up:
- ...
```
