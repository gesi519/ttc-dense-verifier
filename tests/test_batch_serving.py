import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.serving.batch import (
    run_generation_requests,
    score_preference_pairs,
)
from ttc_dense_verifier.serving.clients import Candidate, RuleBasedVerifierClient


class FakeGenerator:
    def expand(self, prompt: str, prefix: str, count: int) -> list[Candidate]:
        del prefix, count
        return [Candidate(text=f"Generated answer for: {prompt.splitlines()[-1]}", logprob=-0.2, is_complete=True)]


class BatchServingTests(unittest.TestCase):
    def test_run_generation_requests_maps_positive_mode_to_chosen_answer_records(self):
        requests = [
            {
                "prompt_id": "p1",
                "source_prompt": "Explain stack versus heap.",
                "generation_prompt": "Write a high-quality answer.\n\nUser question:\nExplain stack versus heap.",
                "model": "remote-qwen32b",
                "metadata": {"generation_mode": "positive", "topic": "memory"},
            }
        ]

        records = run_generation_requests(requests, generator=FakeGenerator())

        self.assertEqual(records[0]["prompt_id"], "p1")
        self.assertEqual(records[0]["kind"], "chosen")
        self.assertEqual(records[0]["model"], "remote-qwen32b")
        self.assertIn("Generated answer", records[0]["text"])
        self.assertEqual(records[0]["metadata"]["generation_mode"], "positive")
        self.assertEqual(records[0]["metadata"]["source_prompt"], "Explain stack versus heap.")

    def test_run_generation_requests_maps_negative_mode_to_rejected_answer_records(self):
        requests = [
            {
                "prompt_id": "p1",
                "source_prompt": "Explain memcpy versus memmove.",
                "generation_prompt": "Write a controlled low-quality answer.",
                "model": "remote-qwen32b",
                "metadata": {"generation_mode": "negative"},
            }
        ]

        records = run_generation_requests(requests, generator=FakeGenerator())

        self.assertEqual(records[0]["kind"], "rejected")

    def test_score_preference_pairs_scores_chosen_and_rejected_answers(self):
        pairs = [
            {
                "prompt_id": "p1",
                "prompt": "Explain memcpy versus memmove.",
                "chosen": "Use memmove when ranges overlap and state assumptions.",
                "rejected": ">>> memcpy is always safe slogan.",
                "metadata": {"topic": "string.h"},
            }
        ]
        verifier = RuleBasedVerifierClient(
            reward_keywords=["memmove", "assumptions"],
            penalty_keywords=[">>>", "always safe", "slogan"],
        )

        scores = score_preference_pairs(pairs, verifier=verifier)

        self.assertEqual(scores[0]["prompt_id"], "p1")
        self.assertGreater(scores[0]["chosen_score"], scores[0]["rejected_score"])
        self.assertEqual(scores[0]["metadata"]["topic"], "string.h")

    def test_run_generation_requests_cli_supports_scripted_answer_without_network(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "requests.jsonl"
            output_path = root / "answers.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "prompt_id": "p1",
                        "source_prompt": "Explain stack versus heap.",
                        "generation_prompt": "Prompt",
                        "model": "remote-qwen32b",
                        "metadata": {"generation_mode": "positive"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "run-generation-requests",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--scripted-answer",
                    "Local smoke answer.",
                ]
            )

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["kind"], "chosen")
            self.assertEqual(rows[0]["text"], "Local smoke answer.")

    def test_score_preferences_cli_supports_rule_based_smoke_verifier(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "pairs.jsonl"
            output_path = root / "scores.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "prompt_id": "p1",
                        "prompt": "Explain undefined behavior.",
                        "chosen": "State assumptions and boundary conditions.",
                        "rejected": ">>> slogan.",
                        "metadata": {"topic": "c"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "score-preferences",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--reward-keyword",
                    "assumptions",
                    "--penalty-keyword",
                    ">>>",
                ]
            )

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertGreater(rows[0]["chosen_score"], rows[0]["rejected_score"])


if __name__ == "__main__":
    unittest.main()
