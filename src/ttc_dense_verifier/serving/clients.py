from __future__ import annotations

import json
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Candidate:
    text: str
    logprob: float = 0.0
    is_complete: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class GeneratorClient(Protocol):
    def expand(self, prompt: str, prefix: str, count: int) -> list[Candidate]:
        """Return up to count continuations for prompt plus prefix."""


class VerifierClient(Protocol):
    def score(self, prompt: str, answer: str) -> float:
        """Return a scalar verifier reward for a candidate answer."""


class ScriptedGeneratorClient:
    """Deterministic generator for tests, demos, and offline smoke checks."""

    def __init__(self, script: dict[str, list[tuple[str, float, bool] | Candidate]]):
        self._script = script

    def expand(self, prompt: str, prefix: str, count: int) -> list[Candidate]:
        del prompt
        entries = self._script.get(prefix, self._script.get("", []))
        candidates: list[Candidate] = []
        for entry in entries[:count]:
            if isinstance(entry, Candidate):
                candidates.append(entry)
            else:
                text, logprob, is_complete = entry
                candidates.append(Candidate(text=text, logprob=logprob, is_complete=is_complete))
        return candidates


class RuleBasedVerifierClient:
    """Small deterministic verifier used when real reward models are remote."""

    def __init__(self, reward_keywords: list[str] | None = None, penalty_keywords: list[str] | None = None):
        self.reward_keywords = [keyword.lower() for keyword in (reward_keywords or [])]
        self.penalty_keywords = [keyword.lower() for keyword in (penalty_keywords or [])]

    def score(self, prompt: str, answer: str) -> float:
        del prompt
        normalized = answer.lower()
        reward = sum(1.0 for keyword in self.reward_keywords if keyword in normalized)
        penalty = sum(1.0 for keyword in self.penalty_keywords if keyword in normalized)
        length_bonus = min(len(answer.split()) / 100.0, 0.25)
        return reward - penalty + length_bonus


class OpenAICompatibleGeneratorClient:
    """HTTP client for remote vLLM/OpenAI-compatible chat completions.

    This client performs network calls only when explicitly used. It never
    downloads or imports model weights locally.
    """

    def __init__(
        self,
        endpoint: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 60,
        max_tokens: int | None = None,
        temperature: float | None = None,
        extra_body: dict[str, Any] | None = None,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.extra_body = dict(extra_body or {})

    def expand(self, prompt: str, prefix: str, count: int) -> list[Candidate]:
        messages = [{"role": "user", "content": prompt}]
        if prefix:
            messages.append({"role": "assistant", "content": prefix})
        payload = {
            "model": self.model,
            "n": count,
            "messages": messages,
        }
        if self.max_tokens is not None:
            payload["max_tokens"] = self.max_tokens
        if self.temperature is not None:
            payload["temperature"] = self.temperature
        payload.update(self.extra_body)
        request = urllib.request.Request(
            f"{self.endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        candidates: list[Candidate] = []
        for choice in data.get("choices", []):
            message = choice.get("message", {})
            content = str(message.get("content", ""))
            logprob = float(choice.get("logprob", choice.get("logprobs", 0.0)) or 0.0)
            candidates.append(Candidate(text=content, logprob=logprob, is_complete=True))
        return candidates

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


class HTTPVerifierClient:
    """HTTP scalar-score verifier client for remote reward-model services."""

    def __init__(self, endpoint: str, api_key: str | None = None, timeout_seconds: float = 60):
        self.endpoint = endpoint
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def score(self, prompt: str, answer: str) -> float:
        payload = {"prompt": prompt, "answer": answer}
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return float(data["score"])

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
