# Task Log: P6 Training Contract

status: planned

## Owning Agent

`agents/training_agent.md`

## Objective

Document and validate the local training input contract for reward-model and SFT dataset exports. This task runs locally and must not start training.

## Allowed Files

```text
docs/training_contract.md
tests/test_training_configs.py
tests/test_training_exports.py
tests/test_training_validation.py
src/ttc_dense_verifier/training/
```

## Forbidden Files and Actions

- Do not start `llamafactory-cli train`.
- Do not edit checkpoint directories.
- Do not edit remote `.env`.
- Do not call remote endpoints.
- Do not run GPU jobs.
- Do not commit or push.

## Required Checks

```bash
PYTHONPATH=src python3 -m unittest tests.test_training_configs tests.test_training_exports tests.test_training_validation tests.test_training_run_summary -v
PYTHONPATH=src python3 -m compileall -q src tests
```

## Expected Deliverables

- `docs/training_contract.md`
- Any focused tests needed to enforce training input assumptions.
- A final summary with changed files, checks, risks, and follow-up.

## Scheduler Review Checklist

- The contract matches current LLaMA-Factory export behavior.
- RM and SFT dataset formats are clearly separated.
- Checkpoint overwrite risks are called out.
- No training or GPU task was started.
- Tests pass.
