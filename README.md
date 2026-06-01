# TTC Dense Verifier

This repository is the implementation scaffold for a test-time compute dense verifier workflow. It keeps the generator and verifier behind replaceable client interfaces so local development never downloads model checkpoints.

The initial code focuses on the parts that can be tested locally:

- preference-data construction from prompt, chosen, and rejected JSONL files;
- deterministic train/validation/test splitting by prompt ID;
- verifier-guided Beam Search and a small MCTS controller;
- static quality metrics for symbol noise, Markdown defects, slogans, and length;
- CLI commands for data preparation, static evaluation, TTC decoding smoke tests, and remote deployment checks.

Model execution is intentionally external. Use HTTP/vLLM-compatible clients or remote scripts for Qwen checkpoints; do not put model weights in this repository.

## Harness Engineering

This repository uses a Harness Engineering layout for reproducible agent-driven experiments. The project-level agent boundaries, constraints, and automation entrypoints are documented in:

- `AGENTS.md`
- `docs/harness_engineering.md`
- `docs/project_structure.md`
- `docs/constraints_layer.md`
- `docs/automation_layer.md`

Common local entrypoints:

```bash
make test
make smoke
make remote-runbook
make verify
```

## Remote Gate

Generate remote scripts after changing deployment logic:

```powershell
$env:PYTHONPATH="src"
python -m ttc_dense_verifier.cli export-remote-runbook `
  --output-dir scripts/remote_deploy/generated `
  --remote-project-dir /data/lry_machine_learning/ttc_dense_verifier
```

Before remote training, copy `scripts/remote_deploy/generated/.env.example` to `.env` on the server, set the generator model path and verifier service command, source it, start `start_generator_vllm.sh` and `start_verifier_service.sh`, then run `scripts/remote_deploy/generated/health_check.sh`.

## Local Verification

```powershell
python -m unittest discover -s tests -v
```

## CLI Examples

```powershell
$env:PYTHONPATH="src"
python -m ttc_dense_verifier.cli prepare-preferences `
  --questions data/raw_questions/questions.jsonl `
  --positive data/generated_positive/positive_answers.jsonl `
  --negative data/generated_negative/negative_answers.jsonl `
  --output-dir data/preference

python -m ttc_dense_verifier.cli evaluate-static `
  --input data/evaluation_outputs/outputs.jsonl `
  --output-dir outputs/tables
```
