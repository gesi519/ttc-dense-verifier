from __future__ import annotations

from typing import Any

from ttc_dense_verifier.decoding.types import DecodingResult


def build_inference_record(
    *,
    prompt_id: str,
    prompt: str,
    result: DecodingResult,
    generator_model: str,
    verifier_model: str,
) -> dict[str, Any]:
    branch_scores = [
        {
            "text": branch.text,
            "generator_logprob": branch.generator_logprob,
            "verifier_reward": branch.verifier_reward,
            "total_score": branch.total_score,
            "is_complete": branch.is_complete,
            "metadata": branch.metadata,
        }
        for branch in result.branches
    ]
    step_traces = [
        step.to_dict() if hasattr(step, "to_dict") else step
        for step in result.steps
    ]
    return {
        "prompt_id": prompt_id,
        "prompt": prompt,
        "method": result.method,
        "final_answer": result.final_answer,
        "final_score": result.final_score,
        "branch_scores": branch_scores,
        "step_traces": step_traces,
        "verifier_call_count": result.verifier_call_count,
        "latency_ms": result.latency_ms,
        "generator_model": generator_model,
        "verifier_model": verifier_model,
        "generator_token_count": None,
        "verifier_token_count": None,
        "decoding_parameters": result.metadata,
    }
