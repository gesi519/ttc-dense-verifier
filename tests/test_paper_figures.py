import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.evaluation.figures import (
    build_architecture_mermaid,
    build_case_study_markdown,
    build_decoding_mermaid,
    build_quality_compute_rows,
)


def _sample_inference_row():
    return {
        "prompt_id": "p1",
        "prompt": "Explain memcpy versus memmove.",
        "method": "ttc_beam",
        "final_answer": "Use memmove when memory ranges overlap.",
        "final_score": 2.0,
        "latency_ms": 42.0,
        "verifier_call_count": 3,
        "decoding_parameters": {"beam_width": 2, "beta": 1.5},
        "branch_scores": [
            {"text": "memcpy is always safe.", "verifier_reward": -1.0, "total_score": -0.9},
            {"text": "Use memmove when ranges overlap.", "verifier_reward": 2.0, "total_score": 2.0},
        ],
        "step_traces": [
            {
                "step_index": 0,
                "kept": [{"text": "Use memmove when ranges overlap.", "total_score": 2.0}],
                "pruned": [{"text": "memcpy is always safe.", "total_score": -0.9}],
            }
        ],
    }


class PaperFigureTests(unittest.TestCase):
    def test_build_architecture_mermaid_mentions_workflow_components(self):
        mermaid = build_architecture_mermaid()

        self.assertIn("Frozen Qwen2.5-32B Generator", mermaid)
        self.assertIn("Dense Qwen2.5-7B Verifier", mermaid)
        self.assertIn("Beam Search / MCTS Controller", mermaid)
        self.assertIn("Preference Data", mermaid)

    def test_build_decoding_mermaid_uses_branch_scores_and_pruning(self):
        mermaid = build_decoding_mermaid([_sample_inference_row()])

        self.assertIn("Explain memcpy versus memmove", mermaid)
        self.assertIn("Verifier Score", mermaid)
        self.assertIn("Pruned Branch", mermaid)
        self.assertIn("Final Answer", mermaid)

    def test_build_quality_compute_rows_groups_by_method_and_budget(self):
        rows = build_quality_compute_rows(
            [
                _sample_inference_row(),
                {
                    **_sample_inference_row(),
                    "prompt_id": "p2",
                    "final_score": 1.0,
                    "latency_ms": 24.0,
                    "verifier_call_count": 1,
                },
            ]
        )

        self.assertEqual(rows[0]["method"], "ttc_beam")
        self.assertEqual(rows[0]["count"], 2)
        self.assertEqual(rows[0]["compute_budget"], "beam_width=2; beta=1.5")
        self.assertEqual(rows[0]["final_score_mean"], 1.5)
        self.assertEqual(rows[0]["verifier_call_count_mean"], 2.0)
        self.assertEqual(rows[0]["latency_ms_mean"], 33.0)

    def test_build_case_study_markdown_includes_branch_table(self):
        markdown = build_case_study_markdown(_sample_inference_row())

        self.assertIn("# Figure 4: Qualitative Case Study", markdown)
        self.assertIn("Explain memcpy versus memmove.", markdown)
        self.assertIn("| Branch | Verifier Reward | Total Score |", markdown)
        self.assertIn("memcpy is always safe.", markdown)
        self.assertIn("Use memmove when memory ranges overlap.", markdown)

    def test_export_paper_figures_cli_writes_required_figure_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "inference.jsonl"
            output_dir = root / "figures"
            input_path.write_text(json.dumps(_sample_inference_row()) + "\n", encoding="utf-8")

            exit_code = main(
                [
                    "export-paper-figures",
                    "--input",
                    str(input_path),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "figure1_architecture.mmd").exists())
            self.assertTrue((output_dir / "figure2_ttc_decoding.mmd").exists())
            self.assertTrue((output_dir / "figure3_quality_vs_compute.csv").exists())
            self.assertTrue((output_dir / "figure4_case_study.md").exists())
            with (output_dir / "figure3_quality_vs_compute.csv").open("r", encoding="utf-8", newline="") as handle:
                figure3_rows = list(csv.DictReader(handle))
            self.assertEqual(figure3_rows[0]["method"], "ttc_beam")


if __name__ == "__main__":
    unittest.main()
