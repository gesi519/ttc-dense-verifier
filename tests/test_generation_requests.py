import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.data_pipeline.generation_prompts import (
    build_generation_requests,
    render_generation_prompt,
)
from ttc_dense_verifier.data_pipeline.records import PromptRecord


class GenerationRequestTests(unittest.TestCase):
    def test_negative_prompt_includes_controlled_defects_without_changing_question(self):
        prompt = PromptRecord(
            prompt_id="p1",
            prompt="Explain memcpy versus memmove.",
            source="taxonomy",
            metadata={"topic": "string.h"},
        )

        rendered = render_generation_prompt(prompt, mode="negative")

        self.assertIn("Explain memcpy versus memmove.", rendered)
        self.assertIn("controlled low-quality answer", rendered)
        self.assertIn("symbol noise", rendered)
        self.assertIn("❌", rendered)
        self.assertIn("✅", rendered)
        self.assertIn("⚠️", rendered)
        self.assertIn(">>>", rendered)
        self.assertIn("==>", rendered)
        self.assertIn("hollow slogans", rendered)
        self.assertIn("grand generic conclusions", rendered)
        self.assertIn("unsupported technical assertions", rendered)
        self.assertIn("stack jargon", rendered)
        self.assertIn("underlying mechanism", rendered)
        self.assertIn("unprofessional code-explanation style", rendered)
        self.assertIn("secondary defect", rendered)
        self.assertIn("logic gaps, symbol abuse, and missing concepts as the main defects", rendered)
        self.assertIn("explaining its parameters", rendered)
        self.assertIn("return value", rendered)
        self.assertIn("side effects", rendered)
        self.assertIn("why each argument matters", rendered)
        self.assertIn("function names, APIs, flags, or parameters", rendered)
        self.assertIn("how they change behavior", rendered)
        self.assertIn("broken heading levels", rendered)
        self.assertIn("numbering jumps", rendered)
        self.assertIn("conclusions before causes", rendered)
        self.assertIn("causal chain", rendered)

    def test_positive_prompt_requests_rigorous_answer(self):
        prompt = PromptRecord(
            prompt_id="p1",
            prompt="Explain undefined behavior in C.",
            source="taxonomy",
        )

        rendered = render_generation_prompt(prompt, mode="positive")

        self.assertIn("high-quality technical answer", rendered)
        self.assertIn("explicit assumptions", rendered)
        self.assertIn("boundary conditions", rendered)
        self.assertIn("professional code-explanation style", rendered)
        self.assertIn("without decorative status symbols or noisy separators", rendered)
        self.assertIn("introduce each relevant function, API, flag, and parameter", rendered)
        self.assertIn("parameter roles", rendered)
        self.assertIn("return values", rendered)
        self.assertIn("side effects", rendered)
        self.assertIn("underlying mechanism in the code path", rendered)
        self.assertIn("how arguments, flags, or call ordering change program behavior", rendered)
        self.assertIn("language or library guarantees", rendered)
        self.assertIn("why the fix works", rendered)
        self.assertNotIn("symbol noise", rendered)

    def test_build_generation_requests_preserves_prompt_metadata(self):
        prompts = [
            PromptRecord("p1", "Explain stack versus heap.", "taxonomy", {"topic": "memory"}),
            PromptRecord("p2", "Explain pthread mutex deadlock.", "taxonomy", {"topic": "pthread"}),
        ]

        requests = build_generation_requests(prompts, mode="negative", model="remote-qwen32b")

        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["prompt_id"], "p1")
        self.assertEqual(requests[0]["model"], "remote-qwen32b")
        self.assertEqual(requests[0]["metadata"]["topic"], "memory")
        self.assertEqual(requests[0]["metadata"]["generation_mode"], "negative")

    def test_build_generation_requests_cli_writes_jsonl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            questions = root / "questions.jsonl"
            output = root / "requests.jsonl"
            questions.write_text(
                json.dumps(
                    {
                        "prompt_id": "p1",
                        "prompt": "Explain stack versus heap.",
                        "source": "unit-test",
                        "metadata": {"topic": "memory"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "build-generation-requests",
                    "--questions",
                    str(questions),
                    "--mode",
                    "positive",
                    "--model",
                    "remote-qwen32b",
                    "--output",
                    str(output),
                ]
            )

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["prompt_id"], "p1")
            self.assertEqual(rows[0]["metadata"]["generation_mode"], "positive")
            self.assertIn("high-quality technical answer", rows[0]["generation_prompt"])


if __name__ == "__main__":
    unittest.main()
