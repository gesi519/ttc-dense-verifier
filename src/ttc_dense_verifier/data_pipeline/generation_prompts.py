from __future__ import annotations

from typing import Literal

from ttc_dense_verifier.data_pipeline.records import PromptRecord

GenerationMode = Literal["negative", "positive"]


NEGATIVE_INSTRUCTIONS = """You are generating training data for a verifier.
Write a controlled low-quality answer to the user's technical question.
The answer should remain on topic, but intentionally include several defects:
- abuse UNIX-style status markers and emoji-like symbols such as ❌, ✅, ⚠️, [OK], or [FAIL] where they do not belong;
- add non-standard symbol noise such as >>>, ==>, ===>, ->->, repeated arrows, or meaningless separators;
- include hollow slogans, grand generic conclusions, or flashy aphorisms instead of precise technical reasoning;
- unsupported technical assertions;
- stack jargon such as cache line, undefined behavior, memory model, ABI, syscall, lock-free, or happens-before without explaining the underlying mechanism;
- use an unprofessional code-explanation style as a secondary defect, while keeping logic gaps, symbol abuse, and missing concepts as the main defects;
- warn about or cite a function before explaining its parameters, return value, side effects, and why each argument matters;
- mention function names, APIs, flags, or parameters without explaining what they do in the code path or how they change behavior;
- make Markdown structure messy with broken heading levels, malformed lists, or numbering jumps such as 1.1 directly to 1.3;
- state conclusions before causes, omit the causal chain, or jump from symptom to fix without explaining why;
- inconsistent academic/casual style.
Do not mention that the answer is intentionally bad."""


POSITIVE_INSTRUCTIONS = """You are generating training data for a verifier.
Write a high-quality technical answer to the user's question.
The answer should include clear definitions, explicit assumptions, causal reasoning,
correct Markdown structure, concise examples, and boundary conditions when relevant.
For code-related questions:
- use professional code-explanation style without decorative status symbols or noisy separators;
- introduce each relevant function, API, flag, and parameter before warning about it or relying on it;
- explain parameter roles, return values, side effects, ownership or lifetime constraints, and error behavior when relevant;
- connect each recommendation to the underlying mechanism in the code path;
- explain how arguments, flags, or call ordering change program behavior;
- distinguish language or library guarantees from implementation details and portability assumptions;
- give enough detail that a reader can understand why the fix works, not just which function name to use.
When the user asks for tests, name concise test cases and expected outcomes; do not write a full test harness unless explicitly requested.
Prefer sections such as Definitions, Assumptions and Boundary Conditions, Causal Mechanism, Example, Limitations, and Recommendation when they fit the question.
When including code:
- ensure every C snippet has sufficient buffer capacity, valid pointer ranges, and no out-of-bounds access;
- make snippets minimal, self-contained, and compilable unless the user explicitly asks for pseudocode;
- explain each snippet's assumptions and limitations immediately after the code block;
- do not present implementation behavior as a language or POSIX guarantee;
- close every Markdown code fence and avoid ending the answer inside a list item, sentence, or code block.
- if a snippet writes past the current string terminator, allocate extra capacity explicitly, such as `char buf[16] = "abcdef";`;
- never use `char buf[] = "..."` in an example that writes beyond the literal's allocated bytes;
- ensure examples that compare `memcpy` and `memmove` do not themselves rely on undefined behavior except in clearly marked non-executed "bad example" snippets;
- never say that `memcpy` copies "as if" through a temporary array; that abstract guarantee belongs to `memmove`;
- when showing string shifts, account for the null terminator and verify the exact printed output from the byte indices;
- if an example shifts only part of a C string, either print a bounded prefix with precision or explain the unchanged suffix in the final string;
- verify copy-direction reasoning: when `dest < src`, forward copying is safe for overlap; when `dest > src`, backward copying is needed for overlap;
- avoid calling runtime undefined behavior "ill-formed"; reserve "ill-formed" for compile-time program formation errors;
- be careful with `n == 0`: state pointer validity assumptions rather than making broad claims about null pointer safety;
- include a short "Limitations" note for every snippet, explicitly naming what the snippet does not prove;
- keep the answer concise enough to finish completely within the token budget while still satisfying the requested details.
Before finalizing the answer, verify that it fully satisfies every output requirement in the user question.
Avoid slogans, unexplained concept insertion, overconfident claims, and conclusion-first reasoning."""


def render_generation_prompt(prompt: PromptRecord, mode: GenerationMode) -> str:
    if mode == "negative":
        instructions = NEGATIVE_INSTRUCTIONS
    elif mode == "positive":
        instructions = POSITIVE_INSTRUCTIONS
    else:
        raise ValueError(f"Unsupported generation mode: {mode}")
    return f"{instructions}\n\nUser question:\n{prompt.prompt}\n"


def build_generation_requests(
    prompts: list[PromptRecord],
    *,
    mode: GenerationMode,
    model: str,
) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    for prompt in prompts:
        metadata = dict(prompt.metadata)
        metadata.update({"source": prompt.source, "generation_mode": mode})
        requests.append(
            {
                "prompt_id": prompt.prompt_id,
                "source_prompt": prompt.prompt,
                "generation_prompt": render_generation_prompt(prompt, mode),
                "model": model,
                "metadata": metadata,
            }
        )
    return requests
