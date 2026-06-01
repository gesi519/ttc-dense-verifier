# Remote Deploy Scripts

Generated deployment artifacts live in `generated/`.

Regenerate them after changing `src/ttc_dense_verifier/remote/plan.py`:

```bash
python -m ttc_dense_verifier.cli export-remote-runbook \
  --output-dir scripts/remote_deploy/generated \
  --remote-project-dir /data/lry_machine_learning/ttc_dense_verifier
```

Remote startup order:

1. Sync the repository with `make remote-sync`.
2. Create a CUDA Python environment and install this package.
3. Install and verify `tmux`, `llamafactory-cli`, vLLM, and CUDA PyTorch.
4. Copy `generated/.env.example` to `generated/.env` and fill endpoint, model path, GPU, and verifier service command values. `GENERATOR_ENDPOINT` is the OpenAI-compatible base URL such as `http://127.0.0.1:8000/v1`.
5. Run `make remote-status` before changing remote services.
6. Run `generated/start_generator_vllm.sh` and `generated/start_verifier_service.sh`.
7. Run `make remote-health` to verify CUDA, tooling, writable paths, and one generator/verifier probe request.
8. Run `make remote-jobs` for ordered long jobs. After verifier training, the runbook runs `generated/switch_verifier_to_trained.sh` and probes the trained verifier before the `post_training_validation` phase scores validation pairs.
