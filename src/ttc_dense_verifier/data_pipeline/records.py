from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PromptRecord:
    prompt_id: str
    prompt: str
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PromptRecord":
        return cls(
            prompt_id=str(data["prompt_id"]),
            prompt=str(data["prompt"]),
            source=str(data.get("source", "unknown")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AnswerRecord:
    prompt_id: str
    kind: str
    text: str
    model: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AnswerRecord":
        return cls(
            prompt_id=str(data["prompt_id"]),
            kind=str(data.get("kind", "answer")),
            text=str(data.get("text", "")),
            model=str(data.get("model", "unknown")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PreferencePair:
    prompt_id: str
    prompt: str
    chosen: str
    rejected: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PreferencePair":
        return cls(
            prompt_id=str(data["prompt_id"]),
            prompt=str(data["prompt"]),
            chosen=str(data["chosen"]),
            rejected=str(data["rejected"]),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
