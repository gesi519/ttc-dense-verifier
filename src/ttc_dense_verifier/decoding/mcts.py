from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from ttc_dense_verifier.decoding.types import Branch, DecodingResult
from ttc_dense_verifier.serving.clients import GeneratorClient, VerifierClient


@dataclass(frozen=True)
class MCTSConfig:
    expansions_per_node: int = 4
    simulation_budget: int = 32
    exploration_weight: float = 1.4
    beta: float = 1.0

    def __post_init__(self) -> None:
        if self.expansions_per_node < 1:
            raise ValueError("expansions_per_node must be at least 1")
        if self.simulation_budget < 1:
            raise ValueError("simulation_budget must be at least 1")


@dataclass
class _Node:
    text: str
    generator_logprob: float = 0.0
    verifier_reward: float = 0.0
    total_score: float = 0.0
    is_complete: bool = False
    visits: int = 0
    value_sum: float = 0.0
    children: list["_Node"] = field(default_factory=list)

    @property
    def average_value(self) -> float:
        if self.visits == 0:
            return self.total_score
        return self.value_sum / self.visits


class MCTSTTC:
    def __init__(self, generator: GeneratorClient, verifier: VerifierClient, config: MCTSConfig | None = None):
        self.generator = generator
        self.verifier = verifier
        self.config = config or MCTSConfig()

    def decode(self, prompt: str) -> DecodingResult:
        started = time.perf_counter()
        root = _Node(text="")
        verifier_calls = self._expand(prompt, root)

        if not root.children:
            return DecodingResult(
                prompt=prompt,
                final_answer="",
                final_score=0.0,
                method="ttc_mcts",
                verifier_call_count=verifier_calls,
                latency_ms=(time.perf_counter() - started) * 1000.0,
            )

        for _ in range(self.config.simulation_budget):
            node = self._select(root)
            if not node.is_complete and not node.children:
                verifier_calls += self._expand(prompt, node)
            reward = node.total_score if not node.children else max(child.total_score for child in node.children)
            node.visits += 1
            node.value_sum += reward

        best = max(root.children, key=lambda child: (child.average_value, child.total_score))
        branches = [
            Branch(
                text=child.text,
                generator_logprob=child.generator_logprob,
                verifier_reward=child.verifier_reward,
                total_score=child.total_score,
                is_complete=child.is_complete,
                metadata={"visits": child.visits, "average_value": child.average_value},
            )
            for child in root.children
        ]
        return DecodingResult(
            prompt=prompt,
            final_answer=best.text.strip(),
            final_score=best.total_score,
            method="ttc_mcts",
            verifier_call_count=verifier_calls,
            latency_ms=(time.perf_counter() - started) * 1000.0,
            branches=branches,
            metadata={
                "expansions_per_node": self.config.expansions_per_node,
                "simulation_budget": self.config.simulation_budget,
                "exploration_weight": self.config.exploration_weight,
            },
        )

    def _expand(self, prompt: str, node: _Node) -> int:
        calls = 0
        expansions = self.generator.expand(prompt, node.text, self.config.expansions_per_node)
        for candidate in expansions:
            text = node.text + candidate.text
            generator_logprob = node.generator_logprob + candidate.logprob
            verifier_reward = self.verifier.score(prompt, text)
            calls += 1
            total_score = generator_logprob + self.config.beta * verifier_reward
            node.children.append(
                _Node(
                    text=text,
                    generator_logprob=generator_logprob,
                    verifier_reward=verifier_reward,
                    total_score=total_score,
                    is_complete=candidate.is_complete,
                )
            )
        return calls

    def _select(self, root: _Node) -> _Node:
        total_visits = max(1, sum(child.visits for child in root.children))

        def ucb(child: _Node) -> float:
            if child.visits == 0:
                return float("inf")
            exploration = self.config.exploration_weight * math.sqrt(math.log(total_visits + 1) / child.visits)
            return child.average_value + exploration

        return max(root.children, key=ucb)
