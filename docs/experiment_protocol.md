# Experiment Protocol

## Compared Methods

- `raw_generator`: direct Qwen2.5-32B-Instruct generation.
- `sft_baseline`: optional Qwen2.5-32B LoRA or QLoRA SFT baseline.
- `ttc_beam`: frozen generator plus verifier-guided Beam Search.
- `ttc_mcts`: frozen generator plus verifier-guided MCTS.

## Local Metrics

The local static evaluator computes abnormal symbol counts, code fence mismatch, heading and list counts, repeated slogan-like phrase counts, answer length, and word count.

## Required Logs

Each inference run should preserve prompt ID, method name, final answer, branch scores, verifier call count, latency, token counts when available, and decoding parameters.
