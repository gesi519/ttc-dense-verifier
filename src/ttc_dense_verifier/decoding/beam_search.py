from __future__ import annotations

import time
from dataclasses import dataclass

from ttc_dense_verifier.decoding.types import BeamStepTrace, Branch, DecodingResult
from ttc_dense_verifier.serving.clients import GeneratorClient, VerifierClient


@dataclass(frozen=True)
class BeamSearchConfig:
    beam_width: int = 4
    expansions_per_step: int = 4
    beta: float = 1.0
    max_steps: int = 8

    def __post_init__(self) -> None:
        if self.beam_width < 1:
            raise ValueError("beam_width must be at least 1")
        if self.expansions_per_step < 1:
            raise ValueError("expansions_per_step must be at least 1")
        if self.max_steps < 1:
            raise ValueError("max_steps must be at least 1")


class BeamSearchTTC:
    def __init__(self, generator: GeneratorClient, verifier: VerifierClient, config: BeamSearchConfig | None = None):
        self.generator = generator
        self.verifier = verifier
        self.config = config or BeamSearchConfig()

    def decode(self, prompt: str) -> DecodingResult:
        started = time.perf_counter()
        beams = [Branch(text="", generator_logprob=0.0, verifier_reward=0.0, total_score=0.0)]
        traces: list[BeamStepTrace] = []
        verifier_calls = 0

        for step_index in range(self.config.max_steps):
            candidates: list[Branch] = []
            for beam in beams:
                if beam.is_complete:
                    candidates.append(beam)
                    continue
                expansions = self.generator.expand(prompt, beam.text, self.config.expansions_per_step)
                if not expansions:
                    candidates.append(
                        Branch(
                            text=beam.text,
                            generator_logprob=beam.generator_logprob,
                            verifier_reward=beam.verifier_reward,
                            total_score=beam.total_score,
                            is_complete=True,
                            metadata={**beam.metadata, "stopped_reason": "no_expansions"},
                        )
                    )
                    continue
                for candidate in expansions:
                    text = beam.text + candidate.text
                    generator_logprob = beam.generator_logprob + candidate.logprob
                    verifier_reward = self.verifier.score(prompt, text)
                    verifier_calls += 1
                    total_score = generator_logprob + self.config.beta * verifier_reward
                    candidates.append(
                        Branch(
                            text=text,
                            generator_logprob=generator_logprob,
                            verifier_reward=verifier_reward,
                            total_score=total_score,
                            is_complete=candidate.is_complete,
                            metadata=candidate.metadata,
                        )
                    )

            ranked = sorted(candidates, key=lambda branch: branch.total_score, reverse=True)
            kept = ranked[: self.config.beam_width]
            pruned = ranked[self.config.beam_width :]
            traces.append(BeamStepTrace(step_index=step_index, candidates=ranked, kept=kept, pruned=pruned))
            beams = kept
            if beams and all(beam.is_complete for beam in beams):
                break

        final_branch = max(beams, key=lambda branch: branch.total_score)
        latency_ms = (time.perf_counter() - started) * 1000.0
        return DecodingResult(
            prompt=prompt,
            final_answer=final_branch.text.strip(),
            final_score=final_branch.total_score,
            method="ttc_beam",
            verifier_call_count=verifier_calls,
            latency_ms=latency_ms,
            steps=traces,
            branches=beams,
            metadata={
                "beam_width": self.config.beam_width,
                "expansions_per_step": self.config.expansions_per_step,
                "beta": self.config.beta,
                "max_steps": self.config.max_steps,
            },
        )
