import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.evaluation.judge import build_judge_requests
from ttc_dense_verifier.evaluation.reports import (
    build_error_breakdown,
    build_human_preference_table,
    build_human_review_rows,
    build_latency_table,
    build_overall_table,
)


class EvaluationReportTests(unittest.TestCase):
    def test_build_overall_table_summarizes_method_quality(self):
        rows = [
            {
                "prompt_id": "p1",
                "method": "raw",
                "final_answer": ">>> slogan ===>",
                "verifier_call_count": 0,
                "latency_ms": 10,
            },
            {
                "prompt_id": "p1",
                "method": "ttc_beam",
                "final_answer": "State assumptions and boundary conditions.",
                "verifier_call_count": 2,
                "latency_ms": 25,
            },
        ]

        table = build_overall_table(rows)

        self.assertEqual(table[0]["method"], "raw")
        self.assertEqual(table[0]["count"], 1)
        self.assertGreater(table[0]["abnormal_symbol_count_mean"], table[1]["abnormal_symbol_count_mean"])
        self.assertEqual(table[1]["method"], "ttc_beam")

    def test_build_error_breakdown_and_latency_tables(self):
        rows = [
            {
                "prompt_id": "p1",
                "method": "raw",
                "final_answer": "```c\nint main(void) {return 0;}\n",
                "verifier_call_count": 0,
                "latency_ms": 10,
            },
            {
                "prompt_id": "p2",
                "method": "ttc_beam",
                "final_answer": "Clean answer.",
                "verifier_call_count": 4,
                "latency_ms": 30,
            },
        ]

        error_table = build_error_breakdown(rows)
        latency_table = build_latency_table(rows)

        self.assertEqual(error_table[0]["method"], "raw")
        self.assertEqual(error_table[0]["code_fence_mismatch_total"], 1)
        self.assertEqual(latency_table[1]["method"], "ttc_beam")
        self.assertEqual(latency_table[1]["verifier_call_count_mean"], 4)
        self.assertEqual(latency_table[1]["latency_ms_mean"], 30)

    def test_build_judge_requests_contains_structured_scoring_instruction(self):
        rows = [
            {
                "prompt_id": "p1",
                "method": "ttc_beam",
                "prompt": "Explain memcpy versus memmove.",
                "final_answer": "Use memmove when memory ranges overlap.",
            }
        ]

        requests = build_judge_requests(rows, judge_model="remote-judge")

        self.assertEqual(requests[0]["model"], "remote-judge")
        self.assertIn("academic_rigor", requests[0]["judge_prompt"])
        self.assertIn("JSON", requests[0]["judge_prompt"])
        self.assertEqual(requests[0]["metadata"]["method"], "ttc_beam")

    def test_build_human_review_rows_creates_one_row_per_prompt_with_methods(self):
        rows = [
            {"prompt_id": "p1", "method": "raw", "prompt": "Q1", "final_answer": "A raw"},
            {"prompt_id": "p1", "method": "ttc_beam", "prompt": "Q1", "final_answer": "A beam"},
            {"prompt_id": "p2", "method": "raw", "prompt": "Q2", "final_answer": "B raw"},
        ]

        review_rows = build_human_review_rows(rows)

        self.assertEqual(len(review_rows), 2)
        self.assertEqual(review_rows[0]["prompt_id"], "p1")
        self.assertEqual(review_rows[0]["raw_answer"], "A raw")
        self.assertEqual(review_rows[0]["ttc_beam_answer"], "A beam")
        self.assertIn("best_method", review_rows[0])

    def test_build_human_preference_table_summarizes_review_votes_and_ttc_flags(self):
        review_rows = [
            {
                "prompt_id": "p1",
                "best_method": "ttc_beam",
                "ttc_removes_visible_defects": "yes",
                "ttc_loses_useful_information": "no",
                "verifier_over_penalizes_valid_wording": "no",
            },
            {
                "prompt_id": "p2",
                "best_method": "raw",
                "ttc_removes_visible_defects": "yes",
                "ttc_loses_useful_information": "yes",
                "verifier_over_penalizes_valid_wording": "no",
            },
            {
                "prompt_id": "p3",
                "best_method": "",
                "ttc_removes_visible_defects": "yes",
                "ttc_loses_useful_information": "no",
                "verifier_over_penalizes_valid_wording": "yes",
            },
        ]

        table = build_human_preference_table(review_rows)

        self.assertEqual([row["method"] for row in table], ["raw", "ttc_beam"])
        self.assertEqual(table[0]["reviewed_count"], 2)
        self.assertEqual(table[0]["best_count"], 1)
        self.assertEqual(table[0]["preference_rate"], 0.5)
        self.assertEqual(table[1]["best_count"], 1)
        self.assertEqual(table[1]["ttc_removes_visible_defects_yes_rate"], 1.0)
        self.assertEqual(table[1]["ttc_loses_useful_information_yes_rate"], 0.5)
        self.assertEqual(table[1]["verifier_over_penalizes_valid_wording_yes_rate"], 0.0)

    def test_export_evaluation_assets_cli_writes_tables_and_review_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "outputs.jsonl"
            output_dir = root / "eval"
            input_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "prompt_id": "p1",
                                "method": "raw",
                                "prompt": "Explain stack versus heap.",
                                "final_answer": ">>> slogan ===>",
                                "latency_ms": 10,
                                "verifier_call_count": 0,
                            }
                        ),
                        json.dumps(
                            {
                                "prompt_id": "p1",
                                "method": "ttc_beam",
                                "prompt": "Explain stack versus heap.",
                                "final_answer": "State assumptions and boundary conditions.",
                                "latency_ms": 25,
                                "verifier_call_count": 2,
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "export-evaluation-assets",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                    "--judge-model",
                    "remote-judge",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "table1_overall_metrics.csv").exists())
            self.assertTrue((output_dir / "table2_error_breakdown.csv").exists())
            self.assertTrue((output_dir / "table3_latency_cost.csv").exists())
            self.assertTrue((output_dir / "judge_requests.jsonl").exists())
            self.assertTrue((output_dir / "human_review.csv").exists())
            with (output_dir / "human_review.csv").open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["prompt_id"], "p1")
            self.assertIn("ttc_beam_answer", rows[0])

    def test_export_human_preference_table_cli_writes_table4(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            review_path = root / "human_review.csv"
            output_path = root / "table4_human_preference.csv"
            with review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "prompt_id",
                        "best_method",
                        "ttc_removes_visible_defects",
                        "ttc_loses_useful_information",
                        "verifier_over_penalizes_valid_wording",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "prompt_id": "p1",
                        "best_method": "ttc_beam",
                        "ttc_removes_visible_defects": "yes",
                        "ttc_loses_useful_information": "no",
                        "verifier_over_penalizes_valid_wording": "no",
                    }
                )

            exit_code = main(
                [
                    "export-human-preference-table",
                    "--input",
                    str(review_path),
                    "--output",
                    str(output_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            with output_path.open("r", encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["method"], "ttc_beam")
            self.assertEqual(rows[0]["best_count"], "1")


if __name__ == "__main__":
    unittest.main()
