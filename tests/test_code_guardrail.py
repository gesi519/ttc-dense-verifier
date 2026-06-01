import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.evaluation.code_guardrail import (
    build_code_guardrail_prompts,
    evaluate_code_guardrail_outputs,
)


class CodeGuardrailTests(unittest.TestCase):
    def test_build_code_guardrail_prompts_creates_c_system_task_set(self):
        prompts = build_code_guardrail_prompts(limit=30)

        self.assertEqual(len(prompts), 30)
        self.assertEqual(prompts[0]["prompt_id"], "guardrail-0001")
        self.assertTrue(all(prompt["source"] == "code_ability_guardrail" for prompt in prompts))
        self.assertTrue(any("memcpy" in prompt["prompt"] for prompt in prompts))
        self.assertTrue(any("pthread" in prompt["prompt"] for prompt in prompts))
        self.assertTrue(all(prompt["metadata"]["expected_keywords"] for prompt in prompts))

    def test_evaluate_code_guardrail_outputs_flags_missing_keywords_and_unsafe_claims(self):
        rows = [
            {
                "prompt_id": "guardrail-0001",
                "method": "ttc_beam",
                "final_answer": "Use memmove when ranges overlap. State assumptions before calling memcpy.",
            },
            {
                "prompt_id": "guardrail-0002",
                "method": "raw",
                "final_answer": "pthread_mutex_lock is always safe and deadlock cannot happen.",
            },
        ]
        prompts = [
            {
                "prompt_id": "guardrail-0001",
                "prompt": "Explain memcpy versus memmove.",
                "metadata": {"expected_keywords": ["memmove", "overlap"], "unsafe_claims": ["always safe"]},
            },
            {
                "prompt_id": "guardrail-0002",
                "prompt": "Analyze pthread deadlock.",
                "metadata": {"expected_keywords": ["deadlock", "mutex"], "unsafe_claims": ["always safe", "cannot happen"]},
            },
        ]

        details, summary = evaluate_code_guardrail_outputs(rows, prompts)

        self.assertEqual(details[0]["missing_keywords"], "")
        self.assertEqual(details[0]["unsafe_claims"], "")
        self.assertEqual(details[1]["missing_keywords"], "mutex")
        self.assertIn("always safe", details[1]["unsafe_claims"])
        self.assertEqual(summary["count"], 2)
        self.assertEqual(summary["passed_count"], 1)
        self.assertEqual(summary["unsafe_claim_count"], 1)

    def test_code_guardrail_cli_writes_prompts_and_evaluation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prompts_path = root / "guardrail_prompts.jsonl"
            outputs_path = root / "outputs.jsonl"
            eval_dir = root / "eval"

            build_exit = main(["build-code-guardrail", "--output", str(prompts_path), "--limit", "3"])
            self.assertEqual(build_exit, 0)

            first_prompt = json.loads(prompts_path.read_text(encoding="utf-8").splitlines()[0])
            outputs_path.write_text(
                json.dumps(
                    {
                        "prompt_id": first_prompt["prompt_id"],
                        "method": "ttc_beam",
                        "final_answer": " ".join(first_prompt["metadata"]["expected_keywords"]),
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            eval_exit = main(
                [
                    "evaluate-code-guardrail",
                    "--prompts",
                    str(prompts_path),
                    "--outputs",
                    str(outputs_path),
                    "--output-dir",
                    str(eval_dir),
                ]
            )

            self.assertEqual(eval_exit, 0)
            self.assertTrue((eval_dir / "code_guardrail_details.csv").exists())
            summary = json.loads((eval_dir / "code_guardrail_summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["count"], 1)
            with (eval_dir / "code_guardrail_details.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["prompt_id"], first_prompt["prompt_id"])


if __name__ == "__main__":
    unittest.main()
