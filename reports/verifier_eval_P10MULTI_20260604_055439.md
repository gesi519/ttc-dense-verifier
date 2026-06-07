# Verifier eval P10MULTI_20260604_055439

## Scope
- checkpoint: `/data/lry_machine_learning/checkpoints/ttc_dense_verifier/verifier_qwen7b_rm_P10MULTI_20260604_055439/checkpoint-600`
- base_model: `/data/lry_machine_learning/models/Qwen2.5-7B-Instruct`
- validation slice: `data/training/rm/val_rm.jsonl` first 50 pairs
- loader: LLaMAFactory `load_model(..., add_valuehead=True)`

## Results
- pairwise_accuracy: 1.0000
- mean_margin: 12.7158
- median_margin: 13.2728
- min_margin: 5.7775
- max_margin: 16.2693
- failed_prompt_ids: []
- elapsed_sec: 52.65

## Training Metrics
- train_loss: 0.02391868796035441
- last_eval_loss: 1.2086234164598864e-05
- best_metric: 1.082625203707721e-05
- best_model_checkpoint: `/data/lry_machine_learning/checkpoints/ttc_dense_verifier/verifier_qwen7b_rm_P10MULTI_20260604_055439/checkpoint-600`

## Decision
The trained verifier checkpoint loads with its value head and passes the pairwise smoke test on the validation slice.
