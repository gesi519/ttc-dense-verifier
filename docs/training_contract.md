# Training Input Contract

This contract defines the local artifacts required before any LLaMA-Factory
training command is allowed to run. It covers reward-model training for the
dense verifier and SFT training for the generator baseline. It is a dry-run
contract only: validation must not start `llamafactory-cli train`, load model
weights, call remote services, or reserve GPU memory.

## Scope

The local training inputs are produced from preference data after prompt
generation, answer generation, and preference pairing.

Required local exports:

- RM dataset directory: `data/training/rm`
- SFT dataset directory: `data/training/sft`
- RM config: `configs/training/verifier_rm_qwen7b.yaml`
- SFT config: `configs/training/generator_sft_qwen32b_lora.yaml`

The validation entrypoint is:

```bash
PYTHONPATH=src python3 -m ttc_dense_verifier.cli validate-training-inputs \
  --rm-config configs/training/verifier_rm_qwen7b.yaml \
  --sft-config configs/training/generator_sft_qwen32b_lora.yaml \
  --rm-dataset-dir data/training/rm \
  --sft-dataset-dir data/training/sft \
  --output outputs/training_input_validation.json
```

## RM Dataset

The reward-model dataset is a ranking dataset with separate train and
validation files.

Required files:

- `data/training/rm/train_rm.jsonl`
- `data/training/rm/val_rm.jsonl`
- `data/training/rm/dataset_info.json`

Each JSONL row must contain:

```json
{
  "instruction": "Original prompt text",
  "input": "",
  "chosen": "Preferred answer",
  "rejected": "Rejected answer",
  "metadata": {
    "prompt_id": "stable prompt id"
  }
}
```

`dataset_info.json` must expose both dataset names used by the RM config:

```json
{
  "ttc_rm": {
    "file_name": "train_rm.jsonl",
    "ranking": true,
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "chosen": "chosen",
      "rejected": "rejected"
    }
  },
  "ttc_rm_val": {
    "file_name": "val_rm.jsonl",
    "ranking": true,
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "chosen": "chosen",
      "rejected": "rejected"
    }
  }
}
```

RM config requirements:

- `stage: rm`
- `do_train: true`
- `finetuning_type: lora`
- `dataset: ttc_rm`
- `eval_dataset: ttc_rm_val`
- `dataset_dir: data/training/rm`
- `template: qwen`
- `output_dir: checkpoints/verifier_qwen7b_rm`

## SFT Dataset

The SFT dataset keeps only the positive side of each preference pair. It must
not include `rejected` text in training rows.

Required files:

- `data/training/sft/train_sft.jsonl`
- `data/training/sft/dataset_info.json`

Each JSONL row must contain:

```json
{
  "instruction": "Original prompt text",
  "input": "",
  "output": "Preferred answer",
  "metadata": {
    "prompt_id": "stable prompt id"
  }
}
```

`dataset_info.json` must expose the dataset name used by the SFT config:

```json
{
  "ttc_sft": {
    "file_name": "train_sft.jsonl",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
```

SFT config requirements:

- `stage: sft`
- `do_train: true`
- `finetuning_type: lora`
- `quantization_bit: 4`
- `dataset: ttc_sft`
- `dataset_dir: data/training/sft`
- `template: qwen`
- `output_dir: checkpoints/generator_qwen32b_sft_lora`
- `deepspeed: configs/training/deepspeed_zero3.json`

## Export Commands

RM export:

```bash
PYTHONPATH=src python3 -m ttc_dense_verifier.cli export-rm-dataset \
  --train data/preference/train_preference.jsonl \
  --val data/preference/val_preference.jsonl \
  --output-dir data/training/rm \
  --dataset-name ttc_rm
```

SFT export:

```bash
PYTHONPATH=src python3 -m ttc_dense_verifier.cli export-sft-dataset \
  --input data/preference/train_preference.jsonl \
  --output data/training/sft/train_sft.jsonl
```

## Validation Semantics

`validate-training-inputs` checks:

- Required config keys are present.
- RM config uses `stage: rm`; SFT config uses `stage: sft`.
- `do_train` is explicitly `true`.
- `dataset_info.json` exists in both dataset directories.
- Dataset names referenced by configs exist in `dataset_info.json`.
- RM datasets have `ranking: true`.
- LLaMA-Factory column mappings match the exported JSONL schema.
- The first non-empty rows in each JSONL file contain required columns.
- Existing non-empty checkpoint directories are reported when
  `overwrite_output_dir: true` is set.

Validation failures block training. Overwrite findings are warnings because a
resume or intentional replacement can be valid, but the scheduler must review
them before starting training.

## Checkpoint Overwrite Rule

Never start training blindly when `output_dir` already exists and contains
files. The current configs set:

- `checkpoints/verifier_qwen7b_rm`
- `checkpoints/generator_qwen32b_sft_lora`

If either directory is non-empty and `overwrite_output_dir: true`, the agent
must stop for scheduler review unless the task log explicitly authorizes
overwriting that checkpoint.
