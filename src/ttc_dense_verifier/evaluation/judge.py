from __future__ import annotations

from typing import Any

JUDGE_DIMENSIONS = (
    "academic_rigor",
    "factual_density",
    "structure_consistency",
    "style_consistency",
    "logic_continuity",
    "usefulness",
)


def render_judge_prompt(prompt: str, answer: str) -> str:
    dimensions = ", ".join(JUDGE_DIMENSIONS)
    return (
        "You are an independent technical writing judge. Score the answer for "
        f"these dimensions: {dimensions}. Return JSON with each dimension as an integer 1-5 "
        "and a short justification field. Do not compare against hidden references.\n\n"
        f"User prompt:\n{prompt}\n\nCandidate answer:\n{answer}\n"
    )


def build_judge_requests(rows: list[dict[str, Any]], *, judge_model: str) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    for row in rows:
        prompt_id = str(row.get("prompt_id", ""))
        method = str(row.get("method", "unknown"))
        prompt = str(row.get("prompt", ""))
        answer = str(row.get("final_answer", row.get("answer", "")))
        requests.append(
            {
                "request_id": f"{prompt_id}:{method}",
                "prompt_id": prompt_id,
                "model": judge_model,
                "judge_prompt": render_judge_prompt(prompt, answer),
                "metadata": {"method": method},
            }
        )
    return requests
