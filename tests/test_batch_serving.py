import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.serving.batch import (
    run_generation_requests,
    score_preference_pairs,
)
from ttc_dense_verifier.serving.clients import Candidate, OpenAICompatibleGeneratorClient, RuleBasedVerifierClient


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

    def test_run_generation_requests_cli_resume_appends_only_missing_prompts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "requests.jsonl"
            output_path = root / "answers.jsonl"
            input_path.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "prompt_id": prompt_id,
                            "source_prompt": f"Question {prompt_id}",
                            "generation_prompt": "Prompt",
                            "model": "remote-qwen32b",
                            "metadata": {"generation_mode": "positive"},
                        }
                    )
                    for prompt_id in ["p1", "p2"]
                )
                + "\n",
                encoding="utf-8",
            )
            output_path.write_text(
                json.dumps(
                    {
                        "prompt_id": "p1",
                        "kind": "chosen",
                        "text": "Existing answer.",
                        "model": "remote-qwen32b",
                        "metadata": {},
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
                    "New answer.",
                    "--resume",
                    "--progress-every",
                    "1",
                ]
            )

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual([row["prompt_id"] for row in rows], ["p1", "p2"])
            self.assertEqual(rows[0]["text"], "Existing answer.")
            self.assertEqual(rows[1]["text"], "New answer.")

    def test_run_generation_requests_cli_resume_supports_concurrency(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "requests.jsonl"
            output_path = root / "answers.jsonl"
            input_path.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "prompt_id": f"p{index}",
                            "source_prompt": f"Question {index}",
                            "generation_prompt": "Prompt",
                            "model": "remote-qwen32b",
                            "metadata": {"generation_mode": "positive"},
                        }
                    )
                    for index in range(1, 5)
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
                    "Concurrent answer.",
                    "--resume",
                    "--concurrency",
                    "4",
                    "--progress-every",
                    "1",
                ]
            )

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual({row["prompt_id"] for row in rows}, {"p1", "p2", "p3", "p4"})
            self.assertTrue(all(row["text"] == "Concurrent answer." for row in rows))

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

    def test_openai_generator_includes_optional_sampling_controls(self):
        client = OpenAICompatibleGeneratorClient(
            "http://generator.example/v1",
            model="Qwen2.5-32B-Instruct",
            max_tokens=192,
            temperature=0.2,
            extra_body={"thinking": {"type": "disabled"}},
        )
        payloads = []
        lock = threading.Lock()

        def fake_urlopen(request, timeout):
            del timeout
            with lock:
                payloads.append(json.loads(request.data.decode("utf-8")))

            class Response:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps({"choices": [{"message": {"content": "answer"}}]}).encode("utf-8")

            return Response()

        import urllib.request

        original_urlopen = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            candidates = client.expand("Prompt", "", 1)
        finally:
            urllib.request.urlopen = original_urlopen

        self.assertEqual(candidates[0].text, "answer")
        self.assertEqual(payloads[0]["max_tokens"], 192)
        self.assertEqual(payloads[0]["temperature"], 0.2)
        self.assertEqual(payloads[0]["thinking"], {"type": "disabled"})
        self.assertEqual(payloads[0]["messages"], [{"role": "user", "content": "Prompt"}])


if __name__ == "__main__":
    unittest.main()
