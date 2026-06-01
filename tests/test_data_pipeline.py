import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.data_pipeline.records import AnswerRecord, PromptRecord
from ttc_dense_verifier.data_pipeline.preference import (
    build_preference_pairs,
    split_by_prompt_id,
)
from ttc_dense_verifier.data_pipeline.taxonomy import build_taxonomy_prompts
from ttc_dense_verifier.utils.jsonl import read_jsonl, write_jsonl


class DataPipelineTests(unittest.TestCase):
    def test_build_taxonomy_prompts_creates_stable_c_system_questions(self):
        prompts = build_taxonomy_prompts(limit=6)

        self.assertEqual(len(prompts), 6)
        self.assertEqual(prompts[0].prompt_id, "taxonomy-000001")
        self.assertTrue(all(prompt.source == "c_system_taxonomy" for prompt in prompts))
        self.assertTrue(any("memcpy" in prompt.prompt or "memmove" in prompt.prompt for prompt in prompts))
        self.assertTrue(any(prompt.metadata["task_type"] == "debugging" for prompt in prompts))

    def test_build_taxonomy_prompts_avoids_duplicate_prompt_text_for_target_scale(self):
        prompts = build_taxonomy_prompts(limit=200)

        self.assertEqual(len({prompt.prompt for prompt in prompts}), 200)

    def test_build_preference_pairs_filters_invalid_pairs_and_preserves_metadata(self):
        prompts = [
            PromptRecord(
                prompt_id="p1",
                prompt="Explain memcpy versus memmove under overlap.",
                source="taxonomy",
                metadata={"topic": "string.h"},
            ),
            PromptRecord(
                prompt_id="p2",
                prompt="Explain stack versus heap.",
                source="taxonomy",
                metadata={"topic": "memory"},
            ),
            PromptRecord(
                prompt_id="p3",
                prompt="Explain undefined behavior.",
                source="taxonomy",
                metadata={"topic": "c"},
            ),
        ]
        chosen = [
            AnswerRecord("p1", "chosen", "Use memmove for overlapping ranges because it preserves bytes.", "qwen32b"),
            AnswerRecord("p2", "chosen", "Stack and heap have different lifetimes and allocation rules.", "qwen32b"),
            AnswerRecord("p3", "chosen", "Undefined behavior means the C standard imposes no requirements.", "qwen32b"),
        ]
        rejected = [
            AnswerRecord("p1", "rejected", ">>> memcpy is always fine!!!", "qwen14b", {"defect": "symbol_noise"}),
            AnswerRecord("p2", "rejected", "Stack and heap have different lifetimes and allocation rules.", "qwen14b"),
            AnswerRecord("p3", "rejected", "", "qwen14b"),
        ]

        pairs, report = build_preference_pairs(prompts, chosen, rejected, similarity_threshold=0.92)

        self.assertEqual([pair.prompt_id for pair in pairs], ["p1"])
        self.assertEqual(pairs[0].metadata["topic"], "string.h")
        self.assertEqual(pairs[0].metadata["chosen_model"], "qwen32b")
        self.assertEqual(pairs[0].metadata["rejected_model"], "qwen14b")
        self.assertEqual(pairs[0].metadata["defect"], "symbol_noise")
        self.assertEqual(report.total_prompts, 3)
        self.assertEqual(report.kept_pairs, 1)
        self.assertEqual(report.dropped_near_duplicate, 1)
        self.assertEqual(report.dropped_empty, 1)

    def test_split_by_prompt_id_is_deterministic_and_keeps_prompt_ids_disjoint(self):
        pairs = [
            {
                "prompt_id": f"p{i}",
                "prompt": f"Prompt {i}",
                "chosen": f"Chosen {i}",
                "rejected": f"Rejected {i}",
                "metadata": {},
            }
            for i in range(10)
        ]

        first = split_by_prompt_id(pairs, train_ratio=0.8, val_ratio=0.1, seed=7)
        second = split_by_prompt_id(pairs, train_ratio=0.8, val_ratio=0.1, seed=7)

        self.assertEqual(first, second)
        self.assertEqual(len(first["train"]), 8)
        self.assertEqual(len(first["val"]), 1)
        self.assertEqual(len(first["test"]), 1)
        train_ids = {item["prompt_id"] for item in first["train"]}
        val_ids = {item["prompt_id"] for item in first["val"]}
        test_ids = {item["prompt_id"] for item in first["test"]}
        self.assertTrue(train_ids.isdisjoint(val_ids))
        self.assertTrue(train_ids.isdisjoint(test_ids))
        self.assertTrue(val_ids.isdisjoint(test_ids))

    def test_jsonl_round_trip_creates_parent_directories(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "nested" / "records.jsonl"
            records = [{"id": "a", "value": 1}, {"id": "b", "value": 2}]

            write_jsonl(path, records)

            self.assertEqual(read_jsonl(path), records)
            raw_lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual([json.loads(line)["id"] for line in raw_lines], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
