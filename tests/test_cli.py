import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main


class CLITests(unittest.TestCase):
    def test_build_questions_command_writes_taxonomy_questions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "questions.jsonl"

            exit_code = main(["build-questions", "--output", str(output), "--limit", "5"])

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 5)
            self.assertEqual(rows[0]["prompt_id"], "taxonomy-000001")
            self.assertEqual(rows[0]["source"], "c_system_taxonomy")

    def test_prepare_preferences_command_writes_split_files_and_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            questions = root / "questions.jsonl"
            positive = root / "positive.jsonl"
            negative = root / "negative.jsonl"
            output = root / "preference"
            questions.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "prompt_id": f"p{i}",
                            "prompt": f"Explain C topic {i}.",
                            "source": "unit-test",
                            "metadata": {"topic": "c"},
                        }
                    )
                    for i in range(10)
                )
                + "\n",
                encoding="utf-8",
            )
            positive.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "prompt_id": f"p{i}",
                            "kind": "chosen",
                            "text": f"Clear answer with assumptions and boundary conditions {i}.",
                            "model": "remote-qwen32b",
                        }
                    )
                    for i in range(10)
                )
                + "\n",
                encoding="utf-8",
            )
            negative.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "prompt_id": f"p{i}",
                            "kind": "rejected",
                            "text": f">>> noisy slogan answer {i} ===>",
                            "model": "remote-qwen14b",
                            "metadata": {"defect": "symbol_noise"},
                        }
                    )
                    for i in range(10)
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "prepare-preferences",
                    "--questions",
                    str(questions),
                    "--positive",
                    str(positive),
                    "--negative",
                    str(negative),
                    "--output-dir",
                    str(output),
                    "--seed",
                    "3",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(len((output / "train_preference.jsonl").read_text(encoding="utf-8").splitlines()), 8)
            self.assertEqual(len((output / "val_preference.jsonl").read_text(encoding="utf-8").splitlines()), 1)
            self.assertEqual(len((output / "test_prompts.jsonl").read_text(encoding="utf-8").splitlines()), 1)
            self.assertIn("kept_pairs: 10", (output / "data_report.md").read_text(encoding="utf-8"))

    def test_evaluate_static_metrics_command_writes_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inputs = root / "outputs.jsonl"
            output = root / "tables"
            inputs.write_text(
                "\n".join(
                    [
                        json.dumps({"prompt_id": "p1", "method": "raw", "answer": ">>> slogan ===>"}),
                        json.dumps({"prompt_id": "p2", "method": "ttc_beam", "answer": "Structured answer."}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(["evaluate-static", "--input", str(inputs), "--output-dir", str(output)])

            self.assertEqual(exit_code, 0)
            summary = json.loads((output / "static_metrics_summary.json").read_text(encoding="utf-8"))
            self.assertGreater(summary["raw"]["abnormal_symbol_count_mean"], 0)
            self.assertEqual(summary["ttc_beam"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
