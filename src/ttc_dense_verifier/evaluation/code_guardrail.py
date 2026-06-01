from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

GUARDRAIL_CASES: tuple[dict[str, Any], ...] = (
    {
        "prompt": "Explain when memcpy is unsafe and when memmove is required for overlapping memory ranges.",
        "expected_keywords": ["memcpy", "memmove", "overlap"],
        "unsafe_claims": ["always safe", "overlap does not matter"],
        "topic": "string.h",
    },
    {
        "prompt": "Analyze a pthread_mutex_lock deadlock scenario with two locks acquired in opposite order.",
        "expected_keywords": ["pthread", "mutex", "deadlock"],
        "unsafe_claims": ["cannot happen", "always safe"],
        "topic": "pthread",
    },
    {
        "prompt": "Explain undefined behavior in C without claiming a fixed runtime outcome.",
        "expected_keywords": ["undefined behavior", "standard", "no requirements"],
        "unsafe_claims": ["always crashes", "always works"],
        "topic": "undefined_behavior",
    },
    {
        "prompt": "Review C code that calls realloc and then loses the original pointer on failure.",
        "expected_keywords": ["realloc", "failure", "original pointer"],
        "unsafe_claims": ["cannot fail", "memory is preserved automatically"],
        "topic": "stdlib.h",
    },
    {
        "prompt": "Explain why strlen on a non-null-terminated buffer is dangerous.",
        "expected_keywords": ["strlen", "null", "buffer"],
        "unsafe_claims": ["always bounded", "reads only allocated memory"],
        "topic": "string.h",
    },
    {
        "prompt": "Describe how mmap updates become visible and when msync or munmap matters.",
        "expected_keywords": ["mmap", "msync", "visibility"],
        "unsafe_claims": ["immediately durable", "always synchronized"],
        "topic": "posix",
    },
    {
        "prompt": "Explain stack versus heap lifetime using a function that returns a pointer.",
        "expected_keywords": ["stack", "heap", "lifetime"],
        "unsafe_claims": ["stack pointer remains valid", "heap frees itself"],
        "topic": "memory",
    },
    {
        "prompt": "Review a printf format-string mismatch involving size_t and pointers.",
        "expected_keywords": ["printf", "format", "size_t"],
        "unsafe_claims": ["format does not matter", "compiler fixes it"],
        "topic": "stdio.h",
    },
    {
        "prompt": "Explain strict aliasing and why type-punning through incompatible pointers is risky.",
        "expected_keywords": ["strict aliasing", "pointer", "undefined behavior"],
        "unsafe_claims": ["all casts are safe", "types do not matter"],
        "topic": "undefined_behavior",
    },
    {
        "prompt": "Analyze false sharing in a pthread counter benchmark.",
        "expected_keywords": ["false sharing", "cache", "pthread"],
        "unsafe_claims": ["cache is irrelevant", "threads never interfere"],
        "topic": "performance",
    },
)


def build_code_guardrail_prompts(limit: int = 30) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("limit must be at least 1")
    prompts: list[dict[str, Any]] = []
    index = 1
    while len(prompts) < limit:
        for case in GUARDRAIL_CASES:
            if len(prompts) >= limit:
                break
            prompts.append(
                {
                    "prompt_id": f"guardrail-{index:04d}",
                    "prompt": case["prompt"],
                    "source": "code_ability_guardrail",
        "metadata": {
                        "topic": case["topic"],
                        "task_type": case.get("task_type", "technical_qa"),
                        "expected_keywords": list(case["expected_keywords"]),
                        "unsafe_claims": list(case["unsafe_claims"]),
                    },
                }
            )
            index += 1
    return prompts


def evaluate_code_guardrail_outputs(
    outputs: list[dict[str, Any]],
    prompts: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prompt_by_id = {str(prompt["prompt_id"]): prompt for prompt in prompts}
    details: list[dict[str, Any]] = []
    by_method: dict[str, list[bool]] = defaultdict(list)
    unsafe_count = 0

    for output in outputs:
        prompt_id = str(output["prompt_id"])
        prompt = prompt_by_id[prompt_id]
        metadata = prompt.get("metadata", {})
        answer = str(output.get("final_answer", output.get("answer", "")))
        missing_keywords = [
            keyword for keyword in metadata.get("expected_keywords", []) if not _contains_term(answer, str(keyword))
        ]
        unsafe_claims = [
            phrase for phrase in metadata.get("unsafe_claims", []) if _contains_term(answer, str(phrase))
        ]
        passed = not missing_keywords and not unsafe_claims
        if unsafe_claims:
            unsafe_count += 1
        method = str(output.get("method", "unknown"))
        by_method[method].append(passed)
        details.append(
            {
                "prompt_id": prompt_id,
                "method": method,
                "topic": metadata.get("topic", ""),
                "passed": passed,
                "missing_keywords": ", ".join(missing_keywords),
                "unsafe_claims": ", ".join(unsafe_claims),
                "answer_length": len(answer),
            }
        )

    passed_count = sum(1 for row in details if row["passed"])
    summary = {
        "count": len(details),
        "passed_count": passed_count,
        "pass_rate": passed_count / len(details) if details else 0.0,
        "unsafe_claim_count": unsafe_count,
        "by_method": {
            method: {
                "count": len(values),
                "passed_count": sum(1 for value in values if value),
                "pass_rate": sum(1 for value in values if value) / len(values) if values else 0.0,
            }
            for method, values in sorted(by_method.items())
        },
    }
    return details, summary


def _contains_term(text: str, term: str) -> bool:
    normalized_term = term.strip()
    if not normalized_term:
        return False
    pattern = rf"(?<![A-Za-z0-9_]){re.escape(normalized_term)}(?![A-Za-z0-9_])"
    return re.search(pattern, text, flags=re.IGNORECASE) is not None
