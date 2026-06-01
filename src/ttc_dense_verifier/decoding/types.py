from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Branch:
    text: str
    generator_logprob: float
    verifier_reward: float
    total_score: float
    is_complete: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BeamStepTrace:
    step_index: int
    candidates: list[Branch]
    kept: list[Branch]
    pruned: list[Branch]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DecodingResult:
    prompt: str
    final_answer: str
    final_score: float
    method: str
    verifier_call_count: int
    latency_ms: float
    steps: list[Any] = field(default_factory=list)
    branches: list[Branch] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
