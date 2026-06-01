# Remote Bootstrap Report

Date: 2026-06-01

## Scope

Phase P4 checked remote placement and readiness for the TTC Dense Verifier workflow on `g3`.

No model service, training job, batch data generation, or long GPU task was started.

## Remote Target

```text
host: g3
project_dir: /data/lry_machine_learning/ttc_dense_verifier
mode: synced artifact tree
```

The remote directory is writable and contains the synced repository files. It is not a Git checkout because `remote-sync` intentionally excludes `.git`.

## Sync Result

The first rsync-based sync timed out. The Makefile was updated to use tar-over-ssh instead:

```bash
make remote-sync
```

The updated sync completed successfully. It excludes:

```text
.git
checkpoints
outputs/logs
scripts/remote_deploy/generated/.env
```

## Remote Status

`make remote-status` completed and reported:

```text
/data/lry_machine_learning/ttc_dense_verifier
[status] not a git checkout; synced artifact tree
```

GPU inventory was available through `nvidia-smi`.

At the time of inspection, all 8 GPUs were already occupied by existing processes:

```text
GPU 0-3: ~38319 MiB each, high utilization
GPU 4-7: ~13013-13015 MiB each, high utilization
```

This means subsequent service startup, data generation, training, or TTC inference should wait for an explicit scheduling decision.

## Tooling Status

Observed on remote PATH:

```text
tmux: available
nvidia-smi: available
python3: /usr/bin/python3, Python 3.8.10
python: missing from PATH
vllm: missing from PATH
llamafactory-cli: missing from PATH
```

The presence of Miniconda was observed under:

```text
/data/lry_machine_learning/miniconda3
```

but the required project environment has not been selected or activated yet.

## Model Path Status

A quick scan under `/data/lry_machine_learning/models` did not find Qwen checkpoints. Existing model directories included SmolVLM/LeRobot assets, not the required generator/verifier checkpoints.

The generated `.env` still requires real values for:

```text
GENERATOR_MODEL_PATH
VERIFIER_SERVICE_COMMAND
```

## Env Status

The remote `.env` file was created from:

```text
scripts/remote_deploy/generated/.env.example
```

No secret values are recorded in this report.

`make remote-env-check` currently fails as expected:

```text
[env] required variable is empty: VERIFIER_SERVICE_COMMAND
```

This is a correct blocker. The next phase must not run `remote-health`, start services, or run long jobs until the verifier service command and model paths are filled in on the remote `.env`.

## Follow-Up Required

Before P7 service health checks:

1. Decide which remote Python/conda environment should run this project.
2. Install or expose `vllm` and `llamafactory-cli` in that environment.
3. Place or reference the Qwen2.5-32B generator checkpoint.
4. Define the verifier score service command.
5. Re-run:

```bash
make remote-sync
make remote-status
make remote-env-check
```

Only after those pass should the project proceed to service startup or health checks.
