# TTC Dense Verifier Workflow

This project implements a test-time compute workflow for rigorous technical generation. The generator remains frozen. A separate verifier scores candidate branches during inference, allowing Beam Search or MCTS to prune answers with symbol noise, shallow claims, style drift, structural breaks, or logic gaps.

The local codebase is intentionally model-agnostic. It provides data construction, scoring interfaces, decoding controllers, static metrics, and command-line orchestration. Qwen generator and verifier checkpoints are expected to run remotely through vLLM, LLaMA-Factory, TRL, or an OpenAI-compatible HTTP API.

## Stages

1. Build C and systems-programming prompt sets.
2. Generate positive and negative answers outside this repository.
3. Convert aligned answers into preference data.
4. Train a Qwen2.5-7B reward-model verifier remotely.
5. Run verifier-guided Beam Search or MCTS using remote generator and verifier services.
6. Evaluate static metrics, judge metrics, latency, and human review results.
