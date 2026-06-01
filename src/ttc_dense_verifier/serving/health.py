from __future__ import annotations

from typing import Any

from ttc_dense_verifier.serving.clients import HTTPVerifierClient, OpenAICompatibleGeneratorClient


def probe_remote_services(
    *,
    generator_endpoint: str,
    generator_model: str,
    verifier_endpoint: str,
    api_key: str | None = None,
    timeout_seconds: float = 10,
) -> dict[str, Any]:
    generator_report = _probe_generator(
        endpoint=generator_endpoint,
        model=generator_model,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    verifier_report = _probe_verifier(
        endpoint=verifier_endpoint,
        api_key=api_key,
        timeout_seconds=timeout_seconds,
    )
    return {
        "ok": bool(generator_report["ok"] and verifier_report["ok"]),
        "generator": generator_report,
        "verifier": verifier_report,
    }


def _probe_generator(
    *,
    endpoint: str,
    model: str,
    api_key: str | None,
    timeout_seconds: float,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "endpoint": endpoint,
        "model": model,
        "candidate_count": 0,
        "sample": "",
        "error": "",
    }
    try:
        client = OpenAICompatibleGeneratorClient(
            endpoint=endpoint,
            model=model,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )
        candidates = client.expand(
            prompt="Reply with a short technical acknowledgement.",
            prefix="",
            count=1,
        )
        report["candidate_count"] = len(candidates)
        report["sample"] = candidates[0].text if candidates else ""
        report["ok"] = bool(candidates and candidates[0].text)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report


def _probe_verifier(*, endpoint: str, api_key: str | None, timeout_seconds: float) -> dict[str, Any]:
    report: dict[str, Any] = {
        "ok": False,
        "endpoint": endpoint,
        "score": None,
        "error": "",
    }
    try:
        client = HTTPVerifierClient(endpoint=endpoint, api_key=api_key, timeout_seconds=timeout_seconds)
        score = client.score(
            prompt="Explain memcpy versus memmove.",
            answer="Use memmove when memory ranges overlap.",
        )
        report["score"] = score
        report["ok"] = isinstance(score, float)
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    return report
