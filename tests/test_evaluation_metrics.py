import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ttc_dense_verifier.evaluation.metrics import compute_text_metrics, summarize_metrics


class EvaluationMetricTests(unittest.TestCase):
    def test_compute_text_metrics_detects_workflow_quality_defects(self):
        text = """# Title
>>> This is a game changer!!! ===>
```c
int main(void) { return 0; }
"""

        metrics = compute_text_metrics(text)

        self.assertGreaterEqual(metrics["abnormal_symbol_count"], 2)
        self.assertEqual(metrics["code_fence_mismatch"], 1)
        self.assertEqual(metrics["slogan_phrase_count"], 1)
        self.assertEqual(metrics["heading_count"], 1)
        self.assertGreater(metrics["word_count"], 5)

    def test_summarize_metrics_averages_numeric_fields_by_method(self):
        rows = [
            {"method": "raw", "metrics": {"abnormal_symbol_count": 2, "word_count": 10}},
            {"method": "raw", "metrics": {"abnormal_symbol_count": 4, "word_count": 14}},
            {"method": "ttc_beam", "metrics": {"abnormal_symbol_count": 0, "word_count": 12}},
        ]

        summary = summarize_metrics(rows)

        self.assertEqual(summary["raw"]["count"], 2)
        self.assertEqual(summary["raw"]["abnormal_symbol_count_mean"], 3)
        self.assertEqual(summary["raw"]["word_count_mean"], 12)
        self.assertEqual(summary["ttc_beam"]["count"], 1)
        self.assertEqual(summary["ttc_beam"]["abnormal_symbol_count_mean"], 0)


if __name__ == "__main__":
    unittest.main()
