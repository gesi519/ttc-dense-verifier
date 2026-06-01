import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.training.sft_dataset import to_sft_record
from ttc_dense_verifier.training.validation import validate_verifier_scores


class TrainingValidationTests(unittest.TestCase):
    def test_validate_verifier_scores_reports_pairwise_accuracy_and_bias_checks(self):
        rows = [
            {
                "prompt_id": "p1",
                "chosen": "Clear answer with assumptions.",
                "rejected": ">>> noisy slogan",
                "chosen_score": 3.0,
                "rejected_score": -1.0,
            },
            {
                "prompt_id": "p2",
                "chosen": "Structured answer with boundary conditions.",
                "rejected": "Bad answer ===>",
                "chosen_score": 2.5,
                "rejected_score": 0.0,
            },
            {
                "prompt_id": "p3",
                "chosen": "Correct but concise.",
                "rejected": "Incorrect answer.",
                "chosen_score": 0.5,
                "rejected_score": 1.0,
            },
        ]

        report = validate_verifier_scores(rows, min_pairwise_accuracy=0.65)

        self.assertAlmostEqual(report["pairwise_accuracy"], 2 / 3)
        self.assertEqual(report["passed_min_accuracy"], True)
        self.assertAlmostEqual(report["mean_margin"], 2.0)
        self.assertIn("length_score_correlation", report)
        self.assertIn("markdown_score_correlation", report)
        self.assertEqual(len(report["failures"]), 1)

    def test_to_sft_record_uses_positive_answer_only(self):
        pair = {
            "prompt_id": "p1",
            "prompt": "Explain stack versus heap.",
            "chosen": "Stack and heap differ by lifetime and allocation.",
            "rejected": ">>> shallow answer",
            "metadata": {"topic": "memory"},
        }

        record = to_sft_record(pair)

        self.assertEqual(record["instruction"], "Explain stack versus heap.")
        self.assertEqual(record["input"], "")
        self.assertEqual(record["output"], "Stack and heap differ by lifetime and allocation.")
        self.assertEqual(record["metadata"]["prompt_id"], "p1")
        self.assertNotIn("rejected", record)

    def test_export_sft_dataset_cli_writes_positive_side_jsonl(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "train_preference.jsonl"
            output_path = root / "sft.jsonl"
            input_path.write_text(
                json.dumps(
                    {
                        "prompt_id": "p1",
                        "prompt": "Explain memcpy versus memmove.",
                        "chosen": "Use memmove when ranges overlap.",
                        "rejected": ">>> memcpy always safe",
                        "metadata": {"topic": "string.h"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(["export-sft-dataset", "--input", str(input_path), "--output", str(output_path)])

            self.assertEqual(exit_code, 0)
            rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(rows[0]["output"], "Use memmove when ranges overlap.")
            self.assertNotIn("rejected", rows[0])

    def test_validate_verifier_scores_cli_writes_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "scores.jsonl"
            output_path = root / "verifier_report.json"
            input_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "prompt_id": "p1",
                                "chosen": "Clear answer.",
                                "rejected": ">>> noisy",
                                "chosen_score": 2,
                                "rejected_score": -1,
                            }
                        ),
                        json.dumps(
                            {
                                "prompt_id": "p2",
                                "chosen": "Another clear answer.",
                                "rejected": "bad ===>",
                                "chosen_score": 1,
                                "rejected_score": 0,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "validate-verifier-scores",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--min-pairwise-accuracy",
                    "0.65",
                ]
            )

            self.assertEqual(exit_code, 0)
            report = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(report["pairwise_accuracy"], 1.0)
            self.assertEqual(report["passed_min_accuracy"], True)


if __name__ == "__main__":
    unittest.main()
