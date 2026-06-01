from __future__ import annotations

from typing import Any, Literal

from ttc_dense_verifier.decoding.beam_search import BeamSearchConfig, BeamSearchTTC
from ttc_dense_verifier.decoding.mcts import MCTSConfig, MCTSTTC
from ttc_dense_verifier.inference.artifacts import build_inference_record
from ttc_dense_verifier.serving.clients import GeneratorClient, VerifierClient

DecodeMethod = Literal["beam", "mcts"]


def decode_prompts(
    prompts: list[dict[str, Any]],
    *,
    method: DecodeMethod,
    generator: GeneratorClient,
    verifier: VerifierClient,
    generator_model: str,
    verifier_model: str,
    limit: int | None = None,
    beam_config: BeamSearchConfig | None = None,
    mcts_config: MCTSConfig | None = None,
) -> list[dict[str, Any]]:
    selected_prompts = prompts[:limit] if limit is not None else prompts
    decoder = _build_decoder(method, generator, verifier, beam_config, mcts_config)
    records: list[dict[str, Any]] = []
    for index, row in enumerate(selected_prompts, start=1):
        prompt_id = str(row.get("prompt_id", f"prompt-{index:06d}"))
        prompt = str(row["prompt"])
        result = decoder.decode(prompt)
        records.append(
            build_inference_record(
                prompt_id=prompt_id,
                prompt=prompt,
                result=result,
                generator_model=generator_model,
                verifier_model=verifier_model,
            )
        )
    return records


def _build_decoder(
    method: DecodeMethod,
    generator: GeneratorClient,
    verifier: VerifierClient,
    beam_config: BeamSearchConfig | None,
    mcts_config: MCTSConfig | None,
) -> BeamSearchTTC | MCTSTTC:
    if method == "beam":
        return BeamSearchTTC(generator=generator, verifier=verifier, config=beam_config or BeamSearchConfig())
    if method == "mcts":
        return MCTSTTC(generator=generator, verifier=verifier, config=mcts_config or MCTSConfig())
    raise ValueError(f"Unsupported decode method: {method}")
