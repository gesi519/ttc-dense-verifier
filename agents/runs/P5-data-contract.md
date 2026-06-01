# Task Log: P5 Data Contract

status: committed

## Result

Completed by Codex worker Faraday. Scheduler reviewed the contract, duplicate
prompt split test, and local validation results.

## Owning Agent

`agents/data_pipeline_agent.md`

## Objective

Document and tighten the local data formation contract for prompts, generation requests, answer records, preference pairs, and split rules. This task runs locally and must not use GPU or remote services.

## Allowed Files

```text
docs/data_contract.md
tests/test_data_pipeline.py
tests/test_generation_requests.py
src/ttc_dense_verifier/data_pipeline/
```

## Forbidden Files and Actions

- Do not edit remote deployment scripts.
- Do not edit training configs.
- Do not modify checkpoint or output directories.
- Do not call remote endpoints.
- Do not run GPU jobs.
- Do not commit or push.

## Required Checks

```bash
PYTHONPATH=src python3 -m unittest tests.test_data_pipeline tests.test_generation_requests -v
PYTHONPATH=src python3 -m compileall -q src tests
```

## Expected Deliverables

- `docs/data_contract.md`
- Any focused schema tests needed to enforce the contract.
- A final summary with changed files, checks, risks, and follow-up.

## Scheduler Review Checklist

- The contract matches current CLI behavior.
- The split rules prevent train/val/test overlap.
- The document clearly distinguishes prompt, request, answer, and preference pair schemas.
- No large data files were added.
- Tests pass.
