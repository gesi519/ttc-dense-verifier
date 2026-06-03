from __future__ import annotations

from typing import Any

from ttc_dense_verifier.serving.clients import GeneratorClient, VerifierClient


def run_generation_request(
    request: dict[str, Any],
    *,
    generator: GeneratorClient,
) -> dict[str, Any]:
    metadata = dict(request.get("metadata", {}))
    generation_mode = str(metadata.get("generation_mode", "positive"))
    kind = "chosen" if generation_mode == "positive" else "rejected"
    candidates = generator.expand(str(request["generation_prompt"]), "", 1)
    text = candidates[0].text if candidates else ""
    metadata["source_prompt"] = request.get("source_prompt", "")
    if candidates:
        metadata["generator_logprob"] = candidates[0].logprob
        metadata.update(candidates[0].metadata)
    return {
        "prompt_id": request["prompt_id"],
        "kind": kind,
        "text": text,
        "model": request.get("model", "unknown"),
        "metadata": metadata,
    }


def run_generation_requests(
    requests: list[dict[str, Any]],
    *,
    generator: GeneratorClient,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for request in requests:
        records.append(run_generation_request(request, generator=generator))
    return records


def score_preference_pairs(
    pairs: list[dict[str, Any]],
    *,
    verifier: VerifierClient,
) -> list[dict[str, Any]]:
    scores: list[dict[str, Any]] = []
    for pair in pairs:
        prompt = str(pair["prompt"])
        chosen = str(pair["chosen"])
        rejected = str(pair["rejected"])
        scores.append(
            {
                "prompt_id": pair["prompt_id"],
                "prompt": prompt,
                "chosen": chosen,
                "rejected": rejected,
                "chosen_score": verifier.score(prompt, chosen),
                "rejected_score": verifier.score(prompt, rejected),
                "metadata": dict(pair.get("metadata", {})),
            }
        )
    return scores
