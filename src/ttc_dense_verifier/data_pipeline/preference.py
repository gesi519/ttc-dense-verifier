from __future__ import annotations

import random
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any, Iterable

from ttc_dense_verifier.data_pipeline.records import AnswerRecord, PreferencePair, PromptRecord


@dataclass(frozen=True)
class PreferenceBuildReport:
    total_prompts: int
    kept_pairs: int
    dropped_missing_answer: int
    dropped_empty: int
    dropped_near_duplicate: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = ["# Data Report", ""]
        for key, value in self.to_dict().items():
            lines.append(f"- {key}: {value}")
        lines.append("")
        return "\n".join(lines)


def _index_answers(records: Iterable[AnswerRecord]) -> dict[str, AnswerRecord]:
    indexed: dict[str, AnswerRecord] = {}
    for record in records:
        indexed[record.prompt_id] = record
    return indexed


def _is_empty(text: str) -> bool:
    return not text or not text.strip()


def _similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, left.strip().lower(), right.strip().lower()).ratio()


def build_preference_pairs(
    prompts: Iterable[PromptRecord],
    chosen_answers: Iterable[AnswerRecord],
    rejected_answers: Iterable[AnswerRecord],
    *,
    similarity_threshold: float = 0.94,
) -> tuple[list[PreferencePair], PreferenceBuildReport]:
    chosen_by_prompt = _index_answers(chosen_answers)
    rejected_by_prompt = _index_answers(rejected_answers)
    pairs: list[PreferencePair] = []
    total = 0
    dropped_missing = 0
    dropped_empty = 0
    dropped_duplicate = 0

    for prompt in prompts:
        total += 1
        chosen = chosen_by_prompt.get(prompt.prompt_id)
        rejected = rejected_by_prompt.get(prompt.prompt_id)
        if chosen is None or rejected is None:
            dropped_missing += 1
            continue
        if _is_empty(prompt.prompt) or _is_empty(chosen.text) or _is_empty(rejected.text):
            dropped_empty += 1
            continue
        if _similarity(chosen.text, rejected.text) >= similarity_threshold:
            dropped_duplicate += 1
            continue

        metadata: dict[str, Any] = dict(prompt.metadata)
        metadata.update(
            {
                "source": prompt.source,
                "chosen_model": chosen.model,
                "rejected_model": rejected.model,
            }
        )
        metadata.update(rejected.metadata)
        pairs.append(
            PreferencePair(
                prompt_id=prompt.prompt_id,
                prompt=prompt.prompt,
                chosen=chosen.text,
                rejected=rejected.text,
                metadata=metadata,
            )
        )

    report = PreferenceBuildReport(
        total_prompts=total,
        kept_pairs=len(pairs),
        dropped_missing_answer=dropped_missing,
        dropped_empty=dropped_empty,
        dropped_near_duplicate=dropped_duplicate,
    )
    return pairs, report


def _as_dict(record: PreferencePair | dict[str, Any]) -> dict[str, Any]:
    if isinstance(record, PreferencePair):
        return record.to_dict()
    return dict(record)


def split_by_prompt_id(
    pairs: Iterable[PreferencePair | dict[str, Any]],
    *,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    seed: int = 13,
) -> dict[str, list[dict[str, Any]]]:
    records = [_as_dict(pair) for pair in pairs]
    if not records:
        return {"train": [], "val": [], "test": []}

    prompt_ids = sorted({str(record["prompt_id"]) for record in records})
    random.Random(seed).shuffle(prompt_ids)
    total = len(prompt_ids)
    train_count = int(total * train_ratio)
    val_count = int(total * val_ratio)
    if total >= 3:
        train_count = max(1, min(train_count, total - 2))
        val_count = max(1, min(val_count, total - train_count - 1))
    test_count = total - train_count - val_count
    if test_count < 0:
        raise ValueError("train_ratio and val_ratio leave no room for test records")

    train_ids = set(prompt_ids[:train_count])
    val_ids = set(prompt_ids[train_count : train_count + val_count])
    test_ids = set(prompt_ids[train_count + val_count :])

    splits = {"train": [], "val": [], "test": []}
    for record in records:
        prompt_id = str(record["prompt_id"])
        if prompt_id in train_ids:
            splits["train"].append(record)
        elif prompt_id in val_ids:
            splits["val"].append(record)
        elif prompt_id in test_ids:
            splits["test"].append(record)
    return splits
