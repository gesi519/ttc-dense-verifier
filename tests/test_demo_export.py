import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.cli import main
from ttc_dense_verifier.demo.static_site import render_demo_page


class DemoExportTests(unittest.TestCase):
    def test_render_demo_page_shows_prompt_scores_pruned_and_final_answer(self):
        records = [
            {
                "prompt_id": "p1",
                "prompt": "Explain memcpy versus memmove.",
                "method": "ttc_beam",
                "final_answer": "Use memmove when ranges overlap.",
                "final_score": 3.5,
                "verifier_call_count": 2,
                "branch_scores": [
                    {
                        "text": "Use memmove when ranges overlap.",
                        "verifier_reward": 2.0,
                        "total_score": 3.5,
                    }
                ],
                "step_traces": [
                    {
                        "kept": [{"text": "Use memmove when ranges overlap.", "total_score": 3.5}],
                        "pruned": [{"text": ">>> memcpy is always safe.", "total_score": -2.0}],
                    }
                ],
            }
        ]

        html = render_demo_page(records, title="TTC Demo")

        self.assertIn("TTC Demo", html)
        self.assertIn("Explain memcpy versus memmove.", html)
        self.assertIn("Use memmove when ranges overlap.", html)
        self.assertIn("Verifier calls", html)
        self.assertIn("Pruned branches", html)
        self.assertIn("-2.00", html)
        self.assertIn("3.50", html)

    def test_render_demo_page_escapes_untrusted_log_text(self):
        records = [
            {
                "prompt_id": "p1",
                "prompt": "<script>alert(1)</script>",
                "method": "ttc_beam",
                "final_answer": "<b>unsafe</b>",
                "final_score": 1,
                "verifier_call_count": 1,
                "branch_scores": [],
                "step_traces": [],
            }
        ]

        html = render_demo_page(records)

        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("&lt;b&gt;unsafe&lt;/b&gt;", html)

    def test_export_demo_page_cli_writes_html(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            input_path = root / "outputs.jsonl"
            output_path = root / "demo.html"
            input_path.write_text(
                json.dumps(
                    {
                        "prompt_id": "p1",
                        "prompt": "Explain stack versus heap.",
                        "method": "ttc_beam",
                        "final_answer": "Stack and heap differ by lifetime.",
                        "final_score": 2.25,
                        "verifier_call_count": 2,
                        "branch_scores": [],
                        "step_traces": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            exit_code = main(
                [
                    "export-demo-page",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--title",
                    "Verifier Demo",
                ]
            )

            self.assertEqual(exit_code, 0)
            html = output_path.read_text(encoding="utf-8")
            self.assertIn("Verifier Demo", html)
            self.assertIn("Explain stack versus heap.", html)


if __name__ == "__main__":
    unittest.main()
