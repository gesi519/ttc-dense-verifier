from __future__ import annotations

from dataclasses import dataclass

from ttc_dense_verifier.data_pipeline.records import PromptRecord


@dataclass(frozen=True)
class TaxonomyTopic:
    name: str
    concepts: tuple[str, ...]


TASK_TEMPLATES: tuple[tuple[str, str], ...] = (
    (
        "explanation",
        "Explain {concept} in C or systems programming. State assumptions, boundary conditions, and one concise example.",
    ),
    (
        "debugging",
        "Debug a likely failure involving {concept}. Identify the root cause, the unsafe assumption, and a corrected approach.",
    ),
    (
        "code_review",
        "Review a C code snippet that uses {concept}. List correctness risks, portability concerns, and test cases.",
    ),
    (
        "performance",
        "Analyze the performance implications of {concept}. Separate guaranteed behavior from implementation-dependent behavior.",
    ),
)

SCENARIOS: tuple[str, ...] = (
    "for a junior systems-programming student",
    "for a production incident review",
    "for a codebase migration from Linux to another POSIX-like system",
    "for a strict exam answer",
    "for a benchmark-analysis discussion",
    "for a library API design review",
    "for a static analyzer warning triage",
    "for a security audit note",
    "for a debugging checklist",
    "for a concise lecture slide explanation",
    "for a pull-request review comment",
    "for a postmortem of an intermittent bug",
)

OUTPUT_REQUIREMENTS: tuple[str, ...] = (
    "Use Markdown headings and avoid unsupported claims.",
    "Include one minimal C snippet and explain its limitation.",
    "Separate standard-guaranteed behavior from implementation details.",
    "Name at least two tests that would expose the issue.",
    "Explain the causal chain before giving the final recommendation.",
    "Keep the tone academic and avoid slogan-like phrasing.",
)


TOPICS: tuple[TaxonomyTopic, ...] = (
    TaxonomyTopic("string.h", ("memcpy versus memmove", "strncpy truncation", "strlen on non-terminated buffers")),
    TaxonomyTopic("stdlib.h", ("malloc failure handling", "realloc pointer ownership", "qsort comparator contracts")),
    TaxonomyTopic("stdio.h", ("fread partial reads", "printf format mismatch", "buffered file I/O")),
    TaxonomyTopic("pthread", ("pthread_mutex_lock deadlock", "condition variable wakeups", "data races")),
    TaxonomyTopic("memory", ("stack versus heap lifetime", "buffer overflow", "alignment requirements")),
    TaxonomyTopic("posix", ("file descriptor lifetime", "mmap synchronization", "fork and threads")),
    TaxonomyTopic("undefined_behavior", ("signed integer overflow", "strict aliasing", "use after free")),
    TaxonomyTopic("performance", ("cache locality", "false sharing", "branch prediction")),
)


def build_taxonomy_prompts(limit: int = 5000) -> list[PromptRecord]:
    if limit < 1:
        raise ValueError("limit must be at least 1")

    prompts: list[PromptRecord] = []
    next_id = 1
    for topic in TOPICS:
        for concept in topic.concepts:
            for scenario in SCENARIOS:
                for output_requirement in OUTPUT_REQUIREMENTS:
                    for task_type, template in TASK_TEMPLATES:
                        if len(prompts) >= limit:
                            return prompts
                        prompts.append(
                            PromptRecord(
                                prompt_id=f"taxonomy-{next_id:06d}",
                                prompt=(
                                    f"{template.format(concept=concept)} "
                                    f"Frame the answer {scenario}. {output_requirement}"
                                ),
                                source="c_system_taxonomy",
                                metadata={
                                    "topic": topic.name,
                                    "concept": concept,
                                    "task_type": task_type,
                                    "scenario": scenario,
                                    "output_requirement": output_requirement,
                                },
                            )
                        )
                        next_id += 1
    return prompts
